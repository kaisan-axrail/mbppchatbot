"""
Session data models and validation functions for the websocket chatbot system.

This module provides dataclasses and utility functions for session management,
following clean code standards with proper type annotations.
"""

import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from enum import Enum


class SessionStatus(Enum):
    """Enumeration for session status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


@dataclass
class ClientInfo:
    """Client information for session tracking."""
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    connection_id: Optional[str] = None


@dataclass
class Session:
    """
    Session data model for in-memory session management.
    
    This class represents an active session with all necessary metadata
    for conversation tracking and session lifecycle management.
    """
    session_id: str
    created_at: datetime
    last_activity: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    client_info: Optional[ClientInfo] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """
        Check if session has expired based on last activity.
        
        Args:
            timeout_minutes: Session timeout in minutes (default: 30)
            
        Returns:
            bool: True if session has expired, False otherwise
        """
        current_time = datetime.now(timezone.utc)
        time_diff = current_time - self.last_activity
        return time_diff.total_seconds() > (timeout_minutes * 60)
    
    def update_activity(self) -> None:
        """Update the last activity timestamp to current time."""
        self.last_activity = datetime.now(timezone.utc)
        if self.status == SessionStatus.INACTIVE:
            self.status = SessionStatus.ACTIVE


@dataclass
class SessionRecord:
    """
    Session record data model for DynamoDB storage.
    
    This class represents session data as stored in DynamoDB with
    proper serialization format and TTL support.
    """
    sessionId: str
    created_at: str  # ISO timestamp string for DynamoDB
    last_activity: str  # ISO timestamp string for DynamoDB
    is_active: bool
    client_info: Optional[Dict[str, Any]] = field(default=None)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl: int = field(default_factory=lambda: int(time.time()) + (24 * 60 * 60))  # 24 hours default
    
    @classmethod
    def from_session(cls, session: Session) -> 'SessionRecord':
        """
        Create SessionRecord from Session object.
        
        Args:
            session: Session object to convert
            
        Returns:
            SessionRecord: Converted session record for DynamoDB storage
        """
        client_info_dict = None
        if session.client_info:
            client_info_dict = {
                'user_agent': session.client_info.user_agent,
                'ip_address': session.client_info.ip_address,
                'connection_id': session.client_info.connection_id
            }
        
        return cls(
            sessionId=session.session_id,
            created_at=session.created_at.isoformat(),
            last_activity=session.last_activity.isoformat(),
            is_active=(session.status == SessionStatus.ACTIVE),
            client_info=client_info_dict,
            metadata=session.metadata,
            ttl=int(time.time()) + (24 * 60 * 60)  # 24 hours from now
        )
    
    def to_session(self) -> Session:
        """
        Convert SessionRecord to Session object.
        
        Returns:
            Session: Converted session object for in-memory use
        """
        client_info = None
        if self.client_info:
            client_info = ClientInfo(
                user_agent=self.client_info.get('user_agent'),
                ip_address=self.client_info.get('ip_address'),
                connection_id=self.client_info.get('connection_id')
            )
        
        status = SessionStatus.ACTIVE if self.is_active else SessionStatus.INACTIVE
        
        return Session(
            session_id=self.sessionId,
            created_at=datetime.fromisoformat(self.created_at.replace('Z', '+00:00')),
            last_activity=datetime.fromisoformat(self.last_activity.replace('Z', '+00:00')),
            status=status,
            client_info=client_info,
            metadata=self.metadata
        )


def generate_session_id() -> str:
    """
    Generate a unique session ID using UUID4.
    
    Returns:
        str: Unique session identifier in UUID4 format
    """
    return str(uuid.uuid4())


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        bool: True if valid UUID4 format, False otherwise
    """
    if not isinstance(session_id, str):
        return False
    
    try:
        uuid_obj = uuid.UUID(session_id, version=4)
        return str(uuid_obj) == session_id
    except (ValueError, TypeError):
        return False


def create_new_session(client_info: Optional[ClientInfo] = None) -> Session:
    """
    Create a new session with generated ID and current timestamp.
    
    Args:
        client_info: Optional client information
        
    Returns:
        Session: New session object with generated ID
    """
    current_time = datetime.now(timezone.utc)
    
    return Session(
        session_id=generate_session_id(),
        created_at=current_time,
        last_activity=current_time,
        status=SessionStatus.ACTIVE,
        client_info=client_info,
        metadata={}
    )


def validate_session_data(session_data: Dict[str, Any]) -> bool:
    """
    Validate session data dictionary contains required fields.
    
    Args:
        session_data: Dictionary containing session data
        
    Returns:
        bool: True if all required fields are present and valid
    """
    required_fields = ['session_id', 'created_at', 'last_activity', 'is_active']
    
    # Check required fields exist
    for field in required_fields:
        if field not in session_data:
            return False
    
    # Validate session ID format
    if not validate_session_id(session_data['session_id']):
        return False
    
    # Validate boolean field
    if not isinstance(session_data['is_active'], bool):
        return False
    
    # Validate timestamp formats
    try:
        datetime.fromisoformat(session_data['created_at'].replace('Z', '+00:00'))
        datetime.fromisoformat(session_data['last_activity'].replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return False
    
    return True