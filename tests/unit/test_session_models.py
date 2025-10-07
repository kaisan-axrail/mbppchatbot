"""
Unit tests for session data models and validation functions.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from shared.session_models import (
    Session,
    SessionRecord,
    ClientInfo,
    SessionStatus,
    generate_session_id,
    validate_session_id,
    create_new_session,
    validate_session_data
)


class TestSessionModels:
    """Test cases for session data models."""
    
    def test_session_creation(self):
        """Test Session dataclass creation and basic functionality."""
        session_id = generate_session_id()
        current_time = datetime.now(timezone.utc)
        client_info = ClientInfo(
            user_agent="test-agent",
            ip_address="127.0.0.1",
            connection_id="conn-123"
        )
        
        session = Session(
            session_id=session_id,
            created_at=current_time,
            last_activity=current_time,
            client_info=client_info
        )
        
        assert session.session_id == session_id
        assert session.created_at == current_time
        assert session.last_activity == current_time
        assert session.status == SessionStatus.ACTIVE
        assert session.client_info == client_info
        assert isinstance(session.metadata, dict)
    
    def test_session_is_expired(self):
        """Test session expiration logic."""
        current_time = datetime.now(timezone.utc)
        old_time = current_time - timedelta(minutes=45)
        
        # Create expired session
        expired_session = Session(
            session_id=generate_session_id(),
            created_at=old_time,
            last_activity=old_time
        )
        
        # Create active session
        active_session = Session(
            session_id=generate_session_id(),
            created_at=current_time,
            last_activity=current_time
        )
        
        assert expired_session.is_expired(timeout_minutes=30) is True
        assert active_session.is_expired(timeout_minutes=30) is False
    
    def test_session_update_activity(self):
        """Test session activity update."""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        session = Session(
            session_id=generate_session_id(),
            created_at=old_time,
            last_activity=old_time,
            status=SessionStatus.INACTIVE
        )
        
        session.update_activity()
        
        assert session.last_activity > old_time
        assert session.status == SessionStatus.ACTIVE
    
    def test_session_record_creation(self):
        """Test SessionRecord dataclass creation."""
        session_id = generate_session_id()
        current_time = datetime.now(timezone.utc).isoformat()
        
        record = SessionRecord(
            session_id=session_id,
            created_at=current_time,
            last_activity=current_time,
            is_active=True
        )
        
        assert record.session_id == session_id
        assert record.created_at == current_time
        assert record.last_activity == current_time
        assert record.is_active is True
        assert isinstance(record.ttl, int)
    
    def test_session_record_conversion(self):
        """Test conversion between Session and SessionRecord."""
        client_info = ClientInfo(
            user_agent="test-agent",
            ip_address="192.168.1.1"
        )
        
        original_session = Session(
            session_id=generate_session_id(),
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            client_info=client_info,
            metadata={"test": "value"}
        )
        
        # Convert to record and back
        record = SessionRecord.from_session(original_session)
        converted_session = record.to_session()
        
        assert converted_session.session_id == original_session.session_id
        assert converted_session.status == original_session.status
        assert converted_session.client_info.user_agent == original_session.client_info.user_agent
        assert converted_session.metadata == original_session.metadata


class TestSessionUtilities:
    """Test cases for session utility functions."""
    
    def test_generate_session_id(self):
        """Test session ID generation."""
        session_id = generate_session_id()
        
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID4 string length
        assert validate_session_id(session_id) is True
        
        # Test uniqueness
        another_id = generate_session_id()
        assert session_id != another_id
    
    def test_validate_session_id(self):
        """Test session ID validation."""
        valid_id = str(uuid.uuid4())
        invalid_ids = [
            "not-a-uuid",
            "12345",
            "",
            None,
            123,
            "550e8400-e29b-41d4-a716-44665544000"  # Invalid UUID
        ]
        
        assert validate_session_id(valid_id) is True
        
        for invalid_id in invalid_ids:
            assert validate_session_id(invalid_id) is False
    
    def test_create_new_session(self):
        """Test new session creation utility."""
        client_info = ClientInfo(user_agent="test")
        session = create_new_session(client_info)
        
        assert validate_session_id(session.session_id) is True
        assert session.status == SessionStatus.ACTIVE
        assert session.client_info == client_info
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)
        assert isinstance(session.metadata, dict)
    
    def test_create_new_session_without_client_info(self):
        """Test new session creation without client info."""
        session = create_new_session()
        
        assert validate_session_id(session.session_id) is True
        assert session.status == SessionStatus.ACTIVE
        assert session.client_info is None
    
    def test_validate_session_data(self):
        """Test session data validation."""
        valid_data = {
            'session_id': str(uuid.uuid4()),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_activity': datetime.now(timezone.utc).isoformat(),
            'is_active': True,
            'metadata': {}
        }
        
        assert validate_session_data(valid_data) is True
        
        # Test missing required fields
        incomplete_data = valid_data.copy()
        del incomplete_data['session_id']
        assert validate_session_data(incomplete_data) is False
        
        # Test invalid session ID
        invalid_id_data = valid_data.copy()
        invalid_id_data['session_id'] = "invalid-id"
        assert validate_session_data(invalid_id_data) is False
        
        # Test invalid boolean
        invalid_bool_data = valid_data.copy()
        invalid_bool_data['is_active'] = "true"
        assert validate_session_data(invalid_bool_data) is False
        
        # Test invalid timestamp
        invalid_time_data = valid_data.copy()
        invalid_time_data['created_at'] = "not-a-timestamp"
        assert validate_session_data(invalid_time_data) is False


class TestClientInfo:
    """Test cases for ClientInfo dataclass."""
    
    def test_client_info_creation(self):
        """Test ClientInfo creation with all fields."""
        client_info = ClientInfo(
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.100",
            connection_id="ws-conn-123"
        )
        
        assert client_info.user_agent == "Mozilla/5.0"
        assert client_info.ip_address == "192.168.1.100"
        assert client_info.connection_id == "ws-conn-123"
    
    def test_client_info_optional_fields(self):
        """Test ClientInfo creation with optional fields."""
        client_info = ClientInfo()
        
        assert client_info.user_agent is None
        assert client_info.ip_address is None
        assert client_info.connection_id is None