"""
Unit tests for RAG handler functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from shared.rag_handler import (
    RAGHandler, 
    DocumentChunk, 
    MCPClient,
    create_rag_handler
)
from shared.strand_client import StrandClient, StrandClientError
from shared.exceptions import ChatbotError, RagHandlerError


class TestDocumentChunk:
    """Test DocumentChunk class."""
    
    def test_document_chunk_creation(self):
        """Test DocumentChunk creation and properties."""
        chunk = DocumentChunk(
            id="doc_1",
            content="Test content",
            source="test.pdf",
            score=0.85
        )
        
        assert chunk.id == "doc_1"
        assert chunk.content == "Test content"
        assert chunk.source == "test.pdf"
        assert chunk.score == 0.85
    
    def test_document_chunk_to_dict(self):
        """Test DocumentChunk to_dict method."""
        chunk = DocumentChunk(
            id="doc_1",
            content="Test content",
            source="test.pdf",
            score=0.85
        )
        
        expected_dict = {
            'id': "doc_1",
            'content': "Test content",
            'source': "test.pdf",
            'score': 0.85
        }
        
        assert chunk.to_dict() == expected_dict
    
    def test_document_chunk_from_dict(self):
        """Test DocumentChunk from_dict class method."""
        data = {
            'id': "doc_1",
            'content': "Test content",
            'source': "test.pdf",
            'score': 0.85
        }
        
        chunk = DocumentChunk.from_dict(data)
        
        assert chunk.id == "doc_1"
        assert chunk.content == "Test content"
        assert chunk.source == "test.pdf"
        assert chunk.score == 0.85


class TestMCPClient:
    """Test MCPClient class."""
    
    def test_mcp_client_initialization(self):
        """Test MCPClient initialization."""
        client = MCPClient("http://test-endpoint")
        assert client.mcp_server_endpoint == "http://test-endpoint"
    
    @pytest.mark.asyncio
    async def test_search_documents_success(self):
        """Test successful document search via MCP."""
        client = MCPClient()
        
        # Mock the _call_mcp_server method
        mock_response = {
            'success': True,
            'result': [
                {
                    'id': 'doc_1',
                    'content': 'Test document content',
                    'source': 'test.pdf',
                    'score': 0.85
                }
            ]
        }
        
        with patch.object(client, '_call_mcp_server', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            
            results = await client.search_documents("test query", limit=5, threshold=0.7)
            
            assert len(results) == 1
            assert results[0]['id'] == 'doc_1'
            assert results[0]['content'] == 'Test document content'
            
            # Verify MCP call was made with correct parameters
            mock_call.assert_called_once_with({
                'tool': 'search_documents',
                'parameters': {
                    'query': 'test query',
                    'limit': 5,
                    'threshold': 0.7
                }
            })


class TestRAGHandler:
    """Test RAGHandler class."""
    
    @pytest.fixture
    def mock_strand_client(self):
        """Create mock Strand client."""
        client = Mock(spec=StrandClient)
        client.api_key = "test_key"
        return client
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Create mock MCP client."""
        client = Mock(spec=MCPClient)
        return client
    
    @pytest.fixture
    def rag_handler(self, mock_strand_client, mock_mcp_client):
        """Create RAG handler with mocked dependencies."""
        return RAGHandler(
            strand_client=mock_strand_client,
            mcp_client=mock_mcp_client,
            max_context_length=8000,
            min_relevance_score=0.7
        )
    
    def test_rag_handler_initialization(self, mock_strand_client):
        """Test RAG handler initialization."""
        handler = RAGHandler(strand_client=mock_strand_client)
        
        assert handler.strand_client == mock_strand_client
        assert handler.mcp_client is not None
        assert handler.max_context_length == 8000
        assert handler.min_relevance_score == 0.7
    
    @pytest.mark.asyncio
    async def test_search_documents_success(self, rag_handler, mock_mcp_client):
        """Test successful document search."""
        # Mock MCP client response
        mock_search_results = [
            {
                'id': 'doc_1',
                'content': 'Test content 1',
                'source': 'test1.pdf',
                'score': 0.85
            },
            {
                'id': 'doc_2',
                'content': 'Test content 2',
                'source': 'test2.pdf',
                'score': 0.75
            }
        ]
        
        mock_mcp_client.search_documents = AsyncMock(return_value=mock_search_results)
        
        results = await rag_handler.search_documents("test query", limit=5, threshold=0.7)
        
        assert len(results) == 2
        assert isinstance(results[0], DocumentChunk)
        assert results[0].id == 'doc_1'
        assert results[0].score == 0.85
        assert results[1].id == 'doc_2'
        assert results[1].score == 0.75
        
        # Verify results are sorted by score (highest first)
        assert results[0].score >= results[1].score


class TestEnhancedRAGIntegration:
    """Test enhanced RAG integration with Strand SDK."""
    
    @pytest.fixture
    def mock_strand_client(self):
        """Create mock Strand client."""
        client = Mock(spec=StrandClient)
        client.api_key = "test_key"
        return client
    
    @pytest.fixture
    def rag_handler(self, mock_strand_client):
        """Create RAG handler with mocked dependencies."""
        return RAGHandler(
            strand_client=mock_strand_client,
            max_context_length=8000,
            min_relevance_score=0.7
        )
    
    @pytest.mark.asyncio
    async def test_context_aware_response_generation(self, rag_handler, mock_strand_client):
        """Test context-aware response generation using Strand utilities."""
        document_chunks = [
            DocumentChunk("doc_1", "Important content about AI", "ai_guide.pdf", 0.92),
            DocumentChunk("doc_2", "Additional AI information", "ai_basics.pdf", 0.78)
        ]
        
        # Mock Strand utilities
        with patch('shared.strand_utils.StrandUtils') as mock_strand_utils_class:
            mock_strand_utils = mock_strand_utils_class.return_value
            mock_strand_utils.generate_rag_response = AsyncMock(
                return_value=(
                    "Based on the provided documents, AI is a powerful technology...",
                    ["ai_guide.pdf", "ai_basics.pdf"]
                )
            )
            
            response_content, sources = await rag_handler.generate_response(
                query="What is artificial intelligence?",
                document_chunks=document_chunks,
                conversation_history=[
                    {"role": "user", "content": "I'm learning about technology"},
                    {"role": "assistant", "content": "I'd be happy to help you learn!"}
                ]
            )
            
            # Verify response includes context-aware content
            assert "Based on the provided documents" in response_content
            assert "**Sources:**" in response_content
            assert "relevance: 0.92" in response_content
            assert "relevance: 0.78" in response_content
            
            # Verify sources are ordered by relevance (highest first)
            assert sources[0] == "ai_guide.pdf"  # Higher relevance score
            assert sources[1] == "ai_basics.pdf"  # Lower relevance score
            
            # Verify Strand utilities was called with correct context
            mock_strand_utils.generate_rag_response.assert_called_once()
            call_args = mock_strand_utils.generate_rag_response.call_args
            assert call_args[1]['user_message'] == "What is artificial intelligence?"
            assert len(call_args[1]['context_documents']) == 2
            assert call_args[1]['conversation_history'] is not None
    
    @pytest.mark.asyncio
    async def test_enhanced_source_citations(self, rag_handler):
        """Test enhanced source citations with relevance scores."""
        document_chunks = [
            DocumentChunk("doc_1", "Content 1", "high_relevance.pdf", 0.95),
            DocumentChunk("doc_2", "Content 2", "medium_relevance.pdf", 0.80),
            DocumentChunk("doc_3", "Content 3", "low_relevance.pdf", 0.72),
            DocumentChunk("doc_4", "Content 4", "high_relevance.pdf", 0.88)  # Duplicate source
        ]
        
        response_content = "This is the main response content."
        
        enhanced_response, sources = rag_handler._add_enhanced_source_citations(
            response_content, document_chunks
        )
        
        # Verify enhanced formatting
        assert "**Sources:**" in enhanced_response
        assert "relevance: 0.95" in enhanced_response
        assert "relevance: 0.80" in enhanced_response
        assert "relevance: 0.72" in enhanced_response
        
        # Verify sources are ordered by highest relevance score per source
        assert sources[0] == "high_relevance.pdf"  # 0.95 (highest score for this source)
        assert sources[1] == "medium_relevance.pdf"  # 0.80
        assert sources[2] == "low_relevance.pdf"  # 0.72
        
        # Verify no duplicate sources
        assert len(sources) == 3
        assert len(set(sources)) == 3
    
    @pytest.mark.asyncio
    async def test_no_documents_with_strand_utils(self, rag_handler, mock_strand_client):
        """Test no-documents handling using Strand utilities."""
        with patch('shared.strand_utils.StrandUtils') as mock_strand_utils_class:
            mock_strand_utils = mock_strand_utils_class.return_value
            mock_strand_utils.generate_general_response = AsyncMock(
                return_value="I understand you're looking for information, but I couldn't find relevant documents. Let me help you in other ways..."
            )
            
            response_content, sources = await rag_handler._handle_no_documents(
                query="What is quantum computing?",
                conversation_history=[{"role": "user", "content": "I'm interested in advanced topics"}]
            )
            
            assert "couldn't find relevant documents" in response_content
            assert len(sources) == 0
            
            # Verify Strand utilities was called for fallback
            mock_strand_utils.generate_general_response.assert_called_once()
            call_args = mock_strand_utils.generate_general_response.call_args
            assert "quantum computing" in call_args[1]['user_message']
            assert call_args[1]['conversation_history'] is not None
    
    @pytest.mark.asyncio
    async def test_no_documents_ultimate_fallback(self, rag_handler, mock_strand_client):
        """Test ultimate fallback when Strand utilities also fail."""
        with patch('shared.strand_utils.StrandUtils') as mock_strand_utils_class:
            mock_strand_utils = mock_strand_utils_class.return_value
            mock_strand_utils.generate_general_response = AsyncMock(
                side_effect=Exception("Strand utilities failed")
            )
            
            response_content, sources = await rag_handler._handle_no_documents(
                query="What is quantum computing?"
            )
            
            assert "having trouble processing your request" in response_content
            assert "No relevant documents were found" in response_content
            assert "try rephrasing your question" in response_content
            assert len(sources) == 0
    
    @pytest.mark.asyncio
    async def test_complete_rag_flow_with_context_awareness(self, rag_handler, mock_strand_client):
        """Test complete RAG flow with context-aware response generation."""
        # Mock MCP client search
        mock_mcp_client = Mock()
        mock_mcp_client.search_documents = AsyncMock(return_value=[
            {
                'id': 'doc_1',
                'content': 'Machine learning is a subset of AI that enables computers to learn...',
                'source': 'ml_fundamentals.pdf',
                'score': 0.89
            },
            {
                'id': 'doc_2', 
                'content': 'Deep learning uses neural networks with multiple layers...',
                'source': 'deep_learning_guide.pdf',
                'score': 0.82
            }
        ])
        rag_handler.mcp_client = mock_mcp_client
        
        # Mock Strand utilities
        with patch('shared.strand_utils.StrandUtils') as mock_strand_utils_class:
            mock_strand_utils = mock_strand_utils_class.return_value
            mock_strand_utils.generate_rag_response = AsyncMock(
                return_value=(
                    "Machine learning is indeed a powerful subset of AI. Based on the documents, it enables computers to learn from data without explicit programming. Deep learning, as mentioned in the sources, extends this concept using neural networks with multiple layers to process complex patterns.",
                    ["ml_fundamentals.pdf", "deep_learning_guide.pdf"]
                )
            )
            
            response_content, sources = await rag_handler.process_rag_query(
                query="Can you explain machine learning and deep learning?",
                conversation_history=[
                    {"role": "user", "content": "I'm studying AI concepts"},
                    {"role": "assistant", "content": "Great! I can help explain AI concepts."}
                ],
                max_documents=5,
                relevance_threshold=0.75
            )
            
            # Verify complete flow
            assert "Machine learning is indeed a powerful subset" in response_content
            assert "**Sources:**" in response_content
            assert "relevance: 0.89" in response_content
            assert "relevance: 0.82" in response_content
            assert len(sources) == 2
            
            # Verify MCP search was called
            mock_mcp_client.search_documents.assert_called_once_with(
                query="Can you explain machine learning and deep learning?",
                limit=5,
                threshold=0.75
            )
            
            # Verify Strand utilities was called with context
            mock_strand_utils.generate_rag_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_strand_client_error_handling(self, rag_handler, mock_strand_client):
        """Test proper error handling for Strand client errors."""
        document_chunks = [
            DocumentChunk("doc_1", "Test content", "test.pdf", 0.85)
        ]
        
        with patch('shared.strand_utils.StrandUtils') as mock_strand_utils_class:
            mock_strand_utils = mock_strand_utils_class.return_value
            mock_strand_utils.generate_rag_response = AsyncMock(
                side_effect=StrandClientError("Strand API error", "API_ERROR")
            )
            
            with pytest.raises(RagHandlerError) as exc_info:
                await rag_handler.generate_response(
                    query="test query",
                    document_chunks=document_chunks
                )
            
            assert "Response generation failed" in str(exc_info.value)
            assert exc_info.value.code == "STRAND_ERROR"
    
    def test_enhanced_citations_empty_chunks(self, rag_handler):
        """Test enhanced citations with empty document chunks."""
        response_content = "Test response"
        
        enhanced_response, sources = rag_handler._add_enhanced_source_citations(
            response_content, []
        )
        
        assert enhanced_response == response_content
        assert len(sources) == 0
    
    def test_enhanced_citations_single_source_multiple_chunks(self, rag_handler):
        """Test enhanced citations with multiple chunks from same source."""
        document_chunks = [
            DocumentChunk("doc_1", "Content 1", "same_source.pdf", 0.75),
            DocumentChunk("doc_2", "Content 2", "same_source.pdf", 0.90),  # Higher score
            DocumentChunk("doc_3", "Content 3", "same_source.pdf", 0.65)   # Lower score
        ]
        
        response_content = "Test response"
        
        enhanced_response, sources = rag_handler._add_enhanced_source_citations(
            response_content, document_chunks
        )
        
        # Should use highest relevance score for the source
        assert "relevance: 0.90" in enhanced_response
        assert "relevance: 0.75" not in enhanced_response
        assert "relevance: 0.65" not in enhanced_response
        
        # Should have only one source entry
        assert len(sources) == 1
        assert sources[0] == "same_source.pdf"


if __name__ == "__main__":
    pytest.main([__file__])