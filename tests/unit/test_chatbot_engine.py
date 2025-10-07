"""
Unit tests for ChatbotEngine class and query routing functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from shared.chatbot_engine import (
    ChatbotEngine, 
    ChatbotEngineError, 
    ChatbotResponse,
    create_chatbot_engine
)
from shared.strand_utils import QueryType
from shared.session_models import Session


class TestChatbotResponse:
    """Test cases for ChatbotResponse class."""
    
    def test_chatbot_response_creation(self):
        """Test ChatbotResponse object creation."""
        response = ChatbotResponse(
            content="Test response",
            query_type=QueryType.GENERAL,
            sources=["source1", "source2"],
            tools_used=["tool1"],
            response_time=150.5
        )
        
        assert response.content == "Test response"
        assert response.query_type == QueryType.GENERAL
        assert response.sources == ["source1", "source2"]
        assert response.tools_used == ["tool1"]
        assert response.response_time == 150.5
        assert response.message_id is not None
        assert response.timestamp is not None
    
    def test_chatbot_response_to_dict(self):
        """Test ChatbotResponse to_dict conversion."""
        response = ChatbotResponse(
            content="Test response",
            query_type=QueryType.RAG,
            message_id="test-msg-123"
        )
        
        result = response.to_dict()
        
        assert result['message_id'] == "test-msg-123"
        assert result['content'] == "Test response"
        assert result['query_type'] == "rag"
        assert result['sources'] == []
        assert result['tools_used'] == []
        assert 'timestamp' in result


class TestChatbotEngine:
    """Test cases for ChatbotEngine class."""
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_init_with_defaults(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test ChatbotEngine initialization with default parameters."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        mock_session_mgr = Mock()
        mock_session_manager.return_value = mock_session_mgr
        
        engine = ChatbotEngine()
        
        assert engine.region == 'us-east-1'
        assert engine.strand_client == mock_strand_client
        assert engine.session_manager == mock_session_mgr
        mock_create_strand.assert_called_once_with(region='us-east-1')
        mock_session_manager.assert_called_once_with(region='us-east-1')
    
    @patch('shared.chatbot_engine.boto3.resource')
    def test_init_with_custom_clients(self, mock_boto):
        """Test ChatbotEngine initialization with custom clients."""
        mock_strand_client = Mock()
        mock_session_manager = Mock()
        
        engine = ChatbotEngine(
            strand_client=mock_strand_client,
            session_manager=mock_session_manager,
            region='us-west-2'
        )
        
        assert engine.region == 'us-west-2'
        assert engine.strand_client == mock_strand_client
        assert engine.session_manager == mock_session_manager
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_determine_query_type_success(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test successful query type determination."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        
        engine = ChatbotEngine()
        engine.strand_utils.determine_query_type = AsyncMock(return_value=QueryType.RAG)
        
        result = await engine.determine_query_type("Search for documents about AI")
        
        assert result == QueryType.RAG
        engine.strand_utils.determine_query_type.assert_called_once_with("Search for documents about AI")
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_determine_query_type_error_fallback(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test query type determination with error fallback."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        
        engine = ChatbotEngine()
        engine.strand_utils.determine_query_type = AsyncMock(side_effect=Exception("API error"))
        
        result = await engine.determine_query_type("Test message")
        
        assert result == QueryType.GENERAL
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_process_message_invalid_session(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test processing message with invalid session."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        mock_session_mgr = Mock()
        mock_session_manager.return_value = mock_session_mgr
        
        # Mock invalid session
        mock_session_mgr.get_session = AsyncMock(return_value=None)
        
        engine = ChatbotEngine()
        
        with pytest.raises(ChatbotEngineError) as exc_info:
            await engine.process_message("invalid-session", "Hello")
        
        assert exc_info.value.error_code == "INVALID_SESSION"
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_process_message_general_query(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test processing a general query message."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        mock_session_mgr = Mock()
        mock_session_manager.return_value = mock_session_mgr
        
        # Mock valid session
        from datetime import datetime, timezone
        from shared.session_models import SessionStatus
        mock_session = Session(
            session_id="test-session",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_activity=datetime(2024, 1, 1, tzinfo=timezone.utc),
            status=SessionStatus.ACTIVE
        )
        mock_session_mgr.get_session = AsyncMock(return_value=mock_session)
        mock_session_mgr.update_activity = AsyncMock()
        
        engine = ChatbotEngine()
        
        # Mock query type determination
        engine.determine_query_type = AsyncMock(return_value=QueryType.GENERAL)
        
        # Mock general response generation
        engine.strand_utils.generate_general_response = AsyncMock(
            return_value="This is a general response"
        )
        
        # Mock logging methods
        engine._log_conversation = AsyncMock()
        
        result = await engine.process_message("test-session", "Hello, how are you?")
        
        assert isinstance(result, ChatbotResponse)
        assert result.content == "This is a general response"
        assert result.query_type == QueryType.GENERAL
        assert result.sources == []
        assert result.tools_used == []
        assert result.response_time is not None
        
        mock_session_mgr.update_activity.assert_called_once_with("test-session")
        engine._log_conversation.assert_called_once()
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_process_message_rag_query(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test processing a RAG query message."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        mock_session_mgr = Mock()
        mock_session_manager.return_value = mock_session_mgr
        
        # Mock valid session
        from datetime import datetime, timezone
        from shared.session_models import SessionStatus
        mock_session = Session(
            session_id="test-session",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_activity=datetime(2024, 1, 1, tzinfo=timezone.utc),
            status=SessionStatus.ACTIVE
        )
        mock_session_mgr.get_session = AsyncMock(return_value=mock_session)
        mock_session_mgr.update_activity = AsyncMock()
        
        engine = ChatbotEngine()
        
        # Mock query type determination
        engine.determine_query_type = AsyncMock(return_value=QueryType.RAG)
        
        # Mock RAG response generation
        engine.strand_utils.generate_rag_response = AsyncMock(
            return_value=("RAG response with context", ["doc1.pdf", "doc2.pdf"])
        )
        
        # Mock logging methods
        engine._log_conversation = AsyncMock()
        
        result = await engine.process_message("test-session", "What does the document say about AI?")
        
        assert isinstance(result, ChatbotResponse)
        assert result.content == "RAG response with context"
        assert result.query_type == QueryType.RAG
        assert result.sources == ["doc1.pdf", "doc2.pdf"]
        assert result.tools_used == []
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_process_message_mcp_query(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test processing an MCP tool query message."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        mock_session_mgr = Mock()
        mock_session_manager.return_value = mock_session_mgr
        
        # Mock valid session
        from datetime import datetime, timezone
        from shared.session_models import SessionStatus
        mock_session = Session(
            session_id="test-session",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_activity=datetime(2024, 1, 1, tzinfo=timezone.utc),
            status=SessionStatus.ACTIVE
        )
        mock_session_mgr.get_session = AsyncMock(return_value=mock_session)
        mock_session_mgr.update_activity = AsyncMock()
        
        engine = ChatbotEngine()
        
        # Mock query type determination
        engine.determine_query_type = AsyncMock(return_value=QueryType.MCP_TOOL)
        
        # Mock MCP tool operations
        engine.strand_utils.identify_mcp_tools = AsyncMock(
            return_value=["create_record", "search_documents"]
        )
        engine.strand_utils.process_tool_results = AsyncMock(
            return_value="Tool execution completed successfully"
        )
        
        # Mock logging methods
        engine._log_conversation = AsyncMock()
        
        result = await engine.process_message("test-session", "Create a new record with this data")
        
        assert isinstance(result, ChatbotResponse)
        assert result.content == "Tool execution completed successfully"
        assert result.query_type == QueryType.MCP_TOOL
        assert result.sources == []
        assert result.tools_used == ["create_record", "search_documents"]
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_get_conversation_history_empty(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test getting conversation history when cache is empty."""
        engine = ChatbotEngine()
        
        history = engine._get_conversation_history("new-session")
        
        assert history == []
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_update_conversation_context(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test updating conversation context cache."""
        engine = ChatbotEngine()
        
        engine._update_conversation_context("test-session", "Hello", "Hi there!")
        
        history = engine._get_conversation_history("test-session")
        
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi there!"}
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_update_conversation_context_limit(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test conversation context cache limit."""
        engine = ChatbotEngine()
        
        # Add 25 exchanges (50 messages) to exceed limit
        for i in range(25):
            engine._update_conversation_context("test-session", f"User message {i}", f"Assistant response {i}")
        
        history = engine._get_conversation_history("test-session")
        
        # Should be limited to 20 messages (10 exchanges)
        assert len(history) == 20
        assert "User message 15" in history[0]["content"]  # Should start from message 15
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_get_engine_status(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test getting engine status."""
        mock_strand_client = Mock()
        mock_strand_client.api_key = "test-key"
        mock_create_strand.return_value = mock_strand_client
        
        engine = ChatbotEngine(region='us-west-2')
        engine._conversation_cache = {"session1": [], "session2": []}
        
        status = engine.get_engine_status()
        
        assert status['region'] == 'us-west-2'
        assert status['strand_client_configured'] is True
        assert status['cached_sessions'] == 2
        assert 'conversations_table' in status
        assert 'analytics_table' in status
        assert 'timestamp' in status
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_rag_query_fallback(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test RAG query handling with fallback to general response."""
        engine = ChatbotEngine()
        
        # Mock RAG response failure
        engine.strand_utils.generate_rag_response = AsyncMock(side_effect=Exception("RAG error"))
        engine.strand_utils.generate_general_response = AsyncMock(return_value="Fallback response")
        
        result, sources = await engine._handle_rag_query("Test query", [])
        
        assert result == "Fallback response"
        assert sources == []
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_general_query_error(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test general query handling with error."""
        engine = ChatbotEngine()
        
        # Mock general response failure
        engine.strand_utils.generate_general_response = AsyncMock(side_effect=Exception("General error"))
        
        result = await engine._handle_general_query("Test query", [])
        
        assert "I apologize" in result
        assert "trouble processing" in result
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_mcp_query_no_tools(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test MCP query handling when no tools are needed."""
        engine = ChatbotEngine()
        
        # Mock no tools identified
        engine.strand_utils.identify_mcp_tools = AsyncMock(return_value=[])
        engine.strand_utils.generate_general_response = AsyncMock(return_value="General response")
        
        result, tools = await engine._handle_mcp_query("Test query", [])
        
        assert result == "General response"
        assert tools == []


class TestGeneralQuestionHandler:
    """Test cases for enhanced general question handling functionality."""
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_general_query_with_context(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test general query handling with conversation context."""
        mock_strand_client = Mock()
        mock_create_strand.return_value = mock_strand_client
        
        engine = ChatbotEngine()
        
        # Mock conversation history
        conversation_history = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "Tell me more about it"}
        ]
        
        # Mock strand utils response
        engine.strand_utils.generate_general_response = AsyncMock(
            return_value="Python is a high-level programming language known for its simplicity and readability."
        )
        
        result = await engine._handle_general_query("Tell me more about it", conversation_history)
        
        assert result == "Python is a high-level programming language known for its simplicity and readability."
        
        # Verify that enhanced context was passed
        call_args = engine.strand_utils.generate_general_response.call_args
        assert call_args[0][0] == "Tell me more about it"  # message
        enhanced_history = call_args[0][1]  # enhanced history
        assert len(enhanced_history) == 3
        assert all(msg['role'] in ['user', 'assistant'] for msg in enhanced_history)
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_general_query_context_filtering(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test conversation context filtering and limiting."""
        engine = ChatbotEngine()
        
        # Create a long conversation history (15 messages)
        long_history = []
        for i in range(15):
            long_history.append({"role": "user", "content": f"User message {i}"})
            long_history.append({"role": "assistant", "content": f"Assistant response {i}"})
        
        # Add some empty and invalid messages
        long_history.append({"role": "system", "content": "System message"})
        long_history.append({"role": "user", "content": ""})
        long_history.append({"role": "assistant", "content": "   "})
        
        enhanced_history = engine._enhance_conversation_context(long_history)
        
        # Should be limited to 10 messages and filtered
        assert len(enhanced_history) <= 10
        assert all(msg['role'] in ['user', 'assistant'] for msg in enhanced_history)
        assert all(msg['content'].strip() for msg in enhanced_history)
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_general_query_timeout_error(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test general query handling with timeout error."""
        engine = ChatbotEngine()
        
        # Mock timeout error
        engine.strand_utils.generate_general_response = AsyncMock(
            side_effect=Exception("Request timeout occurred")
        )
        
        result = await engine._handle_general_query("Test query", [])
        
        assert "taking a bit longer" in result.lower()
        assert "try asking your question again" in result.lower()
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_general_query_rate_limit_error(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test general query handling with rate limit error."""
        engine = ChatbotEngine()
        
        # Mock rate limit error
        engine.strand_utils.generate_general_response = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )
        
        result = await engine._handle_general_query("Test query", [])
        
        assert "handling a lot of requests" in result.lower()
        assert "wait a moment" in result.lower()
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    @pytest.mark.asyncio
    async def test_handle_general_query_service_unavailable_error(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test general query handling with service unavailable error."""
        engine = ChatbotEngine()
        
        # Mock service unavailable error
        engine.strand_utils.generate_general_response = AsyncMock(
            side_effect=Exception("Service temporarily unavailable")
        )
        
        result = await engine._handle_general_query("Test query", [])
        
        assert "technical difficulties" in result.lower()
        assert "try again in a few moments" in result.lower()
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_get_error_fallback_message_generic(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test generic error fallback message."""
        engine = ChatbotEngine()
        
        result = engine._get_error_fallback_message("Unknown error occurred")
        
        assert "apologize" in result.lower()
        assert "trouble processing" in result.lower()
        assert "try rephrasing" in result.lower()
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_enhance_conversation_context_empty(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test enhancing empty conversation context."""
        engine = ChatbotEngine()
        
        result = engine._enhance_conversation_context([])
        
        assert result == []
    
    @patch('shared.chatbot_engine.boto3.resource')
    @patch('shared.chatbot_engine.SessionManager')
    @patch('shared.strand_client.create_strand_client')
    def test_enhance_conversation_context_valid_messages(self, mock_create_strand, mock_session_manager, mock_boto):
        """Test enhancing conversation context with valid messages."""
        engine = ChatbotEngine()
        
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "system", "content": "System message"},  # Should be filtered out
            {"role": "user", "content": ""},  # Should be filtered out
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thanks!"}
        ]
        
        result = engine._enhance_conversation_context(history)
        
        assert len(result) == 4  # Only valid user/assistant messages
        assert all(msg['role'] in ['user', 'assistant'] for msg in result)
        assert all(msg['content'].strip() for msg in result)


class TestChatbotEngineFactory:
    """Test cases for ChatbotEngine factory function."""
    
    @patch('shared.chatbot_engine.ChatbotEngine')
    def test_create_chatbot_engine_factory(self, mock_chatbot_engine):
        """Test factory function for creating ChatbotEngine."""
        mock_strand_client = Mock()
        mock_session_manager = Mock()
        mock_instance = Mock()
        mock_chatbot_engine.return_value = mock_instance
        
        result = create_chatbot_engine(
            strand_client=mock_strand_client,
            session_manager=mock_session_manager,
            region='us-west-2'
        )
        
        mock_chatbot_engine.assert_called_once_with(
            strand_client=mock_strand_client,
            session_manager=mock_session_manager,
            region='us-west-2'
        )
        assert result == mock_instance


if __name__ == '__main__':
    pytest.main([__file__])