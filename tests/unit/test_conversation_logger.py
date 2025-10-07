"""
Unit tests for the conversation logger module.

Tests conversation data storage, retrieval, and structured logging functionality
with proper mocking of DynamoDB operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from botocore.exceptions import ClientError

from shared.conversation_logger import ConversationLogger, configure_conversation_logging
from shared.models import ConversationRecord, QueryType
from shared.exceptions import DatabaseError


class TestConversationLogger:
    """Test cases for ConversationLogger class."""
    
    @pytest.fixture
    def mock_dynamodb_table(self):
        """Mock DynamoDB table for testing."""
        with patch('shared.conversation_logger.boto3') as mock_boto3:
            mock_resource = Mock()
            mock_table = Mock()
            mock_boto3.resource.return_value = mock_resource
            mock_resource.Table.return_value = mock_table
            yield mock_table
    
    @pytest.fixture
    def conversation_logger(self, mock_dynamodb_table):
        """Create ConversationLogger instance for testing."""
        return ConversationLogger('test-conversations-table', 'us-east-1')
    
    def test_init_conversation_logger(self, mock_dynamodb_table):
        """Test ConversationLogger initialization."""
        logger = ConversationLogger('test-table', 'us-west-2')
        
        assert logger.table_name == 'test-table'
        assert logger.region_name == 'us-west-2'
        assert logger.table is not None
    
    def test_log_user_message_success(self, conversation_logger, mock_dynamodb_table):
        """Test successful user message logging."""
        session_id = 'test-session-123'
        content = 'Hello, how are you?'
        metadata = {'client_ip': '192.168.1.1'}
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.conversation_logger.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = 'test-message-id'
            mock_uuid.return_value.__str__ = lambda x: 'test-message-id'
            
            message_id = conversation_logger.log_user_message(
                session_id=session_id,
                content=content,
                metadata=metadata
            )
        
        assert message_id == 'test-message-id'
        mock_dynamodb_table.put_item.assert_called_once()
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['sessionId'] == session_id
        assert item['messageId'] == 'test-message-id'
        assert item['content'] == content
        assert item['messageType'] == 'user'
        assert item['metadata'] == metadata
        assert 'timestamp' in item
    
    def test_log_user_message_with_provided_id(self, conversation_logger, mock_dynamodb_table):
        """Test user message logging with provided message ID."""
        session_id = 'test-session-123'
        content = 'Hello, how are you?'
        message_id = 'custom-message-id'
        
        mock_dynamodb_table.put_item.return_value = {}
        
        result_id = conversation_logger.log_user_message(
            session_id=session_id,
            content=content,
            message_id=message_id
        )
        
        assert result_id == message_id
        mock_dynamodb_table.put_item.assert_called_once()
    
    def test_log_user_message_database_error(self, conversation_logger, mock_dynamodb_table):
        """Test user message logging with database error."""
        session_id = 'test-session-123'
        content = 'Hello, how are you?'
        
        mock_dynamodb_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid item'}},
            'PutItem'
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            conversation_logger.log_user_message(session_id, content)
        
        assert 'Failed to log user message' in str(exc_info.value)
    
    def test_log_assistant_response_success(self, conversation_logger, mock_dynamodb_table):
        """Test successful assistant response logging."""
        session_id = 'test-session-123'
        content = 'I am doing well, thank you!'
        query_type = QueryType.GENERAL
        response_time_ms = 1500
        sources = ['doc1.pdf', 'doc2.pdf']
        tools_used = ['search_tool', 'summarize_tool']
        metadata = {'model_version': 'claude-3.5-sonnet'}
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.conversation_logger.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = 'test-response-id'
            mock_uuid.return_value.__str__ = lambda x: 'test-response-id'
            
            message_id = conversation_logger.log_assistant_response(
                session_id=session_id,
                content=content,
                query_type=query_type,
                response_time_ms=response_time_ms,
                sources=sources,
                tools_used=tools_used,
                metadata=metadata
            )
        
        assert message_id == 'test-response-id'
        mock_dynamodb_table.put_item.assert_called_once()
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['sessionId'] == session_id
        assert item['messageId'] == 'test-response-id'
        assert item['content'] == content
        assert item['messageType'] == 'assistant'
        assert item['queryType'] == query_type.value
        assert item['sources'] == sources
        assert item['toolsUsed'] == tools_used
        assert item['responseTime'] == response_time_ms
        assert item['metadata'] == metadata
        assert 'timestamp' in item
    
    def test_log_assistant_response_minimal(self, conversation_logger, mock_dynamodb_table):
        """Test assistant response logging with minimal parameters."""
        session_id = 'test-session-123'
        content = 'Simple response'
        query_type = QueryType.GENERAL
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.conversation_logger.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-response-id'
            
            message_id = conversation_logger.log_assistant_response(
                session_id=session_id,
                content=content,
                query_type=query_type
            )
        
        assert message_id == 'test-response-id'
        mock_dynamodb_table.put_item.assert_called_once()
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['sessionId'] == session_id
        assert item['content'] == content
        assert item['messageType'] == 'assistant'
        assert item['queryType'] == query_type.value
        assert 'sources' not in item
        assert 'toolsUsed' not in item
        assert 'responseTime' not in item
    
    def test_get_conversation_history_success(self, conversation_logger, mock_dynamodb_table):
        """Test successful conversation history retrieval."""
        session_id = 'test-session-123'
        
        mock_items = [
            {
                'sessionId': session_id,
                'messageId': 'msg-2',
                'timestamp': '2024-01-01T12:01:00Z',
                'messageType': 'assistant',
                'content': 'Response 2',
                'queryType': 'general'
            },
            {
                'sessionId': session_id,
                'messageId': 'msg-1',
                'timestamp': '2024-01-01T12:00:00Z',
                'messageType': 'user',
                'content': 'Question 1'
            }
        ]
        
        mock_dynamodb_table.query.return_value = {'Items': mock_items}
        
        conversations = conversation_logger.get_conversation_history(session_id, limit=10)
        
        assert len(conversations) == 2
        assert conversations[0].messageId == 'msg-2'
        assert conversations[0].messageType == 'assistant'
        assert conversations[0].queryType == QueryType.GENERAL
        assert conversations[1].messageId == 'msg-1'
        assert conversations[1].messageType == 'user'
        assert conversations[1].queryType is None
        
        # Verify query parameters
        mock_dynamodb_table.query.assert_called_once()
        call_args = mock_dynamodb_table.query.call_args[1]
        assert call_args['Limit'] == 10
        assert call_args['ScanIndexForward'] is False
    
    def test_get_conversation_history_with_pagination(self, conversation_logger, mock_dynamodb_table):
        """Test conversation history retrieval with pagination."""
        session_id = 'test-session-123'
        last_message_id = 'last-msg-id'
        
        mock_dynamodb_table.query.return_value = {'Items': []}
        
        conversation_logger.get_conversation_history(
            session_id=session_id,
            limit=20,
            last_message_id=last_message_id
        )
        
        # Verify pagination parameters
        call_args = mock_dynamodb_table.query.call_args[1]
        assert call_args['ExclusiveStartKey'] == {
            'sessionId': session_id,
            'messageId': last_message_id
        }
    
    def test_get_conversation_history_database_error(self, conversation_logger, mock_dynamodb_table):
        """Test conversation history retrieval with database error."""
        session_id = 'test-session-123'
        
        mock_dynamodb_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'Query'
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            conversation_logger.get_conversation_history(session_id)
        
        assert 'Failed to retrieve conversation history' in str(exc_info.value)
    
    def test_delete_conversation_history_success(self, conversation_logger, mock_dynamodb_table):
        """Test successful conversation history deletion."""
        session_id = 'test-session-123'
        
        mock_items = [
            {'messageId': 'msg-1'},
            {'messageId': 'msg-2'},
            {'messageId': 'msg-3'}
        ]
        
        mock_dynamodb_table.query.return_value = {'Items': mock_items}
        mock_dynamodb_table.delete_item.return_value = {}
        
        deleted_count = conversation_logger.delete_conversation_history(session_id)
        
        assert deleted_count == 3
        assert mock_dynamodb_table.delete_item.call_count == 3
        
        # Verify delete calls
        delete_calls = mock_dynamodb_table.delete_item.call_args_list
        for i, call in enumerate(delete_calls):
            expected_key = {
                'sessionId': session_id,
                'messageId': f'msg-{i+1}'
            }
            assert call[1]['Key'] == expected_key
    
    def test_delete_conversation_history_database_error(self, conversation_logger, mock_dynamodb_table):
        """Test conversation history deletion with database error."""
        session_id = 'test-session-123'
        
        mock_dynamodb_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'Query'
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            conversation_logger.delete_conversation_history(session_id)
        
        assert 'Failed to delete conversation history' in str(exc_info.value)
    
    def test_generate_message_id(self, conversation_logger):
        """Test message ID generation."""
        with patch('shared.conversation_logger.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-uuid-123'
            
            message_id = conversation_logger._generate_message_id()
            
            assert message_id == 'test-uuid-123'
            mock_uuid.assert_called_once()
    
    def test_conversation_record_to_item_full(self, conversation_logger):
        """Test conversion of ConversationRecord to DynamoDB item with all fields."""
        record = ConversationRecord(
            sessionId='test-session',
            messageId='test-message',
            timestamp='2024-01-01T12:00:00Z',
            messageType='assistant',
            content='Test response',
            queryType=QueryType.RAG,
            sources=['doc1.pdf'],
            toolsUsed=['search_tool'],
            responseTime=1000
        )
        
        item = conversation_logger._conversation_record_to_item(record)
        
        expected_item = {
            'sessionId': 'test-session',
            'messageId': 'test-message',
            'timestamp': '2024-01-01T12:00:00Z',
            'messageType': 'assistant',
            'content': 'Test response',
            'queryType': 'rag',
            'sources': ['doc1.pdf'],
            'toolsUsed': ['search_tool'],
            'responseTime': 1000
        }
        
        assert item == expected_item
    
    def test_conversation_record_to_item_minimal(self, conversation_logger):
        """Test conversion of ConversationRecord to DynamoDB item with minimal fields."""
        record = ConversationRecord(
            sessionId='test-session',
            messageId='test-message',
            timestamp='2024-01-01T12:00:00Z',
            messageType='user',
            content='Test question'
        )
        
        item = conversation_logger._conversation_record_to_item(record)
        
        expected_item = {
            'sessionId': 'test-session',
            'messageId': 'test-message',
            'timestamp': '2024-01-01T12:00:00Z',
            'messageType': 'user',
            'content': 'Test question'
        }
        
        assert item == expected_item
    
    def test_item_to_conversation_record_full(self, conversation_logger):
        """Test conversion of DynamoDB item to ConversationRecord with all fields."""
        item = {
            'sessionId': 'test-session',
            'messageId': 'test-message',
            'timestamp': '2024-01-01T12:00:00Z',
            'messageType': 'assistant',
            'content': 'Test response',
            'queryType': 'mcp_tool',
            'sources': ['doc1.pdf'],
            'toolsUsed': ['search_tool'],
            'responseTime': 1000
        }
        
        record = conversation_logger._item_to_conversation_record(item)
        
        assert record.sessionId == 'test-session'
        assert record.messageId == 'test-message'
        assert record.timestamp == '2024-01-01T12:00:00Z'
        assert record.messageType == 'assistant'
        assert record.content == 'Test response'
        assert record.queryType == QueryType.MCP_TOOL
        assert record.sources == ['doc1.pdf']
        assert record.toolsUsed == ['search_tool']
        assert record.responseTime == 1000
    
    def test_item_to_conversation_record_minimal(self, conversation_logger):
        """Test conversion of DynamoDB item to ConversationRecord with minimal fields."""
        item = {
            'sessionId': 'test-session',
            'messageId': 'test-message',
            'timestamp': '2024-01-01T12:00:00Z',
            'messageType': 'user',
            'content': 'Test question'
        }
        
        record = conversation_logger._item_to_conversation_record(item)
        
        assert record.sessionId == 'test-session'
        assert record.messageId == 'test-message'
        assert record.timestamp == '2024-01-01T12:00:00Z'
        assert record.messageType == 'user'
        assert record.content == 'Test question'
        assert record.queryType is None
        assert record.sources is None
        assert record.toolsUsed is None
        assert record.responseTime is None


class TestConfigureConversationLogging:
    """Test cases for logging configuration."""
    
    @patch('shared.conversation_logger.logging.basicConfig')
    @patch('shared.conversation_logger.boto3.set_stream_logger')
    def test_configure_conversation_logging_default(self, mock_set_stream_logger, mock_basic_config):
        """Test conversation logging configuration with default level."""
        configure_conversation_logging()
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args[1]
        assert call_args['level'] == 20  # INFO level
        
        # Verify boto3 logging is configured
        assert mock_set_stream_logger.call_count == 2
    
    @patch('shared.conversation_logger.logging.basicConfig')
    @patch('shared.conversation_logger.boto3.set_stream_logger')
    def test_configure_conversation_logging_custom_level(self, mock_set_stream_logger, mock_basic_config):
        """Test conversation logging configuration with custom level."""
        configure_conversation_logging('DEBUG')
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args[1]
        assert call_args['level'] == 10  # DEBUG level


if __name__ == '__main__':
    pytest.main([__file__])