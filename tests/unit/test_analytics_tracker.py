"""
Unit tests for the analytics tracker module.

Tests analytics data collection, tool usage tracking, query type analysis,
and statistics generation with proper mocking of DynamoDB operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, date
from botocore.exceptions import ClientError

from shared.analytics_tracker import (
    AnalyticsTracker, EventType, configure_analytics_logging
)
from shared.models import AnalyticsRecord, QueryType
from shared.exceptions import DatabaseError


class TestAnalyticsTracker:
    """Test cases for AnalyticsTracker class."""
    
    @pytest.fixture
    def mock_dynamodb_table(self):
        """Mock DynamoDB table for testing."""
        with patch('shared.analytics_tracker.boto3') as mock_boto3:
            mock_resource = Mock()
            mock_table = Mock()
            mock_boto3.resource.return_value = mock_resource
            mock_resource.Table.return_value = mock_table
            yield mock_table
    
    @pytest.fixture
    def analytics_tracker(self, mock_dynamodb_table):
        """Create AnalyticsTracker instance for testing."""
        return AnalyticsTracker('test-analytics-table', 'us-east-1')
    
    def test_init_analytics_tracker(self, mock_dynamodb_table):
        """Test AnalyticsTracker initialization."""
        tracker = AnalyticsTracker('test-table', 'us-west-2')
        
        assert tracker.table_name == 'test-table'
        assert tracker.region_name == 'us-west-2'
        assert tracker.table is not None
    
    def test_track_query_event_success(self, analytics_tracker, mock_dynamodb_table):
        """Test successful query event tracking."""
        session_id = 'test-session-123'
        query_type = QueryType.RAG
        response_time_ms = 1500
        metadata = {'model_version': 'claude-3.5-sonnet'}
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-event-id'
            
            event_id = analytics_tracker.track_query_event(
                session_id=session_id,
                query_type=query_type,
                response_time_ms=response_time_ms,
                success=True,
                metadata=metadata
            )
        
        assert event_id == 'test-event-id'
        mock_dynamodb_table.put_item.assert_called_once()
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['eventType'] == EventType.QUERY.value
        assert item['sessionId'] == session_id
        assert item['details']['query_type'] == query_type.value
        assert item['details']['success'] is True
        assert item['details']['response_time_ms'] == response_time_ms
        assert item['details']['model_version'] == 'claude-3.5-sonnet'
        assert 'timestamp' in item
        assert 'date' in item
    
    def test_track_query_event_with_error(self, analytics_tracker, mock_dynamodb_table):
        """Test query event tracking with error."""
        session_id = 'test-session-123'
        query_type = QueryType.GENERAL
        error_message = 'Model unavailable'
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-event-id'
            
            event_id = analytics_tracker.track_query_event(
                session_id=session_id,
                query_type=query_type,
                success=False,
                error_message=error_message
            )
        
        assert event_id == 'test-event-id'
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['details']['success'] is False
        assert item['details']['error_message'] == error_message
    
    def test_track_tool_usage_success(self, analytics_tracker, mock_dynamodb_table):
        """Test successful tool usage tracking."""
        session_id = 'test-session-123'
        tool_name = 'search_documents'
        tool_parameters = {'query': 'test query', 'limit': 5}
        execution_time_ms = 800
        result_summary = 'Found 3 relevant documents'
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-tool-event-id'
            
            event_id = analytics_tracker.track_tool_usage(
                session_id=session_id,
                tool_name=tool_name,
                tool_parameters=tool_parameters,
                execution_time_ms=execution_time_ms,
                success=True,
                result_summary=result_summary
            )
        
        assert event_id == 'test-tool-event-id'
        mock_dynamodb_table.put_item.assert_called_once()
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['eventType'] == EventType.TOOL_USAGE.value
        assert item['sessionId'] == session_id
        assert item['details']['tool_name'] == tool_name
        assert item['details']['tool_parameters'] == tool_parameters
        assert item['details']['execution_time_ms'] == execution_time_ms
        assert item['details']['success'] is True
        assert item['details']['result_summary'] == result_summary
    
    def test_track_tool_usage_with_error(self, analytics_tracker, mock_dynamodb_table):
        """Test tool usage tracking with error."""
        session_id = 'test-session-123'
        tool_name = 'create_record'
        error_message = 'Validation failed'
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-tool-error-id'
            
            event_id = analytics_tracker.track_tool_usage(
                session_id=session_id,
                tool_name=tool_name,
                success=False,
                error_message=error_message
            )
        
        assert event_id == 'test-tool-error-id'
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['details']['success'] is False
        assert item['details']['error_message'] == error_message
    
    def test_track_session_created_event(self, analytics_tracker, mock_dynamodb_table):
        """Test session created event tracking."""
        session_id = 'test-session-123'
        client_info = {'user_agent': 'Mozilla/5.0', 'ip_address': '192.168.1.1'}
        metadata = {'connection_type': 'websocket'}
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-session-event-id'
            
            event_id = analytics_tracker.track_session_event(
                session_id=session_id,
                event_type=EventType.SESSION_CREATED,
                client_info=client_info,
                metadata=metadata
            )
        
        assert event_id == 'test-session-event-id'
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['eventType'] == EventType.SESSION_CREATED.value
        assert item['details']['client_info'] == client_info
        assert item['details']['connection_type'] == 'websocket'
    
    def test_track_session_closed_event(self, analytics_tracker, mock_dynamodb_table):
        """Test session closed event tracking."""
        session_id = 'test-session-123'
        session_duration_ms = 300000  # 5 minutes
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-session-close-id'
            
            event_id = analytics_tracker.track_session_event(
                session_id=session_id,
                event_type=EventType.SESSION_CLOSED,
                session_duration_ms=session_duration_ms
            )
        
        assert event_id == 'test-session-close-id'
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['eventType'] == EventType.SESSION_CLOSED.value
        assert item['details']['session_duration_ms'] == session_duration_ms
    
    def test_track_session_event_invalid_type(self, analytics_tracker):
        """Test session event tracking with invalid event type."""
        session_id = 'test-session-123'
        
        with pytest.raises(ValueError) as exc_info:
            analytics_tracker.track_session_event(
                session_id=session_id,
                event_type=EventType.QUERY  # Invalid for session events
            )
        
        assert 'Invalid session event type' in str(exc_info.value)
    
    def test_track_error_event(self, analytics_tracker, mock_dynamodb_table):
        """Test error event tracking."""
        session_id = 'test-session-123'
        error_type = 'ValidationError'
        error_message = 'Invalid input parameters'
        stack_trace = 'Traceback (most recent call last)...'
        context = {'function': 'process_query', 'input_length': 150}
        
        mock_dynamodb_table.put_item.return_value = {}
        
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-error-event-id'
            
            event_id = analytics_tracker.track_error_event(
                session_id=session_id,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                context=context
            )
        
        assert event_id == 'test-error-event-id'
        
        # Verify the item structure
        call_args = mock_dynamodb_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['eventType'] == EventType.ERROR_OCCURRED.value
        assert item['details']['error_type'] == error_type
        assert item['details']['error_message'] == error_message
        assert item['details']['stack_trace'] == stack_trace
        assert item['details']['context'] == context
    
    def test_get_analytics_by_date_success(self, analytics_tracker, mock_dynamodb_table):
        """Test successful analytics retrieval by date."""
        target_date = '2024-01-01'
        
        mock_items = [
            {
                'date': '2024-01-01',
                'eventId': 'event-1',
                'eventType': 'query',
                'sessionId': 'session-1',
                'details': {'query_type': 'rag'},
                'timestamp': '2024-01-01T12:00:00Z'
            },
            {
                'date': '2024-01-01',
                'eventId': 'event-2',
                'eventType': 'tool_usage',
                'sessionId': 'session-1',
                'details': {'tool_name': 'search_documents'},
                'timestamp': '2024-01-01T12:01:00Z'
            }
        ]
        
        mock_dynamodb_table.query.return_value = {'Items': mock_items}
        
        records = analytics_tracker.get_analytics_by_date(target_date, limit=50)
        
        assert len(records) == 2
        assert records[0].eventId == 'event-1'
        assert records[0].eventType == 'query'
        assert records[1].eventId == 'event-2'
        assert records[1].eventType == 'tool_usage'
        
        # Verify query parameters
        mock_dynamodb_table.query.assert_called_once()
        call_args = mock_dynamodb_table.query.call_args[1]
        assert call_args['Limit'] == 50
        assert call_args['ScanIndexForward'] is False
    
    def test_get_analytics_by_date_with_filter(self, analytics_tracker, mock_dynamodb_table):
        """Test analytics retrieval by date with event type filter."""
        target_date = date(2024, 1, 1)
        event_type = EventType.TOOL_USAGE
        
        mock_dynamodb_table.query.return_value = {'Items': []}
        
        analytics_tracker.get_analytics_by_date(target_date, event_type=event_type)
        
        # Verify filter parameters
        call_args = mock_dynamodb_table.query.call_args[1]
        assert 'FilterExpression' in call_args
        assert call_args['ExpressionAttributeValues'][':event_type'] == event_type.value
    
    def test_get_analytics_by_date_database_error(self, analytics_tracker, mock_dynamodb_table):
        """Test analytics retrieval with database error."""
        target_date = '2024-01-01'
        
        mock_dynamodb_table.query.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'Query'
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            analytics_tracker.get_analytics_by_date(target_date)
        
        assert 'Failed to retrieve analytics by date' in str(exc_info.value)
    
    def test_get_tool_usage_stats_success(self, analytics_tracker, mock_dynamodb_table):
        """Test successful tool usage statistics calculation."""
        start_date = '2024-01-01'
        end_date = '2024-01-31'
        
        mock_items = [
            {
                'date': '2024-01-01',
                'eventId': 'event-1',
                'eventType': 'tool_usage',
                'sessionId': 'session-1',
                'details': {
                    'tool_name': 'search_documents',
                    'success': True,
                    'execution_time_ms': 800
                },
                'timestamp': '2024-01-01T12:00:00Z'
            },
            {
                'date': '2024-01-02',
                'eventId': 'event-2',
                'eventType': 'tool_usage',
                'sessionId': 'session-2',
                'details': {
                    'tool_name': 'search_documents',
                    'success': False,
                    'execution_time_ms': 1200
                },
                'timestamp': '2024-01-02T12:00:00Z'
            },
            {
                'date': '2024-01-03',
                'eventId': 'event-3',
                'eventType': 'tool_usage',
                'sessionId': 'session-3',
                'details': {
                    'tool_name': 'create_record',
                    'success': True,
                    'execution_time_ms': 500
                },
                'timestamp': '2024-01-03T12:00:00Z'
            }
        ]
        
        mock_dynamodb_table.scan.return_value = {'Items': mock_items}
        
        stats = analytics_tracker.get_tool_usage_stats(start_date, end_date)
        
        # Verify summary statistics
        assert stats['summary']['total_tool_usage'] == 3
        assert stats['summary']['successful_usage'] == 2
        assert stats['summary']['failed_usage'] == 1
        assert stats['summary']['success_rate'] == 2/3
        assert stats['summary']['avg_execution_time_ms'] == (800 + 1200 + 500) / 3
        
        # Verify tool breakdown
        assert 'search_documents' in stats['tool_breakdown']
        assert 'create_record' in stats['tool_breakdown']
        
        search_stats = stats['tool_breakdown']['search_documents']
        assert search_stats['total_usage'] == 2
        assert search_stats['successful_usage'] == 1
        assert search_stats['failed_usage'] == 1
        assert search_stats['avg_execution_time_ms'] == (800 + 1200) / 2
        
        create_stats = stats['tool_breakdown']['create_record']
        assert create_stats['total_usage'] == 1
        assert create_stats['successful_usage'] == 1
        assert create_stats['failed_usage'] == 0
        assert create_stats['avg_execution_time_ms'] == 500
    
    def test_get_tool_usage_stats_with_date_objects(self, analytics_tracker, mock_dynamodb_table):
        """Test tool usage statistics with date objects."""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)
        
        mock_dynamodb_table.scan.return_value = {'Items': []}
        
        stats = analytics_tracker.get_tool_usage_stats(start_date, end_date)
        
        assert stats['date_range']['start_date'] == '2024-01-01'
        assert stats['date_range']['end_date'] == '2024-01-31'
    
    def test_get_query_type_stats_success(self, analytics_tracker, mock_dynamodb_table):
        """Test successful query type statistics calculation."""
        start_date = '2024-01-01'
        end_date = '2024-01-31'
        
        mock_items = [
            {
                'date': '2024-01-01',
                'eventId': 'event-1',
                'eventType': 'query',
                'sessionId': 'session-1',
                'details': {
                    'query_type': 'rag',
                    'success': True,
                    'response_time_ms': 1500
                },
                'timestamp': '2024-01-01T12:00:00Z'
            },
            {
                'date': '2024-01-02',
                'eventId': 'event-2',
                'eventType': 'query',
                'sessionId': 'session-2',
                'details': {
                    'query_type': 'general',
                    'success': True,
                    'response_time_ms': 800
                },
                'timestamp': '2024-01-02T12:00:00Z'
            },
            {
                'date': '2024-01-03',
                'eventId': 'event-3',
                'eventType': 'query',
                'sessionId': 'session-3',
                'details': {
                    'query_type': 'rag',
                    'success': False,
                    'response_time_ms': 2000
                },
                'timestamp': '2024-01-03T12:00:00Z'
            }
        ]
        
        mock_dynamodb_table.scan.return_value = {'Items': mock_items}
        
        stats = analytics_tracker.get_query_type_stats(start_date, end_date)
        
        # Verify summary statistics
        assert stats['summary']['total_queries'] == 3
        assert stats['summary']['successful_queries'] == 2
        assert stats['summary']['failed_queries'] == 1
        assert stats['summary']['success_rate'] == 2/3
        assert stats['summary']['avg_response_time_ms'] == (1500 + 800 + 2000) / 3
        
        # Verify query type breakdown
        assert 'rag' in stats['query_type_breakdown']
        assert 'general' in stats['query_type_breakdown']
        
        rag_stats = stats['query_type_breakdown']['rag']
        assert rag_stats['total_queries'] == 2
        assert rag_stats['successful_queries'] == 1
        assert rag_stats['failed_queries'] == 1
        assert rag_stats['avg_response_time_ms'] == (1500 + 2000) / 2
        
        general_stats = stats['query_type_breakdown']['general']
        assert general_stats['total_queries'] == 1
        assert general_stats['successful_queries'] == 1
        assert general_stats['failed_queries'] == 0
        assert general_stats['avg_response_time_ms'] == 800
    
    def test_track_event_database_error(self, analytics_tracker, mock_dynamodb_table):
        """Test event tracking with database error."""
        session_id = 'test-session-123'
        query_type = QueryType.GENERAL
        
        mock_dynamodb_table.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid item'}},
            'PutItem'
        )
        
        with pytest.raises(DatabaseError) as exc_info:
            analytics_tracker.track_query_event(session_id, query_type)
        
        assert 'Failed to track analytics event' in str(exc_info.value)
    
    def test_generate_event_id(self, analytics_tracker):
        """Test event ID generation."""
        with patch('shared.analytics_tracker.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = lambda self: 'test-event-uuid'
            
            event_id = analytics_tracker._generate_event_id()
            
            assert event_id == 'test-event-uuid'
            mock_uuid.assert_called_once()
    
    def test_analytics_record_to_item(self, analytics_tracker):
        """Test conversion of AnalyticsRecord to DynamoDB item."""
        record = AnalyticsRecord(
            date='2024-01-01',
            eventId='test-event-id',
            eventType='query',
            sessionId='test-session',
            details={'query_type': 'rag', 'success': True},
            timestamp='2024-01-01T12:00:00Z'
        )
        
        item = analytics_tracker._analytics_record_to_item(record)
        
        expected_item = {
            'date': '2024-01-01',
            'eventId': 'test-event-id',
            'eventType': 'query',
            'sessionId': 'test-session',
            'details': {'query_type': 'rag', 'success': True},
            'timestamp': '2024-01-01T12:00:00Z'
        }
        
        assert item == expected_item
    
    def test_item_to_analytics_record(self, analytics_tracker):
        """Test conversion of DynamoDB item to AnalyticsRecord."""
        item = {
            'date': '2024-01-01',
            'eventId': 'test-event-id',
            'eventType': 'tool_usage',
            'sessionId': 'test-session',
            'details': {'tool_name': 'search_documents', 'success': True},
            'timestamp': '2024-01-01T12:00:00Z'
        }
        
        record = analytics_tracker._item_to_analytics_record(item)
        
        assert record.date == '2024-01-01'
        assert record.eventId == 'test-event-id'
        assert record.eventType == 'tool_usage'
        assert record.sessionId == 'test-session'
        assert record.details == {'tool_name': 'search_documents', 'success': True}
        assert record.timestamp == '2024-01-01T12:00:00Z'


class TestEventType:
    """Test cases for EventType enum."""
    
    def test_event_type_values(self):
        """Test EventType enum values."""
        assert EventType.QUERY.value == 'query'
        assert EventType.TOOL_USAGE.value == 'tool_usage'
        assert EventType.SESSION_CREATED.value == 'session_created'
        assert EventType.SESSION_CLOSED.value == 'session_closed'
        assert EventType.ERROR_OCCURRED.value == 'error_occurred'
        assert EventType.RESPONSE_GENERATED.value == 'response_generated'


class TestConfigureAnalyticsLogging:
    """Test cases for analytics logging configuration."""
    
    @patch('shared.analytics_tracker.logging.basicConfig')
    @patch('shared.analytics_tracker.boto3.set_stream_logger')
    def test_configure_analytics_logging_default(self, mock_set_stream_logger, mock_basic_config):
        """Test analytics logging configuration with default level."""
        configure_analytics_logging()
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args[1]
        assert call_args['level'] == 20  # INFO level
        
        # Verify boto3 logging is configured
        assert mock_set_stream_logger.call_count == 2
    
    @patch('shared.analytics_tracker.logging.basicConfig')
    @patch('shared.analytics_tracker.boto3.set_stream_logger')
    def test_configure_analytics_logging_custom_level(self, mock_set_stream_logger, mock_basic_config):
        """Test analytics logging configuration with custom level."""
        configure_analytics_logging('DEBUG')
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args[1]
        assert call_args['level'] == 10  # DEBUG level


if __name__ == '__main__':
    pytest.main([__file__])