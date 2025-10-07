"""
Basic integration tests for core system functionality.

These tests verify basic integration between components without
complex async mocking or external service dependencies.
"""

import pytest
import json
import uuid
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Import components for testing
from shared.session_models import ClientInfo, generate_session_id, validate_session_id
from shared.utils import (
    generate_message_id, 
    get_current_timestamp, 
    validate_message_id,
    format_error_response,
    create_response_metadata
)
from shared.exceptions import ChatbotError, SessionNotFoundError


class TestBasicIntegration:
    """Basic integration tests for core functionality."""
    
    def test_session_id_generation_and_validation(self):
        """Test session ID generation and validation integration."""
        # Generate session ID
        session_id = generate_session_id()
        
        # Validate format
        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        assert validate_session_id(session_id) is True
        
        # Test invalid session IDs
        assert validate_session_id("invalid-id") is False
        assert validate_session_id("") is False
        assert validate_session_id(None) is False
    
    def test_message_id_generation_and_validation(self):
        """Test message ID generation and validation integration."""
        # Generate message ID
        message_id = generate_message_id()
        
        # Validate format
        assert message_id is not None
        assert len(message_id) == 36  # UUID format
        assert validate_message_id(message_id) is True
        
        # Test invalid message IDs
        assert validate_message_id("invalid-id") is False
        assert validate_message_id("") is False
    
    def test_client_info_creation_and_validation(self):
        """Test client info creation and validation."""
        # Create client info with all fields
        client_info = ClientInfo(
            user_agent="test-browser/1.0",
            ip_address="192.168.1.100",
            connection_id="conn-123"
        )
        
        assert client_info.user_agent == "test-browser/1.0"
        assert client_info.ip_address == "192.168.1.100"
        assert client_info.connection_id == "conn-123"
        
        # Create client info with minimal fields
        minimal_client_info = ClientInfo()
        assert minimal_client_info.user_agent is None
        assert minimal_client_info.ip_address is None
        assert minimal_client_info.connection_id is None
    
    def test_timestamp_utilities_integration(self):
        """Test timestamp utilities integration."""
        # Generate timestamp
        timestamp = get_current_timestamp()
        
        # Validate format
        assert timestamp is not None
        assert 'T' in timestamp  # ISO format
        
        # Parse timestamp
        from shared.utils import parse_timestamp
        parsed = parse_timestamp(timestamp)
        assert parsed is not None
        assert isinstance(parsed, datetime)
    
    def test_error_response_formatting(self):
        """Test error response formatting integration."""
        # Create error response
        error_response = format_error_response("TEST_ERROR", "Test error message")
        
        # Validate structure
        assert 'error' in error_response
        assert error_response['error']['code'] == "TEST_ERROR"
        assert error_response['error']['message'] == "Test error message"
        assert 'timestamp' in error_response['error']
    
    def test_response_metadata_creation(self):
        """Test response metadata creation integration."""
        session_id = generate_session_id()
        message_id = generate_message_id()
        
        metadata = create_response_metadata(
            session_id=session_id,
            message_id=message_id,
            query_type="general",
            response_time=150.5
        )
        
        # Validate metadata structure
        assert metadata['session_id'] == session_id
        assert metadata['message_id'] == message_id
        assert metadata['query_type'] == "general"
        assert metadata['response_time'] == 150.5
        assert 'timestamp' in metadata
    
    def test_exception_hierarchy_integration(self):
        """Test exception hierarchy integration."""
        # Test base ChatbotError
        base_error = ChatbotError("Base error message")
        assert str(base_error) == "Base error message"
        assert isinstance(base_error, Exception)
        
        # Test specific exception
        session_error = SessionNotFoundError("session-123")
        assert isinstance(session_error, ChatbotError)
        assert "session-123" in str(session_error)
    
    def test_data_model_integration(self):
        """Test data model integration."""
        from shared.models import QueryType
        
        # Test QueryType enum
        assert QueryType.GENERAL.value == "general"
        assert QueryType.RAG.value == "rag"
        assert QueryType.MCP_TOOL.value == "mcp_tool"
        
        # Test from_string method
        assert QueryType.from_string("general") == QueryType.GENERAL
        assert QueryType.from_string("rag") == QueryType.RAG
        assert QueryType.from_string("mcp_tool") == QueryType.MCP_TOOL
        
        # Test invalid query type
        with pytest.raises(ValueError):
            QueryType.from_string("invalid_type")


class TestComponentInteraction:
    """Test interaction between different components."""
    
    def test_session_models_integration(self):
        """Test session models integration."""
        from shared.session_models import Session, SessionRecord, SessionStatus
        
        # Create session
        session_id = generate_session_id()
        current_time = datetime.now(timezone.utc)
        
        session = Session(
            session_id=session_id,
            created_at=current_time,
            last_activity=current_time,
            status=SessionStatus.ACTIVE
        )
        
        # Validate session
        assert session.session_id == session_id
        assert session.status == SessionStatus.ACTIVE
        assert not session.is_expired(timeout_minutes=30)
        
        # Test session record conversion
        session_record = SessionRecord(
            session_id=session_id,
            created_at=current_time.isoformat(),
            last_activity=current_time.isoformat(),
            is_active=True,
            client_info={'user_agent': 'test'},
            metadata={}
        )
        
        # Convert to dict
        record_dict = session_record.to_dict()
        assert record_dict['session_id'] == session_id
        assert record_dict['is_active'] is True
    
    def test_analytics_data_structure(self):
        """Test analytics data structure integration."""
        from shared.analytics_tracker import AnalyticsRecord, EventType
        
        # Create analytics record
        record = AnalyticsRecord(
            date="2024-01-01",
            event_id=str(uuid.uuid4()),
            event_type=EventType.QUERY,
            session_id=generate_session_id(),
            details={'query_type': 'general', 'response_time': 150},
            timestamp=get_current_timestamp()
        )
        
        # Validate record
        assert record.date == "2024-01-01"
        assert record.event_type == EventType.QUERY
        assert 'query_type' in record.details
        
        # Convert to dict
        record_dict = record.to_dict()
        assert record_dict['event_type'] == "query"
        assert record_dict['details']['query_type'] == 'general'
    
    def test_conversation_data_structure(self):
        """Test conversation data structure integration."""
        from shared.conversation_logger import ConversationRecord
        
        # Create conversation record
        record = ConversationRecord(
            session_id=generate_session_id(),
            message_id=generate_message_id(),
            timestamp=get_current_timestamp(),
            message_type="user",
            content="Hello, chatbot!",
            query_type="general",
            sources=[],
            tools_used=[],
            response_time=100
        )
        
        # Validate record
        assert record.message_type == "user"
        assert record.content == "Hello, chatbot!"
        assert record.query_type == "general"
        assert record.response_time == 100
        
        # Convert to dict
        record_dict = record.to_dict()
        assert record_dict['message_type'] == "user"
        assert record_dict['content'] == "Hello, chatbot!"
    
    def test_error_handling_integration(self):
        """Test error handling integration across components."""
        from shared.exceptions import (
            StrandClientError, 
            McpHandlerError, 
            RagHandlerError,
            get_user_friendly_message
        )
        
        # Test different error types
        strand_error = StrandClientError("API error", "API_ERROR")
        mcp_error = McpHandlerError("Tool error", "TOOL_ERROR")
        rag_error = RagHandlerError("Search error", "SEARCH_ERROR")
        
        # Test user-friendly message generation
        friendly_message = get_user_friendly_message(strand_error)
        assert isinstance(friendly_message, str)
        assert len(friendly_message) > 0
        
        # Test error context creation
        from shared.exceptions import create_error_context
        
        context = create_error_context(
            error=strand_error,
            session_id=generate_session_id(),
            operation="generate_response"
        )
        
        assert 'error_type' in context
        assert 'session_id' in context
        assert 'operation' in context
        assert 'timestamp' in context


class TestConfigurationIntegration:
    """Test configuration and environment integration."""
    
    def test_retry_configuration_integration(self):
        """Test retry configuration integration."""
        from shared.retry_utils import RetryConfig, get_strand_retry_config
        
        # Test default retry config
        config = RetryConfig()
        assert config.max_attempts >= 1
        assert config.base_delay > 0
        assert config.max_delay > config.base_delay
        
        # Test strand-specific config
        strand_config = get_strand_retry_config()
        assert isinstance(strand_config, RetryConfig)
        assert strand_config.max_attempts > 0
    
    def test_logging_configuration_integration(self):
        """Test logging configuration integration."""
        from shared.analytics_tracker import configure_analytics_logging
        from shared.conversation_logger import configure_conversation_logging
        
        # Test analytics logging configuration
        configure_analytics_logging()
        
        # Test conversation logging configuration
        configure_conversation_logging(level="INFO")
        
        # Should not raise any exceptions
        assert True
    
    def test_utility_functions_integration(self):
        """Test utility functions integration."""
        from shared.utils import sanitize_input
        
        # Test input sanitization
        clean_input = sanitize_input("Hello\x00World\x01Test", max_length=50)
        assert "\x00" not in clean_input
        assert "\x01" not in clean_input
        assert "HelloWorldTest" == clean_input
        
        # Test length limiting
        long_input = "a" * 1000
        limited_input = sanitize_input(long_input, max_length=100)
        assert len(limited_input) == 100


class TestDataFlowIntegration:
    """Test data flow between components."""
    
    def test_session_to_analytics_flow(self):
        """Test data flow from session to analytics."""
        from shared.session_models import Session, SessionStatus
        from shared.analytics_tracker import AnalyticsRecord, EventType
        
        # Create session
        session_id = generate_session_id()
        session = Session(
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE
        )
        
        # Create analytics record from session
        analytics_record = AnalyticsRecord(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            event_id=str(uuid.uuid4()),
            event_type=EventType.SESSION_CREATED,
            session_id=session.session_id,
            details={'status': session.status.value},
            timestamp=get_current_timestamp()
        )
        
        # Validate data flow
        assert analytics_record.session_id == session.session_id
        assert analytics_record.event_type == EventType.SESSION_CREATED
        assert analytics_record.details['status'] == 'active'
    
    def test_message_to_conversation_flow(self):
        """Test data flow from message to conversation log."""
        from shared.conversation_logger import ConversationRecord
        
        # Simulate message processing
        session_id = generate_session_id()
        message_id = generate_message_id()
        user_message = "What is machine learning?"
        
        # Create user message record
        user_record = ConversationRecord(
            session_id=session_id,
            message_id=message_id,
            timestamp=get_current_timestamp(),
            message_type="user",
            content=user_message,
            query_type=None,  # Not determined yet
            sources=[],
            tools_used=[],
            response_time=None
        )
        
        # Create assistant response record
        assistant_record = ConversationRecord(
            session_id=session_id,
            message_id=generate_message_id(),
            timestamp=get_current_timestamp(),
            message_type="assistant",
            content="Machine learning is a subset of AI...",
            query_type="general",
            sources=[],
            tools_used=[],
            response_time=250
        )
        
        # Validate conversation flow
        assert user_record.session_id == assistant_record.session_id
        assert user_record.message_type == "user"
        assert assistant_record.message_type == "assistant"
        assert assistant_record.query_type == "general"
        assert assistant_record.response_time == 250


if __name__ == '__main__':
    pytest.main([__file__])