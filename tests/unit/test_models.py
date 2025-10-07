"""
Unit tests for shared data models.
"""

import pytest
from dataclasses import asdict

from shared.models import (
    QueryType,
    Session,
    SessionRecord,
    ConversationRecord
)


class TestQueryType:
    """Test cases for QueryType enum."""
    
    def test_query_type_values(self):
        """Test QueryType enum values."""
        assert QueryType.RAG.value == 'rag'
        assert QueryType.GENERAL.value == 'general'
        assert QueryType.MCP_TOOL.value == 'mcp_tool'
    
    def test_query_type_from_string(self):
        """Test creating QueryType from string values."""
        assert QueryType('rag') == QueryType.RAG
        assert QueryType('general') == QueryType.GENERAL
        assert QueryType('mcp_tool') == QueryType.MCP_TOOL
    
    def test_query_type_invalid_value(self):
        """Test QueryType with invalid value."""
        with pytest.raises(ValueError):
            QueryType('invalid_type')


class TestSession:
    """Test cases for Session dataclass."""
    
    def test_session_creation(self):
        """Test Session object creation."""
        session = Session(
            sessionId="test-session-123",
            createdAt="2024-01-01T00:00:00Z",
            lastActivity="2024-01-01T00:05:00Z",
            isActive=True,
            metadata={"key": "value"}
        )
        
        assert session.sessionId == "test-session-123"
        assert session.createdAt == "2024-01-01T00:00:00Z"
        assert session.lastActivity == "2024-01-01T00:05:00Z"
        assert session.isActive is True
        assert session.metadata == {"key": "value"}
    
    def test_session_without_metadata(self):
        """Test Session creation without metadata."""
        session = Session(
            sessionId="test-session-123",
            createdAt="2024-01-01T00:00:00Z",
            lastActivity="2024-01-01T00:05:00Z",
            isActive=True
        )
        
        assert session.metadata is None
    
    def test_session_to_dict(self):
        """Test Session conversion to dictionary."""
        session = Session(
            sessionId="test-session-123",
            createdAt="2024-01-01T00:00:00Z",
            lastActivity="2024-01-01T00:05:00Z",
            isActive=True,
            metadata={"key": "value"}
        )
        
        session_dict = asdict(session)
        
        assert session_dict['sessionId'] == "test-session-123"
        assert session_dict['createdAt'] == "2024-01-01T00:00:00Z"
        assert session_dict['lastActivity'] == "2024-01-01T00:05:00Z"
        assert session_dict['isActive'] is True
        assert session_dict['metadata'] == {"key": "value"}


class TestSessionRecord:
    """Test cases for SessionRecord dataclass."""
    
    def test_session_record_creation(self):
        """Test SessionRecord object creation."""
        record = SessionRecord(
            sessionId="test-session-123",
            createdAt="2024-01-01T00:00:00Z",
            lastActivity="2024-01-01T00:05:00Z",
            isActive=True,
            clientInfo={"userAgent": "test-browser", "ipAddress": "127.0.0.1"},
            ttl=1704067200
        )
        
        assert record.sessionId == "test-session-123"
        assert record.createdAt == "2024-01-01T00:00:00Z"
        assert record.lastActivity == "2024-01-01T00:05:00Z"
        assert record.isActive is True
        assert record.clientInfo == {"userAgent": "test-browser", "ipAddress": "127.0.0.1"}
        assert record.ttl == 1704067200
    
    def test_session_record_minimal(self):
        """Test SessionRecord creation with minimal fields."""
        record = SessionRecord(
            sessionId="test-session-123",
            createdAt="2024-01-01T00:00:00Z",
            lastActivity="2024-01-01T00:05:00Z",
            isActive=False
        )
        
        assert record.sessionId == "test-session-123"
        assert record.isActive is False
        assert record.clientInfo is None
        assert record.ttl is None
    
    def test_session_record_to_dict(self):
        """Test SessionRecord conversion to dictionary."""
        record = SessionRecord(
            sessionId="test-session-123",
            createdAt="2024-01-01T00:00:00Z",
            lastActivity="2024-01-01T00:05:00Z",
            isActive=True,
            clientInfo={"userAgent": "test-browser"},
            ttl=1704067200
        )
        
        record_dict = asdict(record)
        
        assert record_dict['sessionId'] == "test-session-123"
        assert record_dict['createdAt'] == "2024-01-01T00:00:00Z"
        assert record_dict['lastActivity'] == "2024-01-01T00:05:00Z"
        assert record_dict['isActive'] is True
        assert record_dict['clientInfo'] == {"userAgent": "test-browser"}
        assert record_dict['ttl'] == 1704067200


class TestConversationRecord:
    """Test cases for ConversationRecord dataclass."""
    
    def test_conversation_record_creation(self):
        """Test ConversationRecord object creation."""
        record = ConversationRecord(
            sessionId="test-session-123",
            messageId="msg-456",
            timestamp="2024-01-01T00:00:00Z",
            messageType="user",
            content="Hello, how are you?",
            queryType=QueryType.GENERAL,
            sources=["source1.pdf", "source2.pdf"],
            toolsUsed=["search_tool", "create_tool"],
            responseTime=150
        )
        
        assert record.sessionId == "test-session-123"
        assert record.messageId == "msg-456"
        assert record.timestamp == "2024-01-01T00:00:00Z"
        assert record.messageType == "user"
        assert record.content == "Hello, how are you?"
        assert record.queryType == QueryType.GENERAL
        assert record.sources == ["source1.pdf", "source2.pdf"]
        assert record.toolsUsed == ["search_tool", "create_tool"]
        assert record.responseTime == 150
    
    def test_conversation_record_minimal(self):
        """Test ConversationRecord creation with minimal fields."""
        record = ConversationRecord(
            sessionId="test-session-123",
            messageId="msg-456",
            timestamp="2024-01-01T00:00:00Z",
            messageType="assistant",
            content="Hello! I'm doing well, thank you."
        )
        
        assert record.sessionId == "test-session-123"
        assert record.messageId == "msg-456"
        assert record.messageType == "assistant"
        assert record.content == "Hello! I'm doing well, thank you."
        assert record.queryType is None
        assert record.sources is None
        assert record.toolsUsed is None
        assert record.responseTime is None
    
    def test_conversation_record_user_message(self):
        """Test ConversationRecord for user message."""
        record = ConversationRecord(
            sessionId="test-session-123",
            messageId="msg-456",
            timestamp="2024-01-01T00:00:00Z",
            messageType="user",
            content="What is artificial intelligence?"
        )
        
        assert record.messageType == "user"
        assert record.content == "What is artificial intelligence?"
        # User messages typically don't have queryType, sources, etc.
        assert record.queryType is None
        assert record.sources is None
        assert record.toolsUsed is None
        assert record.responseTime is None
    
    def test_conversation_record_assistant_message(self):
        """Test ConversationRecord for assistant message."""
        record = ConversationRecord(
            sessionId="test-session-123",
            messageId="msg-789",
            timestamp="2024-01-01T00:00:05Z",
            messageType="assistant",
            content="AI is a field of computer science...",
            queryType=QueryType.RAG,
            sources=["ai_guide.pdf"],
            responseTime=250
        )
        
        assert record.messageType == "assistant"
        assert record.queryType == QueryType.RAG
        assert record.sources == ["ai_guide.pdf"]
        assert record.responseTime == 250
    
    def test_conversation_record_to_dict(self):
        """Test ConversationRecord conversion to dictionary."""
        record = ConversationRecord(
            sessionId="test-session-123",
            messageId="msg-456",
            timestamp="2024-01-01T00:00:00Z",
            messageType="user",
            content="Hello!",
            queryType=QueryType.GENERAL
        )
        
        record_dict = asdict(record)
        
        assert record_dict['sessionId'] == "test-session-123"
        assert record_dict['messageId'] == "msg-456"
        assert record_dict['timestamp'] == "2024-01-01T00:00:00Z"
        assert record_dict['messageType'] == "user"
        assert record_dict['content'] == "Hello!"
        assert record_dict['queryType'] == QueryType.GENERAL
        assert record_dict['sources'] is None
        assert record_dict['toolsUsed'] is None
        assert record_dict['responseTime'] is None


if __name__ == "__main__":
    pytest.main([__file__])