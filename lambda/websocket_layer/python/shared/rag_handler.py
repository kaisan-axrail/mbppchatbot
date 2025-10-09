"""
RAG (Retrieval-Augmented Generation) handler for document search and response generation.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import json
import asyncio
from datetime import datetime

from shared.strand_client import StrandClient, format_messages_for_strand, extract_text_from_strand_response
from shared.exceptions import (
    RagHandlerError,
    StrandClientError,
    DocumentSearchError,
    EmbeddingGenerationError,
    McpCommunicationError,
    get_user_friendly_message
)
from shared.retry_utils import (
    retry_with_backoff,
    with_graceful_degradation,
    MCP_RETRY_CONFIG,
    OPENSEARCH_RETRY_CONFIG,
    handle_service_failure
)

# Configure logging
logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a document chunk from search results."""
    
    def __init__(self, id: str, content: str, source: str, score: float):
        self.id = id
        self.content = content
        self.source = source
        self.score = score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'id': self.id,
            'content': self.content,
            'source': self.source,
            'score': self.score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        """Create DocumentChunk from dictionary."""
        return cls(
            id=data['id'],
            content=data['content'],
            source=data['source'],
            score=data['score']
        )


class MCPClient:
    """Simple MCP client for communicating with MCP server."""
    
    def __init__(self, mcp_server_endpoint: str = None):
        """
        Initialize MCP client.
        
        Args:
            mcp_server_endpoint: MCP server endpoint URL or Lambda ARN
        """
        self.mcp_server_endpoint = mcp_server_endpoint
        self.logger = logging.getLogger(f"{__name__}.MCPClient")
    
    @retry_with_backoff(
        config=MCP_RETRY_CONFIG,
        service_name="knowledge_base_search"
    )
    async def search_documents(
        self, 
        query: str, 
        limit: int = 5, 
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search documents using Bedrock Knowledge Base.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            threshold: Minimum similarity score
            
        Returns:
            List of document search results
            
        Raises:
            RAGHandlerError: If Knowledge Base search fails
        """
        try:
            import os
            import boto3
            
            self.logger.info(f"Searching Knowledge Base: {query[:50]}...")
            
            knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
            if not knowledge_base_id:
                self.logger.warning("Knowledge Base ID not configured, using fallback")
                return await self._fallback_search(query, limit)
            
            # Use Bedrock Knowledge Base for retrieval
            bedrock_agent_client = boto3.client('bedrock-agent-runtime')
            
            response = bedrock_agent_client.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={'text': query},
                retrievalConfiguration={
                    'vectorSearchConfiguration': {
                        'numberOfResults': limit
                    }
                }
            )
            
            # Format results
            results = []
            for result in response.get('retrievalResults', []):
                content = result.get('content', {})
                metadata = result.get('metadata', {})
                score = result.get('score', 0.0)
                
                if score >= threshold:
                    results.append({
                        'id': metadata.get('source', f'kb_result_{len(results)}'),
                        'content': content.get('text', ''),
                        'source': metadata.get('source', 'Knowledge Base'),
                        'score': score
                    })
            
            self.logger.info(f"Knowledge Base returned {len(results)} documents")
            return results
            
        except Exception as e:
            self.logger.error(f"Knowledge Base search error: {str(e)}")
            return await self._fallback_search(query, limit)
    
    async def _fallback_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Fallback search using S3 processed documents.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Search results from S3 documents
        """
        import os
        import boto3
        
        self.logger.info("Using S3 document search (Knowledge Base not configured)")
        
        processed_bucket = os.environ.get('PROCESSED_BUCKET', '')
        if not processed_bucket:
            self.logger.warning("No processed bucket configured")
            return []
        
        try:
            s3 = boto3.client('s3')
            
            # List processed documents
            response = s3.list_objects_v2(Bucket=processed_bucket, Prefix='processed/')
            
            results = []
            query_lower = query.lower()
            
            for obj in response.get('Contents', []):
                if len(results) >= limit:
                    break
                    
                key = obj['Key']
                
                try:
                    # Get document content
                    doc = s3.get_object(Bucket=processed_bucket, Key=key)
                    content = doc['Body'].read().decode('utf-8')
                    
                    # Simple keyword matching
                    if query_lower in content.lower():
                        # Extract relevant snippet
                        idx = content.lower().find(query_lower)
                        start = max(0, idx - 200)
                        end = min(len(content), idx + 300)
                        snippet = content[start:end]
                        
                        results.append({
                            'id': key,
                            'content': snippet,
                            'source': key.split('/')[-1],
                            'score': 0.85
                        })
                except Exception as e:
                    self.logger.warning(f"Error reading {key}: {str(e)}")
                    continue
            
            self.logger.info(f"Found {len(results)} documents in S3")
            return results
            
        except Exception as e:
            self.logger.error(f"S3 search error: {str(e)}")
            return []


class RAGHandler:
    """
    RAG (Retrieval-Augmented Generation) handler for document search and response generation.
    """
    
    def __init__(
        self,
        strand_client: StrandClient,
        mcp_client: MCPClient = None,
        max_context_length: int = 8000,
        min_relevance_score: float = 0.7
    ):
        """
        Initialize RAG handler.
        
        Args:
            strand_client: Configured Strand SDK client
            mcp_client: MCP client for document retrieval
            max_context_length: Maximum context length for response generation
            min_relevance_score: Minimum relevance score for document inclusion
        """
        self.strand_client = strand_client
        self.mcp_client = mcp_client or MCPClient()
        self.max_context_length = max_context_length
        self.min_relevance_score = min_relevance_score
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("RAG handler initialized successfully")
    
    async def search_documents(
        self, 
        query: str, 
        limit: int = 5, 
        threshold: float = None
    ) -> List[DocumentChunk]:
        """
        Search for relevant documents using MCP integration.
        
        Args:
            query: Search query text
            limit: Maximum number of documents to retrieve
            threshold: Minimum relevance score threshold
            
        Returns:
            List of DocumentChunk objects
            
        Raises:
            RAGHandlerError: If document search fails
        """
        try:
            # Use provided threshold or default
            threshold = threshold or self.min_relevance_score
            
            self.logger.info(f"Searching documents for query: {query[:100]}...")
            
            # Search documents via MCP client
            search_results = await self.mcp_client.search_documents(
                query=query,
                limit=limit,
                threshold=threshold
            )
            
            # Convert results to DocumentChunk objects
            document_chunks = []
            for result in search_results:
                try:
                    chunk = DocumentChunk.from_dict(result)
                    if chunk.score >= threshold:
                        document_chunks.append(chunk)
                except Exception as e:
                    self.logger.warning(f"Failed to parse document chunk: {str(e)}")
                    continue
            
            # Sort by relevance score (highest first)
            document_chunks.sort(key=lambda x: x.score, reverse=True)
            
            self.logger.info(f"Found {len(document_chunks)} relevant documents")
            return document_chunks
            
        except (RagHandlerError, DocumentSearchError):
            raise
        except Exception as e:
            self.logger.error(f"Document search failed: {str(e)}")
            raise DocumentSearchError(f"Document search failed: {str(e)}")
    
    async def generate_response(
        self,
        query: str,
        document_chunks: List[DocumentChunk],
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate context-aware response using retrieved documents and Strand SDK.
        
        Args:
            query: User's query
            document_chunks: Retrieved document chunks
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (response_content, source_citations)
            
        Raises:
            RAGHandlerError: If response generation fails
        """
        try:
            self.logger.info(f"Generating RAG response with {len(document_chunks)} documents")
            
            # Handle case with no relevant documents
            if not document_chunks:
                return await self._handle_no_documents(query, conversation_history)
            
            # Convert document chunks to format expected by Strand utilities
            context_documents = [chunk.to_dict() for chunk in document_chunks]
            
            # Use Strand utilities for context-aware response generation
            from shared.strand_utils import StrandUtils
            strand_utils = StrandUtils(self.strand_client)
            
            # Generate response with context awareness
            response_content, initial_sources = await strand_utils.generate_rag_response(
                user_message=query,
                context_documents=context_documents,
                conversation_history=conversation_history
            )
            
            if not response_content:
                raise RagHandlerError("Empty response from Strand SDK", "EMPTY_RESPONSE")
            
            # Enhance source citations with proper formatting
            response_with_citations, sources = self._add_enhanced_source_citations(
                response_content, document_chunks
            )
            
            self.logger.info(f"Generated context-aware RAG response with {len(sources)} sources")
            return response_with_citations, sources
            
        except RagHandlerError:
            raise
        except StrandClientError as e:
            self.logger.error(f"Strand SDK error: {str(e)}")
            raise RagHandlerError(f"Response generation failed: {str(e)}", "STRAND_ERROR")
        except Exception as e:
            self.logger.error(f"RAG response generation failed: {str(e)}")
            raise RAGHandlerError(
                f"Response generation failed: {str(e)}",
                "RESPONSE_GENERATION_ERROR"
            )
    
    async def _handle_no_documents(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[str, List[str]]:
        """
        Handle case when no relevant documents are found using Strand utilities.
        
        Args:
            query: User's query
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (response_content, empty_sources_list)
        """
        try:
            self.logger.info("No relevant documents found, generating fallback response")
            
            # Use Strand utilities for consistent response generation
            from shared.strand_utils import StrandUtils
            strand_utils = StrandUtils(self.strand_client)
            
            # Create a specialized message for no-documents case
            no_docs_message = (
                f"I searched for information related to your question: '{query}', "
                "but I couldn't find any relevant documents in the knowledge base. "
                "Could you help me understand what specific information you're looking for, "
                "or would you like me to assist you with something else?"
            )
            
            # Generate contextual response using general response generation
            response_content = await strand_utils.generate_general_response(
                user_message=no_docs_message,
                conversation_history=conversation_history
            )
            
            if not response_content:
                # Ultimate fallback with helpful suggestions
                response_content = (
                    "I apologize, but I couldn't find any relevant information in the "
                    "available documents to answer your question. Here are some ways I can help:\n\n"
                    "• Try rephrasing your question with different keywords\n"
                    "• Ask about a more general topic related to your question\n"
                    "• Let me know if you'd like help with something else\n\n"
                    "What would you like to do?"
                )
            
            return response_content, []
            
        except Exception as e:
            self.logger.error(f"Fallback response generation failed: {str(e)}")
            # Ultimate fallback message with actionable suggestions
            fallback_message = (
                "I apologize, but I'm having trouble processing your request right now. "
                "This might be because:\n\n"
                "• No relevant documents were found for your query\n"
                "• There's a temporary issue with the system\n\n"
                "Please try rephrasing your question or try again in a moment."
            )
            return fallback_message, []
    
    def _build_context_from_documents(self, document_chunks: List[DocumentChunk]) -> str:
        """
        Build context string from document chunks.
        
        Args:
            document_chunks: List of document chunks
            
        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0
        
        for i, chunk in enumerate(document_chunks):
            # Format document chunk with source information
            chunk_text = f"[Document {i+1} - {chunk.source}]\n{chunk.content}\n"
            
            # Check if adding this chunk would exceed max context length
            if current_length + len(chunk_text) > self.max_context_length:
                self.logger.info(f"Context length limit reached, using {i} documents")
                break
            
            context_parts.append(chunk_text)
            current_length += len(chunk_text)
        
        return "\n".join(context_parts)
    
    def _create_rag_system_prompt(self, context: str) -> str:
        """
        Create system prompt for RAG response generation.
        
        Args:
            context: Document context string
            
        Returns:
            System prompt for Strand SDK
        """
        return f"""You are a helpful assistant that answers questions based on the provided documents. 

Use the following documents to answer the user's question:

{context}

Instructions:
1. Answer the question based primarily on the information in the provided documents
2. If the documents don't contain enough information to fully answer the question, say so
3. Be accurate and cite specific information from the documents when possible
4. If you need to make inferences, clearly indicate that you're doing so
5. Keep your response focused and relevant to the user's question
6. Use a natural, conversational tone while being informative

Remember: Base your answer on the provided documents, and be honest about any limitations in the available information."""
    
    def _add_source_citations(
        self, 
        response_content: str, 
        document_chunks: List[DocumentChunk]
    ) -> Tuple[str, List[str]]:
        """
        Add source citations to the response.
        
        Args:
            response_content: Generated response content
            document_chunks: Document chunks used for generation
            
        Returns:
            Tuple of (response_with_citations, source_list)
        """
        # Extract unique sources
        sources = list(set(chunk.source for chunk in document_chunks))
        sources.sort()  # Sort for consistent ordering
        
        if not sources:
            return response_content, []
        
        # Add citations to response
        citations_text = "\n\nSources:\n" + "\n".join(f"• {source}" for source in sources)
        response_with_citations = response_content + citations_text
        
        return response_with_citations, sources
    
    def _add_enhanced_source_citations(
        self, 
        response_content: str, 
        document_chunks: List[DocumentChunk]
    ) -> Tuple[str, List[str]]:
        """
        Add enhanced source citations with relevance scores to the response.
        
        Args:
            response_content: Generated response content
            document_chunks: Document chunks used for generation
            
        Returns:
            Tuple of (response_with_citations, source_list)
        """
        if not document_chunks:
            return response_content, []
        
        # Group chunks by source and get highest relevance score per source
        source_scores = {}
        for chunk in document_chunks:
            if chunk.source not in source_scores or chunk.score > source_scores[chunk.source]:
                source_scores[chunk.source] = chunk.score
        
        # Sort sources by relevance score (highest first)
        sorted_sources = sorted(source_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Format citations with relevance information
        citations_parts = []
        for source, score in sorted_sources:
            citations_parts.append(f"• {source} (relevance: {score:.2f})")
        
        citations_text = "\n\n**Sources:**\n" + "\n".join(citations_parts)
        response_with_citations = response_content + citations_text
        
        # Return just the source names for the sources list
        sources = [source for source, _ in sorted_sources]
        
        return response_with_citations, sources
    
    async def process_rag_query(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None,
        max_documents: int = 5,
        relevance_threshold: float = None
    ) -> Tuple[str, List[str]]:
        """
        Process a complete RAG query from search to response generation.
        
        Args:
            query: User's query
            conversation_history: Previous conversation messages
            max_documents: Maximum number of documents to retrieve
            relevance_threshold: Minimum relevance score for documents
            
        Returns:
            Tuple of (response_content, source_citations)
            
        Raises:
            RAGHandlerError: If RAG processing fails
        """
        try:
            start_time = datetime.now()
            
            # Search for relevant documents
            document_chunks = await self.search_documents(
                query=query,
                limit=max_documents,
                threshold=relevance_threshold
            )
            
            # Generate response with retrieved documents
            response_content, sources = await self.generate_response(
                query=query,
                document_chunks=document_chunks,
                conversation_history=conversation_history
            )
            
            # Log processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            self.logger.info(f"RAG query processed in {processing_time:.2f} seconds")
            
            return response_content, sources
            
        except RAGHandlerError:
            raise
        except Exception as e:
            self.logger.error(f"RAG query processing failed: {str(e)}")
            raise RAGHandlerError(
                f"RAG query processing failed: {str(e)}",
                "RAG_PROCESSING_ERROR"
            )
    
    def get_handler_status(self) -> Dict[str, Any]:
        """
        Get current RAG handler status and configuration.
        
        Returns:
            Status dictionary
        """
        return {
            'strand_client_configured': bool(self.strand_client.api_key),
            'mcp_client_configured': bool(self.mcp_client),
            'max_context_length': self.max_context_length,
            'min_relevance_score': self.min_relevance_score,
            'timestamp': datetime.now().isoformat()
        }


def create_rag_handler(
    strand_client: StrandClient,
    mcp_server_endpoint: str = None,
    max_context_length: int = 8000,
    min_relevance_score: float = 0.7
) -> RAGHandler:
    """
    Factory function to create a configured RAG handler.
    
    Args:
        strand_client: Configured Strand SDK client
        mcp_server_endpoint: MCP server endpoint
        max_context_length: Maximum context length for responses
        min_relevance_score: Minimum relevance score for documents
        
    Returns:
        Configured RAGHandler instance
    """
    mcp_client = MCPClient(mcp_server_endpoint)
    
    return RAGHandler(
        strand_client=strand_client,
        mcp_client=mcp_client,
        max_context_length=max_context_length,
        min_relevance_score=min_relevance_score
    )