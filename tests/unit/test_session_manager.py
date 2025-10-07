"""
Unit tests for SessionManager class with DynamoDB integration.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import boto3

from shared.session_manager import SessionManager
from shared.session_models import (
    Session,
    SessionRecord,
    ClientInfo,
    SessionStatus,
    generate_session_id
)
from shared.exceptions import (
    SessionNotFoundError,
    SessionManagerError,
    DynamoDbError
)


class TestSessionManager:
    """Test cases for SessionManager class."""
    
    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table for testing."""
        table = MagicMock()
        table.put_item = MagicMock()
        table.get_item = MagicMock()
        table.update_item = MagicMock()
        table.scan = MagicMock()
        table.batch_writer = MagicMock()
        return table
    
    @pytest.fixture
    def session_manager(self, mock_table):
        """Create SessionManager instance with mock table."""
        with patch('boto3.resource') as mock_resource:
            mock_resource.return_value.Table.return_value = mock_table
            manager = SessionManager(
                table_name='test-sessions',
                region_name='us-east-1',
                session_timeout_minutes=30
            )
            manager.table = mock_table
            return manager
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, session_manager, mock_table):
        """Test successful session creation."""
        client_info = ClientInfo(
            user_agent="test-agent",
            ip_address="127.0.0.1"
        )
        
        session_id = await session_manager.create_session(client_info)
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID4 length
        
        # Verify put_item was called
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]
        assert 'Item' in call_args
        assert call_args['Item']['session_id'] == session_id
        assert call_args['Item']['is_active'] is True
    
    @pytest.mark.asyncio
    async def test_create_session_without_client_info(self, session_manager, mock_table):
        """Test session creation without client info."""
        session_id = await session_manager.create_session()
        
        assert session_id is not None
        
        # Verify put_item was called
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args[1]
        assert call_args['Item']['client_info'] == {}
    
    @pytest.mark.asyncio
    async def test_get_session_success(self, session_manager, mock_table):
        """Test successful session retrieval."""
        session_id = generate_session_id()
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Mock DynamoDB response
        mock_table.get_item.return_value = {
            'Item': {
                'session_id': session_id,
                'created_at': current_time,
                'last_activity': current_time,
                'is_active': True,
                'client_info': {},
                'metadata': {},
                'ttl': 1234567890
            }
        }
        
        # Retrieve the session
        session = await session_manager.get_session(session_id)
        
        assert session is not None
        assert session.session_id == session_id
        assert session.status == SessionStatus.ACTIVE
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, session_manager, mock_table):
        """Test retrieving non-existent session."""
        fake_session_id = generate_session_id()
        
        # Mock DynamoDB response for non-existent session
        mock_table.get_item.return_value = {}
        
        session = await session_manager.get_session(fake_session_id)
        
        assert session is None
    
    @pytest.mark.asyncio
    async def test_get_session_invalid_id(self, session_manager, mock_table):
        """Test retrieving session with invalid ID."""
        invalid_id = "invalid-session-id"
        
        session = await session_manager.get_session(invalid_id)
        
        assert session is None
        # Should not call DynamoDB for invalid ID
        mock_table.get_item.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_session_expired(self, session_manager, mock_table):
        """Test retrieving expired session."""
        session_id = generate_session_id()
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        
        # Mock DynamoDB response with expired session
        mock_table.get_item.return_value = {
            'Item': {
                'session_id': session_id,
                'created_at': old_time.isoformat(),
                'last_activity': old_time.isoformat(),
                'is_active': True,
                'client_info': {},
                'metadata': {},
                'ttl': int(old_time.timestamp()) + (24 * 60 * 60)
            }
        }
        
        # Try to retrieve expired session
        session = await session_manager.get_session(session_id)
        
        assert session is None
        # Should call update_item to mark as expired
        mock_table.update_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_activity_success(self, session_manager, mock_table):
        """Test successful activity update."""
        session_id = generate_session_id()
        
        # Update activity
        await session_manager.update_activity(session_id)
        
        # Verify update_item was called
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args[1]
        assert call_args['Key']['session_id'] == session_id
    
    @pytest.mark.asyncio
    async def test_update_activity_session_not_found(self, session_manager, mock_table):
        """Test activity update for non-existent session."""
        from botocore.exceptions import ClientError
        
        fake_session_id = generate_session_id()
        
        # Mock DynamoDB conditional check failure
        mock_table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ConditionalCheckFailedException'}},
            'UpdateItem'
        )
        
        with pytest.raises(SessionNotFoundError):
            await session_manager.update_activity(fake_session_id)
    
    @pytest.mark.asyncio
    async def test_update_activity_invalid_id(self, session_manager):
        """Test activity update with invalid session ID."""
        invalid_id = "invalid-id"
        
        with pytest.raises(SessionNotFoundError):
            await session_manager.update_activity(invalid_id)
    
    @pytest.mark.asyncio
    async def test_close_session_success(self, session_manager, mock_table):
        """Test successful session closing."""
        session_id = generate_session_id()
        
        # Close the session
        await session_manager.close_session(session_id)
        
        # Verify update_item was called
        mock_table.update_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive_sessions(self, session_manager, mock_table):
        """Test cleanup of inactive sessions."""
        # Mock scan response with inactive sessions
        mock_table.scan.return_value = {
            'Items': [
                {'session_id': 'inactive-1'},
                {'session_id': 'inactive-2'}
            ]
        }
        
        # Mock batch writer
        mock_batch = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch
        
        # Run cleanup
        cleanup_count = await session_manager.cleanup_inactive_sessions()
        
        assert cleanup_count == 2
        assert mock_batch.delete_item.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_active_session_count(self, session_manager, mock_table):
        """Test getting active session count."""
        # Mock scan response
        mock_table.scan.return_value = {'Count': 5}
        
        count = await session_manager.get_active_session_count()
        assert count == 5
    
    def test_session_record_to_item_conversion(self, session_manager):
        """Test conversion from SessionRecord to DynamoDB item."""
        session_record = SessionRecord(
            session_id=generate_session_id(),
            created_at=datetime.now(timezone.utc).isoformat(),
            last_activity=datetime.now(timezone.utc).isoformat(),
            is_active=True,
            client_info={'user_agent': 'test'},
            metadata={'key': 'value'}
        )
        
        item = session_manager._session_record_to_item(session_record)
        
        assert item['session_id'] == session_record.session_id
        assert item['is_active'] == session_record.is_active
        assert item['client_info'] == session_record.client_info
        assert item['metadata'] == session_record.metadata
    
    def test_item_to_session_record_conversion(self, session_manager):
        """Test conversion from DynamoDB item to SessionRecord."""
        session_id = generate_session_id()
        current_time = datetime.now(timezone.utc).isoformat()
        
        item = {
            'session_id': session_id,
            'created_at': current_time,
            'last_activity': current_time,
            'is_active': True,
            'client_info': {'user_agent': 'test'},
            'metadata': {'key': 'value'},
            'ttl': 1234567890
        }
        
        session_record = session_manager._item_to_session_record(item)
        
        assert session_record.session_id == session_id
        assert session_record.is_active is True
        assert session_record.client_info == {'user_agent': 'test'}
        assert session_record.metadata == {'key': 'value'}
    
    def test_item_to_session_record_empty_client_info(self, session_manager):
        """Test conversion with empty client info."""
        session_id = generate_session_id()
        current_time = datetime.now(timezone.utc).isoformat()
        
        item = {
            'session_id': session_id,
            'created_at': current_time,
            'last_activity': current_time,
            'is_active': True,
            'client_info': {},  # Empty dict
            'metadata': {}
        }
        
        session_record = session_manager._item_to_session_record(item)
        
        assert session_record.client_info is None


class TestSessionManagerErrorHandling:
    """Test error handling in SessionManager."""
    
    @pytest.mark.asyncio
    async def test_initialization_error(self):
        """Test SessionManager initialization with invalid configuration."""
        with patch('boto3.resource') as mock_resource:
            mock_resource.side_effect = Exception("Connection failed")
            
            with pytest.raises(SessionManagerError):
                SessionManager(
                    table_name='test-table',
                    region_name='invalid-region'
                )
    
    @pytest.mark.asyncio
    async def test_create_session_dynamodb_error(self):
        """Test session creation with DynamoDB error."""
        with patch('boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_table.put_item.side_effect = Exception("DynamoDB error")
            mock_resource.return_value.Table.return_value = mock_table
            
            session_manager = SessionManager('test-table')
            
            with pytest.raises(SessionManagerError):
                await session_manager.create_session()
    
    @pytest.mark.asyncio
    async def test_get_session_dynamodb_error(self):
        """Test session retrieval with DynamoDB error."""
        with patch('boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_table.get_item.side_effect = Exception("DynamoDB error")
            mock_resource.return_value.Table.return_value = mock_table
            
            session_manager = SessionManager('test-table')
            
            with pytest.raises(SessionManagerError):
                await session_manager.get_session(generate_session_id())
    
    @pytest.mark.asyncio
    async def test_cleanup_dynamodb_error(self):
        """Test cleanup with DynamoDB error."""
        with patch('boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_table.scan.side_effect = Exception("DynamoDB error")
            mock_resource.return_value.Table.return_value = mock_table
            
            session_manager = SessionManager('test-table')
            
            with pytest.raises(SessionManagerError):
                await session_manager.cleanup_inactive_sessions()