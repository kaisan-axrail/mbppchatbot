"""
Utility functions for Strand SDK interactions and common operations.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from shared.strand_client import StrandClient, StrandClientError, format_messages_for_strand, extract_text_from_strand_response

# Configure logging
logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Enumeration of query types for routing."""
    RAG = "rag"
    GENERAL = "general"
    MCP_TOOL = "mcp_tool"


class StrandUtils:
    """Utility class for common Strand SDK operations."""
    
    def __init__(self, strand_client: StrandClient):
        """
        Initialize StrandUtils with a Strand client.
        
        Args:
            strand_client: Configured StrandClient instance
        """
        self.client = strand_client
    
    async def determine_query_type(self, user_message: str) -> QueryType:
        """
        Determine the type of query using Claude Sonnet 4.5 via Strand SDK.
        
        Args:
            user_message: User's message to analyze
            
        Returns:
            QueryType enum value
            
        Raises:
            StrandClientError: If query type determination fails
        """
        try:
            base_prompt = """You are a query classifier for a chatbot system. Analyze the user's message and determine which type of processing is needed:

1. RAG (rag): Questions about documents, files, or specific information that would require searching through a knowledge base
2. GENERAL (general): General questions, conversations, or requests that can be answered with general knowledge
3. MCP_TOOL (mcp_tool): Requests that require using tools or performing actions (create, update, delete, search data, etc.)

Respond with only one word: "rag", "general", or "mcp_tool"."""
            
            # Add multilingual capabilities to classification
            from shared.multilingual_prompts import MultilingualPromptService
            multilingual_service = MultilingualPromptService()
            system_prompt = multilingual_service.ensure_multilingual_capabilities(base_prompt)
            
            messages = format_messages_for_strand(user_message)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=10,
                temperature=0.1
            )
            
            response_text = extract_text_from_strand_response(response).strip().lower()
            
            # Map response to QueryType
            if response_text == "rag":
                return QueryType.RAG
            elif response_text == "general":
                return QueryType.GENERAL
            elif response_text == "mcp_tool":
                return QueryType.MCP_TOOL
            else:
                # Default to general if unclear
                logger.warning(f"Unclear query type response: {response_text}, defaulting to general")
                return QueryType.GENERAL
                
        except Exception as e:
            logger.error(f"Failed to determine query type: {str(e)}")
            # Default to general on error
            return QueryType.GENERAL
    
    async def generate_general_response(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Generate a general response using Claude Sonnet 4.5 via Strand SDK.
        Handles clarification requests for unclear questions and maintains conversation context.
        
        Args:
            user_message: User's message
            conversation_history: Previous conversation messages
            
        Returns:
            Generated response text
            
        Raises:
            StrandClientError: If response generation fails
        """
        try:
            # Check if the question needs clarification
            needs_clarification = await self._needs_clarification(user_message, conversation_history)
            
            if needs_clarification:
                return await self._request_clarification(user_message, conversation_history)
            
            # Generate regular response with conversation context and multilingual support
            base_prompt = self._build_general_system_prompt(conversation_history)
            
            # Add multilingual capabilities
            from shared.multilingual_prompts import MultilingualPromptService
            multilingual_service = MultilingualPromptService()
            system_prompt = multilingual_service.ensure_multilingual_capabilities(base_prompt)
            
            messages = format_messages_for_strand(user_message, conversation_history)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1000
            )
            
            return extract_text_from_strand_response(response)
            
        except Exception as e:
            logger.error(f"Failed to generate general response: {str(e)}")
            raise StrandClientError(
                f"Failed to generate general response: {str(e)}",
                "GENERAL_RESPONSE_ERROR"
            )
    
    async def _needs_clarification(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]] = None
    ) -> bool:
        """
        Determine if a user message is unclear and needs clarification.
        
        Args:
            user_message: User's message to analyze
            conversation_history: Previous conversation messages for context
            
        Returns:
            True if clarification is needed, False otherwise
        """
        try:
            # Skip clarification check for very short messages or common greetings
            if len(user_message.strip()) < 3:
                return False
            
            common_greetings = ['hi', 'hello', 'hey', 'thanks', 'thank you', 'bye', 'goodbye']
            if user_message.strip().lower() in common_greetings:
                return False
            
            base_prompt = """You are analyzing user messages to determine if they are unclear and need clarification.

A message needs clarification if:
- It's extremely vague or ambiguous
- It contains unclear pronouns without context
- It asks about "this" or "that" without clear reference
- It's incomplete or fragmented
- It asks multiple unrelated questions at once

A message does NOT need clarification if:
- It's a clear question even if broad
- It's a greeting or social interaction
- It references previous conversation context appropriately
- It's a complete thought even if simple

Respond with only "yes" if clarification is needed, or "no" if the message is clear enough to answer."""
            
            # Add multilingual capabilities to clarification detection
            from shared.multilingual_prompts import MultilingualPromptService
            multilingual_service = MultilingualPromptService()
            system_prompt = multilingual_service.ensure_multilingual_capabilities(base_prompt)
            
            messages = format_messages_for_strand(user_message, conversation_history)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=5,
                temperature=0.1
            )
            
            response_text = extract_text_from_strand_response(response).strip().lower()
            return response_text == "yes"
            
        except Exception as e:
            logger.error(f"Failed to check if clarification needed: {str(e)}")
            # Default to not needing clarification on error
            return False
    
    async def _request_clarification(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Generate a clarification request for an unclear user message.
        
        Args:
            user_message: User's unclear message
            conversation_history: Previous conversation messages for context
            
        Returns:
            Clarification request message
        """
        try:
            system_prompt = """You are a helpful AI assistant. The user has sent a message that is unclear or ambiguous. Generate a polite clarification request that:

1. Acknowledges their message
2. Explains what specifically is unclear
3. Asks specific questions to help clarify their intent
4. Remains friendly and helpful

Keep the response concise and focused on getting the information needed to help them effectively."""
            
            messages = format_messages_for_strand(user_message, conversation_history)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=200,
                temperature=0.7
            )
            
            return extract_text_from_strand_response(response)
            
        except Exception as e:
            logger.error(f"Failed to generate clarification request: {str(e)}")
            # Fallback clarification message
            return "I'd be happy to help! Could you please provide a bit more detail about what you're looking for? This will help me give you a more accurate and useful response."
    
    def _build_general_system_prompt(self, conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Build a system prompt for general responses that considers conversation context.
        
        Args:
            conversation_history: Previous conversation messages
            
        Returns:
            System prompt string
        """
        base_prompt = """You are a helpful AI assistant powered by AWS Bedrock Claude models. Provide clear, accurate, and helpful responses to user questions. Be conversational and engaging while maintaining professionalism.

Key guidelines:
- Give comprehensive but concise answers
- Use examples when helpful
- Ask follow-up questions if it would be beneficial
- Maintain a friendly and professional tone
- If you're unsure about something, say so rather than guessing"""
        
        if conversation_history and len(conversation_history) > 0:
            context_prompt = """

You have access to the conversation history. Use this context to:
- Provide relevant follow-up responses
- Reference previous topics when appropriate
- Maintain conversation continuity
- Avoid repeating information already covered unless asked"""
            
            return base_prompt + context_prompt
        
        return base_prompt
    
    async def generate_rag_response(
        self, 
        user_message: str, 
        context_documents: List[Dict[str, Any]], 
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate a RAG response using retrieved documents and Claude Sonnet 4.5.
        
        Args:
            user_message: User's question
            context_documents: Retrieved document chunks
            conversation_history: Previous conversation messages
            
        Returns:
            Tuple of (response_text, source_citations)
            
        Raises:
            StrandClientError: If response generation fails
        """
        try:
            # Format context from documents
            context_text = self._format_context_documents(context_documents)
            
            system_prompt = f"""You are a helpful AI assistant that answers questions based on provided context documents. Use the following context to answer the user's question accurately and cite your sources.

Context Documents:
{context_text}

Instructions:
1. Answer the question based on the provided context
2. If the context doesn't contain relevant information, say so clearly
3. Cite sources by referencing the document names or IDs
4. Be accurate and don't make up information not in the context"""
            
            messages = format_messages_for_strand(user_message, conversation_history)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt
            )
            
            response_text = extract_text_from_strand_response(response)
            
            # Extract source citations
            sources = [doc.get('source', doc.get('id', 'Unknown')) for doc in context_documents]
            
            return response_text, sources
            
        except Exception as e:
            logger.error(f"Failed to generate RAG response: {str(e)}")
            raise StrandClientError(
                f"Failed to generate RAG response: {str(e)}",
                "RAG_RESPONSE_ERROR"
            )
    
    async def identify_mcp_tools(self, user_message: str) -> List[str]:
        """
        Identify required MCP tools from user message using Claude Sonnet 4.5.
        
        Args:
            user_message: User's message requesting tool usage
            
        Returns:
            List of tool names to execute
            
        Raises:
            StrandClientError: If tool identification fails
        """
        try:
            system_prompt = """You are a tool identifier for a chatbot system. Analyze the user's message and identify which MCP tools are needed.

Available tools:
- search_documents: Search for documents using vector similarity
- create_record: Create a new record in the database
- read_record: Read a record from the database
- update_record: Update an existing record in the database
- delete_record: Delete a record from the database

Respond with a JSON array of tool names that are needed, for example: ["search_documents", "create_record"]
If no tools are needed, respond with an empty array: []"""
            
            messages = format_messages_for_strand(user_message)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=100,
                temperature=0.1
            )
            
            response_text = extract_text_from_strand_response(response).strip()
            
            # Parse JSON response
            import json
            try:
                tools = json.loads(response_text)
                if isinstance(tools, list):
                    return tools
                else:
                    logger.warning(f"Tool identification returned non-list: {tools}")
                    return []
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool identification response: {response_text}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to identify MCP tools: {str(e)}")
            return []
    
    async def process_tool_results(
        self, 
        user_message: str, 
        tool_results: List[Dict[str, Any]]
    ) -> str:
        """
        Process MCP tool results and generate a response using Claude Sonnet 4.5.
        
        Args:
            user_message: Original user message
            tool_results: Results from MCP tool execution
            
        Returns:
            Generated response incorporating tool results
            
        Raises:
            StrandClientError: If result processing fails
        """
        try:
            # Format tool results
            results_text = self._format_tool_results(tool_results)
            
            system_prompt = f"""You are a helpful AI assistant that processes tool execution results and provides clear responses to users.

The user made a request, and the following tools were executed:

Tool Results:
{results_text}

Based on these results, provide a clear and helpful response to the user's original request. Summarize what was accomplished and include relevant information from the tool results."""
            
            messages = format_messages_for_strand(user_message)
            
            response = await self.client.generate_response(
                messages=messages,
                system_prompt=system_prompt
            )
            
            return extract_text_from_strand_response(response)
            
        except Exception as e:
            logger.error(f"Failed to process tool results: {str(e)}")
            raise StrandClientError(
                f"Failed to process tool results: {str(e)}",
                "TOOL_RESULT_PROCESSING_ERROR"
            )
    
    def _format_context_documents(self, documents: List[Dict[str, Any]]) -> str:
        """
        Format context documents for RAG prompt.
        
        Args:
            documents: List of document chunks
            
        Returns:
            Formatted context string
        """
        if not documents:
            return "No relevant documents found."
        
        formatted_docs = []
        for i, doc in enumerate(documents, 1):
            source = doc.get('source', doc.get('id', f'Document {i}'))
            content = doc.get('content', '')
            score = doc.get('score', 0)
            
            formatted_docs.append(f"Document {i} (Source: {source}, Relevance: {score:.3f}):\n{content}")
        
        return "\n\n".join(formatted_docs)
    
    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """
        Format tool execution results for processing.
        
        Args:
            tool_results: List of tool execution results
            
        Returns:
            Formatted results string
        """
        if not tool_results:
            return "No tool results available."
        
        formatted_results = []
        for i, result in enumerate(tool_results, 1):
            tool_name = result.get('tool_name', f'Tool {i}')
            success = result.get('success', False)
            data = result.get('data', {})
            error = result.get('error', '')
            
            if success:
                formatted_results.append(f"Tool: {tool_name}\nStatus: Success\nResult: {data}")
            else:
                formatted_results.append(f"Tool: {tool_name}\nStatus: Failed\nError: {error}")
        
        return "\n\n".join(formatted_results)


def create_strand_utils(strand_client: StrandClient = None) -> StrandUtils:
    """
    Factory function to create StrandUtils with a client.
    
    Args:
        strand_client: Optional pre-configured StrandClient
        
    Returns:
        StrandUtils instance
    """
    if strand_client is None:
        from shared.strand_client import create_strand_client
        strand_client = create_strand_client()
    
    return StrandUtils(strand_client)