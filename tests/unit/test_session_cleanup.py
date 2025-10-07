"""
Unit tests for session cleanup Lambda function.

This module provides comprehensive tests for the session cleanup functionality
including handler logic, error scenarios, and CloudWatch integration.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from moto import mock_aws
import boto3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../lambda/session_cleanup'))

import sys
import os
import importlib.util

# Load the session cleanup handler module directly
session_cleanup_handler_path = os.path.join(os.path.dirname(__file__), '../../lambda/session_cleanup/handler.py')
spec = importlib.util.spec_from_file_location("session_cleanup_handler", session_cleanup_handler_path)
session_cleanup_handler = importlib.util.module_from_spec(spec)

# Add shared modules to path for the handler to import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

spec.loader.exec_module(session_cleanup_handler)

SessionCleanupHandler = session_cleanup_handler.SessionCleanupHandler
SessionCleanupError = session_cleanup_handler.SessionCleanupError
lambda_handler = session_cleanup_handler.lambda_handler


class TestSessionCleanupHandler:
    """Test cases for SessionCleanupHandler class."""
    
    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table fixture."""
        table = Mock()
        table.scan.return_value = {'Items': []}
        
        # Mock batch_writer context manager
        mock_batch_writer = Mock()
        table.batch_writer.return_value = mock_batch_writer
        mock_batch_writer.__enter__ = Mock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = Mock(return_value=None)
        
        return table
    
    @pytest.fixture
    def mock_cloudwatch(self):
        """Mock CloudWatch client fixture."""
        return Mock()
    
    @pytest.fixture
    def cleanup_handler(self, mock_table, mock_cloudwatch):
        """SessionCleanupHandler fixture with mocked dependencies."""
        with patch('handler.boto3') as mock_boto3:
            mock_dynamodb = Mock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = mock_cloudwatch
            
            handler = SessionCleanupHandler(
                table_name='test-sessions',
                region_name='us-east-1',
                session_timeout_minutes=30,
                dry_run=False
            )
            handler.table = mock_table
            handler.cloudwatch = mock_cloudwatch
            return handler
    
    def test_init_success(self):
        """Test successful initialization of SessionCleanupHandler."""
        with patch('handler.boto3') as mock_boto3:
            mock_dynamodb = Mock()
            mock_cloudwatch = Mock()
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = mock_cloudwatch
            
            handler = SessionCleanupHandler(
                table_name='test-sessions',
                region_name='us-west-2',
                session_timeout_minutes=60,
                dry_run=True
            )
            
            assert handler.table_name == 'test-sessions'
            assert handler.region_name == 'us-west-2'
            assert handler.session_timeout_minutes == 60
            assert handler.dry_run is True
            
            mock_boto3.resource.assert_called_once_with('dynamodb', region_name='us-west-2')
            mock_boto3.client.assert_called_once_with('cloudwatch', region_name='us-west-2')
    
    def test_init_failure(self):
        """Test initialization failure handling."""
        with patch('handler.boto3') as mock_boto3:
            mock_boto3.resource.side_effect = Exception("AWS connection failed")
            
            with pytest.raises(SessionCleanupError) as exc_info:
                SessionCleanupHandler('test-sessions')
            
            assert "AWS client initialization failed" in str(exc_info.value)
    
    def test_cleanup_no_sessions(self, cleanup_handler, mock_table):
        """Test cleanup when no sessions need to be cleaned up."""
        mock_table.scan.return_value = {'Items': []}
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 0
        assert result['message'] == 'No sessions required cleanup'
        assert 'cutoff_timestamp' in result
    
    def test_cleanup_expired_sessions(self, cleanup_handler, mock_table, mock_cloudwatch):
        """Test cleanup of expired sessions."""
        # Mock expired sessions
        expired_sessions = [
            {
                'session_id': 'session-1',
                'last_activity': '2024-01-01T10:00:00Z',
                'created_at': '2024-01-01T09:00:00Z'
            },
            {
                'session_id': 'session-2',
                'last_activity': '2024-01-01T11:00:00Z',
                'created_at': '2024-01-01T10:00:00Z'
            }
        ]
        
        # First call returns expired sessions, second call returns inactive sessions (empty)
        mock_table.scan.side_effect = [
            {'Items': expired_sessions},
            {'Items': []}
        ]
        
        # Mock batch writer
        mock_batch_writer = Mock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 2
        assert result['sessions_identified'] == 2
        assert result['dry_run'] is False
        
        # Verify batch delete was called for each session
        assert mock_batch_writer.delete_item.call_count == 2
        mock_batch_writer.delete_item.assert_any_call(Key={'session_id': 'session-1'})
        mock_batch_writer.delete_item.assert_any_call(Key={'session_id': 'session-2'})
        
        # Verify CloudWatch metrics were sent
        mock_cloudwatch.put_metric_data.assert_called_once()
    
    def test_cleanup_inactive_sessions(self, cleanup_handler, mock_table, mock_cloudwatch):
        """Test cleanup of inactive sessions."""
        # Mock inactive sessions
        inactive_sessions = [
            {
                'session_id': 'session-3',
                'last_activity': '2024-01-01T12:00:00Z',
                'created_at': '2024-01-01T11:00:00Z'
            }
        ]
        
        # First call returns expired sessions (empty), second call returns inactive sessions
        mock_table.scan.side_effect = [
            {'Items': []},
            {'Items': inactive_sessions}
        ]
        
        # Mock batch writer
        mock_batch_writer = Mock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 1
        assert result['sessions_identified'] == 1
        
        # Verify batch delete was called
        mock_batch_writer.delete_item.assert_called_once_with(Key={'session_id': 'session-3'})
    
    def test_cleanup_dry_run(self, cleanup_handler, mock_table):
        """Test cleanup in dry run mode."""
        cleanup_handler.dry_run = True
        
        # Mock sessions to cleanup
        sessions = [
            {
                'session_id': 'session-1',
                'last_activity': '2024-01-01T10:00:00Z',
                'created_at': '2024-01-01T09:00:00Z'
            }
        ]
        
        mock_table.scan.side_effect = [
            {'Items': sessions},
            {'Items': []}
        ]
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 0  # No actual cleanup in dry run
        assert result['sessions_identified'] == 1
        assert result['dry_run'] is True
        
        # Verify no batch operations were performed
        mock_table.batch_writer.assert_not_called()
    
    def test_cleanup_with_pagination(self, cleanup_handler, mock_table, mock_cloudwatch):
        """Test cleanup with DynamoDB pagination."""
        # Mock paginated response for expired sessions
        page1_sessions = [{'session_id': 'session-1', 'last_activity': '2024-01-01T10:00:00Z', 'created_at': '2024-01-01T09:00:00Z'}]
        page2_sessions = [{'session_id': 'session-2', 'last_activity': '2024-01-01T11:00:00Z', 'created_at': '2024-01-01T10:00:00Z'}]
        
        mock_table.scan.side_effect = [
            {'Items': page1_sessions, 'LastEvaluatedKey': {'session_id': 'session-1'}},
            {'Items': page2_sessions},
            {'Items': []}  # Inactive sessions scan
        ]
        
        # Mock batch writer
        mock_batch_writer = Mock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 2
        
        # Verify pagination was handled (3 scan calls total)
        assert mock_table.scan.call_count == 3
        
        # Verify both sessions were deleted
        assert mock_batch_writer.delete_item.call_count == 2
    
    def test_cleanup_deduplication(self, cleanup_handler, mock_table, mock_cloudwatch):
        """Test deduplication of sessions found in both expired and inactive scans."""
        # Same session appears in both expired and inactive results
        duplicate_session = {
            'session_id': 'session-1',
            'last_activity': '2024-01-01T10:00:00Z',
            'created_at': '2024-01-01T09:00:00Z'
        }
        
        mock_table.scan.side_effect = [
            {'Items': [duplicate_session]},  # Expired sessions
            {'Items': [duplicate_session]}   # Inactive sessions
        ]
        
        # Mock batch writer
        mock_batch_writer = Mock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 1  # Should only clean up once
        assert result['sessions_identified'] == 1
        
        # Verify session was deleted only once
        mock_batch_writer.delete_item.assert_called_once_with(Key={'session_id': 'session-1'})
    
    def test_cleanup_batch_processing(self, cleanup_handler, mock_table, mock_cloudwatch):
        """Test cleanup with large number of sessions requiring batch processing."""
        # Create 30 sessions to test batch processing (batch size is 25)
        sessions = [
            {
                'session_id': f'session-{i}',
                'last_activity': '2024-01-01T10:00:00Z',
                'created_at': '2024-01-01T09:00:00Z'
            }
            for i in range(30)
        ]
        
        mock_table.scan.side_effect = [
            {'Items': sessions},
            {'Items': []}
        ]
        
        # Mock batch writer
        mock_batch_writer = Mock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer
        
        result = cleanup_handler.cleanup_inactive_sessions()
        
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 30
        
        # Verify all sessions were deleted
        assert mock_batch_writer.delete_item.call_count == 30
        
        # Verify batch_writer was called twice (for two batches)
        assert mock_table.batch_writer.call_count == 2
    
    def test_cleanup_dynamodb_error(self, cleanup_handler, mock_table):
        """Test cleanup handling of DynamoDB errors."""
        from botocore.exceptions import ClientError
        
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}}
        mock_table.scan.side_effect = ClientError(error_response, 'Scan')
        
        with pytest.raises(SessionCleanupError) as exc_info:
            cleanup_handler.cleanup_inactive_sessions()
        
        assert "DynamoDB error during cleanup" in str(exc_info.value)
    
    def test_cleanup_unexpected_error(self, cleanup_handler, mock_table):
        """Test cleanup handling of unexpected errors."""
        mock_table.scan.side_effect = Exception("Unexpected error")
        
        with pytest.raises(SessionCleanupError) as exc_info:
            cleanup_handler.cleanup_inactive_sessions()
        
        assert "Unexpected error during cleanup" in str(exc_info.value)
    
    def test_send_metrics_success(self, cleanup_handler, mock_cloudwatch):
        """Test successful CloudWatch metrics sending."""
        cleanup_handler._send_cleanup_metrics(5)
        
        mock_cloudwatch.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'ChatbotSystem/SessionCleanup'
        metric_data = call_args[1]['MetricData']
        assert len(metric_data) == 2
        assert metric_data[0]['MetricName'] == 'SessionsCleanedUp'
        assert metric_data[0]['Value'] == 5
        assert metric_data[1]['MetricName'] == 'CleanupExecutions'
        assert metric_data[1]['Value'] == 1
    
    def test_send_metrics_failure(self, cleanup_handler, mock_cloudwatch):
        """Test CloudWatch metrics sending failure handling."""
        from botocore.exceptions import ClientError
        
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}
        mock_cloudwatch.put_metric_data.side_effect = ClientError(error_response, 'PutMetricData')
        
        # Should not raise exception, just log warning
        cleanup_handler._send_cleanup_metrics(5)
        
        mock_cloudwatch.put_metric_data.assert_called_once()


class TestLambdaHandler:
    """Test cases for lambda_handler function."""
    
    @patch('handler.SessionCleanupHandler')
    @patch('handler.SESSIONS_TABLE', 'test-sessions')
    @patch('handler.REGION_NAME', 'us-west-2')
    @patch('handler.SESSION_TIMEOUT_MINUTES', 45)
    @patch('handler.DRY_RUN', False)
    def test_lambda_handler_success(self, mock_handler_class):
        """Test successful lambda handler execution."""
        # Mock handler instance
        mock_handler = Mock()
        mock_handler.cleanup_inactive_sessions.return_value = {
            'status': 'success',
            'sessions_cleaned': 3,
            'dry_run': False
        }
        mock_handler_class.return_value = mock_handler
        
        event = {'source': 'aws.events'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['status'] == 'success'
        assert body['sessions_cleaned'] == 3
        
        # Verify handler was initialized with correct parameters
        mock_handler_class.assert_called_once_with(
            table_name='test-sessions',
            region_name='us-west-2',
            session_timeout_minutes=45,
            dry_run=False
        )
    
    @patch('handler.SessionCleanupHandler')
    @patch('handler.SESSIONS_TABLE', 'test-sessions')
    @patch('handler.DRY_RUN', True)
    def test_lambda_handler_dry_run(self, mock_handler_class):
        """Test lambda handler in dry run mode."""
        mock_handler = Mock()
        mock_handler.cleanup_inactive_sessions.return_value = {
            'status': 'success',
            'sessions_cleaned': 0,
            'sessions_identified': 5,
            'dry_run': True
        }
        mock_handler_class.return_value = mock_handler
        
        event = {'source': 'aws.events'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['dry_run'] is True
        assert body['sessions_cleaned'] == 0
        assert body['sessions_identified'] == 5
        
        # Verify handler was initialized with dry_run=True
        mock_handler_class.assert_called_once()
        call_args = mock_handler_class.call_args[1]
        assert call_args['dry_run'] is True
    
    @patch('handler.SessionCleanupHandler')
    def test_lambda_handler_cleanup_error(self, mock_handler_class):
        """Test lambda handler with SessionCleanupError."""
        mock_handler = Mock()
        mock_handler.cleanup_inactive_sessions.side_effect = SessionCleanupError("Cleanup failed")
        mock_handler_class.return_value = mock_handler
        
        event = {'source': 'aws.events'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert body['status'] == 'error'
        assert body['error'] == 'Cleanup failed'
        assert body['error_type'] == 'SessionCleanupError'
    
    @patch('handler.SessionCleanupHandler')
    def test_lambda_handler_unexpected_error(self, mock_handler_class):
        """Test lambda handler with unexpected error."""
        mock_handler_class.side_effect = Exception("Unexpected error")
        
        event = {'source': 'aws.events'}
        context = Mock()
        
        result = lambda_handler(event, context)
        
        assert result['statusCode'] == 500
        body = json.loads(result['body'])
        assert body['status'] == 'error'
        assert body['error'] == 'Unexpected error'
        assert body['error_type'] == 'UnexpectedError'
    
    def test_lambda_handler_default_environment(self):
        """Test lambda handler with default environment variables."""
        with patch('handler.SessionCleanupHandler') as mock_handler_class:
            mock_handler = Mock()
            mock_handler.cleanup_inactive_sessions.return_value = {'status': 'success', 'sessions_cleaned': 0}
            mock_handler_class.return_value = mock_handler
            
            event = {'source': 'aws.events'}
            context = Mock()
            
            result = lambda_handler(event, context)
            
            assert result['statusCode'] == 200
            
            # Verify default values were used (these are the actual defaults from the module)
            mock_handler_class.assert_called_once_with(
                table_name='chatbot-sessions',
                region_name='us-east-1',
                session_timeout_minutes=30,
                dry_run=False
            )


class TestSessionCleanupIntegration:
    """Integration tests for session cleanup functionality."""
    
    @mock_aws
    def test_full_cleanup_integration(self):
        """Test full cleanup process with real AWS services (mocked)."""
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='test-sessions',
            KeySchema=[
                {'AttributeName': 'session_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'session_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Add test sessions
        current_time = datetime.now(timezone.utc)
        expired_time = current_time - timedelta(hours=2)
        
        # Active session (should not be cleaned)
        table.put_item(Item={
            'session_id': 'active-session',
            'created_at': current_time.isoformat(),
            'last_activity': current_time.isoformat(),
            'is_active': True
        })
        
        # Expired session (should be cleaned)
        table.put_item(Item={
            'session_id': 'expired-session',
            'created_at': expired_time.isoformat(),
            'last_activity': expired_time.isoformat(),
            'is_active': True
        })
        
        # Inactive session (should be cleaned)
        table.put_item(Item={
            'session_id': 'inactive-session',
            'created_at': current_time.isoformat(),
            'last_activity': current_time.isoformat(),
            'is_active': False
        })
        
        # Create cleanup handler
        handler = SessionCleanupHandler(
            table_name='test-sessions',
            region_name='us-east-1',
            session_timeout_minutes=30,
            dry_run=False
        )
        
        # Perform cleanup
        result = handler.cleanup_inactive_sessions()
        
        # Verify results
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 2  # expired and inactive sessions
        
        # Verify remaining sessions
        response = table.scan()
        remaining_sessions = response['Items']
        assert len(remaining_sessions) == 1
        assert remaining_sessions[0]['session_id'] == 'active-session'


if __name__ == '__main__':
    pytest.main([__file__])