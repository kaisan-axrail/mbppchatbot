"""
Integration tests for session lifecycle management.

These tests verify the complete session lifecycle including creation,
activity tracking, expiration, and cleanup processes.
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

# Import session components
from shared.session_manager import SessionManager
from shared.session_models import ClientInfo, SessionStatus, generate_session_id
from shared.exceptions import SessionNotFoundError, SessionManagerError


class TestSessionLifecycleIntegration:
    """Integration tests for complete session lifecycle."""
    
    @pytest.fixture
    def mock_dynamodb(self):
        """Mock DynamoDB for session testing."""
        with patch('boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_table.put_item = Mock()
            mock_table.get_item = Mock()
            mock_table.update_item = Mock()
            mock_table.scan = Mock()
            mock_table.batch_writer = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            yield mock_table
    
    @pytest.mark.asyncio
    async def test_complete_session_lifecycle(self, mock_dynamodb):
        """Test complete session lifecycle from creation to cleanup."""
        session_manager = SessionManager('test-sessions-table')
        
        # Step 1: Create session
        client_info = ClientInfo(
            user_agent="test-browser/1.0",
            ip_address="192.168.1.100",
            connection_id="conn-123"
        )
        
        mock_dynamodb.put_item.return_value = {}
        session_id = await session_manager.create_session(client_info)
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        mock_dynamodb.put_item.assert_called_once()
        
        # Verify session data structure
        put_call_args = mock_dynamodb.put_item.call_args[1]
        session_item = put_call_args['Item']
        assert session_item['session_id'] == session_id
        assert session_item['is_active'] is True
        assert 'ttl' in session_item
        
        # Step 2: Retrieve session
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'session_id': session_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_activity': datetime.now(timezone.utc).isoformat(),
                'is_active': True,
                'client_info': {
                    'user_agent': 'test-browser/1.0',
                    'ip_address': '192.168.1.100',
                    'connection_id': 'conn-123'
                },
                'metadata': {},
                'ttl': 1234567890
            }
        }
        
        retrieved_session = await session_manager.get_session(session_id)
        assert retrieved_session is not None
        assert retrieved_session.session_id == session_id
        assert retrieved_session.status == SessionStatus.ACTIVE
        
        # Step 3: Update activity
        mock_dynamodb.update_item.return_value = {}
        await session_manager.update_activity(session_id)
        
        mock_dynamodb.update_item.assert_called_once()
        update_call_args = mock_dynamodb.update_item.call_args[1]
        assert update_call_args['Key']['session_id'] == session_id
        assert 'last_activity' in update_call_args['UpdateExpression']
        
        # Step 4: Close session
        await session_manager.close_session(session_id)
        
        # Verify close session call
        assert mock_dynamodb.update_item.call_count == 2  # activity update + close
        close_call_args = mock_dynamodb.update_item.call_args[1]
        assert 'is_active' in close_call_args['UpdateExpression']
    
    @pytest.mark.asyncio
    async def test_session_expiration_handling(self, mock_dynamodb):
        """Test session expiration detection and handling."""
        session_manager = SessionManager('test-sessions-table', session_timeout_minutes=30)
        
        session_id = generate_session_id()
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Mock expired session
        mock_dynamodb.get_item.return_value = {
            'Item': {
                'session_id': session_id,
                'created_at': expired_time.isoformat(),
                'last_activity': expired_time.isoformat(),
                'is_active': True,
                'client_info': {},
                'metadata': {},
                'ttl': int(expired_time.timestamp()) + (24 * 60 * 60)
            }
        }
        
        mock_dynamodb.update_item.return_value = {}
        
        # Attempt to get expired session
        session = await session_manager.get_session(session_id)
        
        # Should return None for expired session
        assert session is None
        
        # Should have called update to mark as expired
        mock_dynamodb.update_item.assert_called_once()
        update_call_args = mock_dynamodb.update_item.call_args[1]
        assert 'is_active' in update_call_args['UpdateExpression']
    
    @pytest.mark.asyncio
    async def test_session_cleanup_integration(self, mock_dynamodb):
        """Test session cleanup process integration."""
        session_manager = SessionManager('test-sessions-table')
        
        # Mock scan results with multiple sessions to clean up
        mock_dynamodb.scan.return_value = {
            'Items': [
                {'session_id': 'expired-session-1', 'last_activity': '2024-01-01T00:00:00Z'},
                {'session_id': 'expired-session-2', 'last_activity': '2024-01-01T00:00:00Z'},
                {'session_id': 'inactive-session-1', 'is_active': False}
            ]
        }
        
        # Mock batch writer
        mock_batch = Mock()
        mock_dynamodb.batch_writer.return_value.__enter__.return_value = mock_batch
        
        # Run cleanup
        cleanup_count = await session_manager.cleanup_inactive_sessions()
        
        # Verify cleanup results
        assert cleanup_count == 3
        assert mock_batch.delete_item.call_count == 3
        
        # Verify scan was called for both expired and inactive sessions
        assert mock_dynamodb.scan.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, mock_dynamodb):
        """Test concurrent session operations."""
        session_manager = SessionManager('test-sessions-table')
        
        # Mock responses for concurrent operations
        mock_dynamodb.put_item.return_value = {}
        mock_dynamodb.update_item.return_value = {}
        
        # Create multiple sessions concurrently
        client_infos = [
            ClientInfo(user_agent=f"browser-{i}", ip_address=f"192.168.1.{i}")
            for i in range(5)
        ]
        
        # Run concurrent session creation
        tasks = [
            session_manager.create_session(client_info)
            for client_info in client_infos
        ]
        
        session_ids = await asyncio.gather(*tasks)
        
        # Verify all sessions were created
        assert len(session_ids) == 5
        assert all(session_id is not None for session_id in session_ids)
        assert len(set(session_ids)) == 5  # All unique
        
        # Verify DynamoDB calls
        assert mock_dynamodb.put_item.call_count == 5
    
    @pytest.mark.asyncio
    async def test_session_error_recovery(self, mock_dynamodb):
        """Test session error handling and recovery."""
        session_manager = SessionManager('test-sessions-table')
        
        # Test DynamoDB error during session creation
        from botocore.exceptions import ClientError
        mock_dynamodb.put_item.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable'}}, 'PutItem'
        )
        
        client_info = ClientInfo(user_agent="test-browser")
        
        with pytest.raises(SessionManagerError):
            await session_manager.create_session(client_info)
        
        # Test recovery after error
        mock_dynamodb.put_item.side_effect = None
        mock_dynamodb.put_item.return_value = {}
        
        # Should work after error is resolved
        session_id = await session_manager.create_session(client_info)
        assert session_id is not None
    
    @pytest.mark.asyncio
    async def test_session_activity_tracking_integration(self, mock_dynamodb):
        """Test session activity tracking integration."""
        session_manager = SessionManager('test-sessions-table')
        
        session_id = generate_session_id()
        mock_dynamodb.update_item.return_value = {}
        
        # Simulate multiple activity updates
        for i in range(5):
            await session_manager.update_activity(session_id)
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Verify all updates were made
        assert mock_dynamodb.update_item.call_count == 5
        
        # Verify each call updated the timestamp
        for call in mock_dynamodb.update_item.call_args_list:
            call_args = call[1]
            assert call_args['Key']['session_id'] == session_id
            assert 'last_activity' in call_args['UpdateExpression']
            assert ':timestamp' in call_args['ExpressionAttributeValues']


class TestSessionCleanupIntegration:
    """Integration tests for session cleanup functionality."""
    
    @pytest.fixture
    def mock_cleanup_components(self):
        """Mock components for session cleanup testing."""
        # Load the session cleanup handler module
        import importlib.util
        
        session_cleanup_handler_path = os.path.join(
            os.path.dirname(__file__), 
            '../../lambda/session_cleanup/handler.py'
        )
        spec = importlib.util.spec_from_file_location("session_cleanup_handler", session_cleanup_handler_path)
        session_cleanup_handler = importlib.util.module_from_spec(spec)
        
        # Add shared modules to path
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
        
        spec.loader.exec_module(session_cleanup_handler)
        
        with patch('boto3.resource') as mock_resource, \
             patch('boto3.client') as mock_client:
            
            mock_table = Mock()
            mock_table.scan = Mock()
            mock_table.batch_writer = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            mock_cloudwatch = Mock()
            mock_cloudwatch.put_metric_data = Mock()
            mock_client.return_value = mock_cloudwatch
            
            yield {
                'handler_module': session_cleanup_handler,
                'dynamodb_table': mock_table,
                'cloudwatch': mock_cloudwatch
            }
    
    @pytest.mark.asyncio
    async def test_scheduled_cleanup_integration(self, mock_cleanup_components):
        """Test scheduled session cleanup integration."""
        SessionCleanupHandler = mock_cleanup_components['handler_module'].SessionCleanupHandler
        
        # Mock expired sessions
        expired_sessions = [
            {
                'session_id': f'expired-{i}',
                'last_activity': '2024-01-01T00:00:00Z',
                'created_at': '2024-01-01T00:00:00Z'
            }
            for i in range(10)
        ]
        
        mock_cleanup_components['dynamodb_table'].scan.return_value = {
            'Items': expired_sessions
        }
        
        # Mock batch writer
        mock_batch = Mock()
        mock_cleanup_components['dynamodb_table'].batch_writer.return_value.__enter__.return_value = mock_batch
        
        # Create cleanup handler
        cleanup_handler = SessionCleanupHandler(
            table_name='test-sessions',
            session_timeout_minutes=30,
            dry_run=False
        )
        
        # Run cleanup
        result = await cleanup_handler.cleanup_inactive_sessions()
        
        # Verify cleanup results
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 10
        assert not result['dry_run']
        
        # Verify batch deletion
        assert mock_batch.delete_item.call_count == 10
        
        # Verify metrics were sent
        mock_cleanup_components['cloudwatch'].put_metric_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dry_run_cleanup_integration(self, mock_cleanup_components):
        """Test dry run cleanup integration."""
        SessionCleanupHandler = mock_cleanup_components['handler_module'].SessionCleanupHandler
        
        # Mock sessions for cleanup
        sessions_to_cleanup = [
            {
                'session_id': f'session-{i}',
                'last_activity': '2024-01-01T00:00:00Z',
                'created_at': '2024-01-01T00:00:00Z'
            }
            for i in range(5)
        ]
        
        mock_cleanup_components['dynamodb_table'].scan.return_value = {
            'Items': sessions_to_cleanup
        }
        
        # Create cleanup handler in dry run mode
        cleanup_handler = SessionCleanupHandler(
            table_name='test-sessions',
            session_timeout_minutes=30,
            dry_run=True
        )
        
        # Run dry run cleanup
        result = await cleanup_handler.cleanup_inactive_sessions()
        
        # Verify dry run results
        assert result['status'] == 'success'
        assert result['sessions_cleaned'] == 0  # No actual cleanup in dry run
        assert result['sessions_identified'] == 5
        assert result['dry_run'] is True
        
        # Verify no actual deletion occurred
        mock_cleanup_components['dynamodb_table'].batch_writer.assert_not_called()
    
    def test_lambda_handler_integration(self, mock_cleanup_components):
        """Test Lambda handler integration for cleanup."""
        lambda_handler = mock_cleanup_components['handler_module'].lambda_handler
        
        # Mock successful cleanup
        with patch.object(
            mock_cleanup_components['handler_module'], 
            'SessionCleanupHandler'
        ) as mock_handler_class:
            
            mock_handler = Mock()
            mock_handler.cleanup_inactive_sessions = AsyncMock(return_value={
                'status': 'success',
                'sessions_cleaned': 3,
                'dry_run': False
            })
            mock_handler_class.return_value = mock_handler
            
            # Test Lambda handler
            event = {'source': 'aws.events'}  # CloudWatch Events trigger
            context = Mock()
            
            result = lambda_handler(event, context)
            
            # Verify successful response
            assert result['statusCode'] == 200
            response_body = json.loads(result['body'])
            assert response_body['status'] == 'success'
            assert response_body['sessions_cleaned'] == 3


class TestSessionMetricsIntegration:
    """Integration tests for session metrics and analytics."""
    
    @pytest.fixture
    def mock_analytics_components(self):
        """Mock analytics components."""
        with patch('boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_table.put_item = Mock()
            mock_table.query = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            yield mock_table
    
    @pytest.mark.asyncio
    async def test_session_analytics_integration(self, mock_analytics_components):
        """Test session analytics integration."""
        from shared.analytics_tracker import AnalyticsTracker
        
        analytics_tracker = AnalyticsTracker('test-analytics-table')
        
        # Mock successful analytics storage
        mock_analytics_components.put_item.return_value = {}
        
        # Track session creation
        await analytics_tracker.track_session_event(
            session_id='test-session-123',
            event_type='session_created',
            details={'client_info': {'user_agent': 'test-browser'}}
        )
        
        # Track session activity
        await analytics_tracker.track_session_event(
            session_id='test-session-123',
            event_type='session_activity',
            details={'activity_type': 'message_sent'}
        )
        
        # Track session closure
        await analytics_tracker.track_session_event(
            session_id='test-session-123',
            event_type='session_closed',
            details={'duration_minutes': 15}
        )
        
        # Verify all events were tracked
        assert mock_analytics_components.put_item.call_count == 3
        
        # Verify event structure
        for call in mock_analytics_components.put_item.call_args_list:
            call_args = call[1]
            item = call_args['Item']
            assert 'event_id' in item
            assert 'timestamp' in item
            assert 'session_id' in item
            assert item['session_id'] == 'test-session-123'
    
    @pytest.mark.asyncio
    async def test_session_metrics_aggregation(self, mock_analytics_components):
        """Test session metrics aggregation."""
        from shared.analytics_tracker import AnalyticsTracker
        
        analytics_tracker = AnalyticsTracker('test-analytics-table')
        
        # Mock query results for metrics
        mock_analytics_components.query.return_value = {
            'Items': [
                {
                    'event_type': 'session_created',
                    'timestamp': '2024-01-01T10:00:00Z',
                    'details': {'client_info': {'user_agent': 'browser-1'}}
                },
                {
                    'event_type': 'session_created',
                    'timestamp': '2024-01-01T11:00:00Z',
                    'details': {'client_info': {'user_agent': 'browser-2'}}
                },
                {
                    'event_type': 'session_closed',
                    'timestamp': '2024-01-01T12:00:00Z',
                    'details': {'duration_minutes': 30}
                }
            ]
        }
        
        # Get analytics for a specific date
        analytics_data = await analytics_tracker.get_analytics_by_date('2024-01-01')
        
        # Verify analytics retrieval
        assert len(analytics_data) == 3
        mock_analytics_components.query.assert_called_once()
        
        # Verify query parameters
        query_call_args = mock_analytics_components.query.call_args[1]
        assert query_call_args['KeyConditionExpression']
        assert '2024-01-01' in str(query_call_args['ExpressionAttributeValues'])


if __name__ == '__main__':
    pytest.main([__file__])