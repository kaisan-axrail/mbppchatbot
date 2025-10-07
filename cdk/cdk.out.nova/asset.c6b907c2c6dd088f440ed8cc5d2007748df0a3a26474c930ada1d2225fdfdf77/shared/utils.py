"""
Shared utility functions for the chatbot system.
"""

import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional


def generate_session_id() -> str:
    """
    Generate a unique session ID.
    
    Returns:
        Unique session ID string
    """
    return str(uuid.uuid4())


def generate_message_id() -> str:
    """
    Generate a unique message ID.
    
    Returns:
        Unique message ID string
    """
    return str(uuid.uuid4())


def get_current_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp string
    """
    return datetime.now(timezone.utc).isoformat()


def get_ttl_timestamp(hours: int = 24) -> int:
    """
    Get TTL timestamp for DynamoDB (Unix timestamp).
    
    Args:
        hours: Number of hours from now for TTL
        
    Returns:
        Unix timestamp for TTL
    """
    return int(time.time()) + (hours * 3600)


def format_error_response(error_code: str, message: str) -> Dict[str, Any]:
    """
    Format error response for consistent error handling.
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        
    Returns:
        Formatted error response dictionary
    """
    return {
        'error': {
            'code': error_code,
            'message': message,
            'timestamp': get_current_timestamp()
        }
    }


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.
    
    Args:
        session_id: Session ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        uuid.UUID(session_id)
        return True
    except ValueError:
        return False


def validate_message_id(message_id: str) -> bool:
    """
    Validate message ID format.
    
    Args:
        message_id: Message ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        uuid.UUID(message_id)
        return True
    except ValueError:
        return False


def format_timestamp(timestamp: datetime) -> str:
    """
    Format datetime object to ISO string.
    
    Args:
        timestamp: Datetime object to format
        
    Returns:
        ISO formatted timestamp string
    """
    return timestamp.isoformat()


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse ISO timestamp string to datetime object.
    
    Args:
        timestamp_str: ISO formatted timestamp string
        
    Returns:
        Datetime object or None if parsing fails
    """
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except ValueError:
        return None


def calculate_time_difference(start_time: datetime, end_time: datetime) -> float:
    """
    Calculate time difference in seconds between two datetime objects.
    
    Args:
        start_time: Start datetime
        end_time: End datetime
        
    Returns:
        Time difference in seconds
    """
    return (end_time - start_time).total_seconds()


def sanitize_input(input_str: str, max_length: int = 1000) -> str:
    """
    Sanitize input string by removing potentially harmful characters.
    
    Args:
        input_str: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(input_str, str):
        return ""
    
    # Remove null bytes and control characters
    sanitized = ''.join(char for char in input_str if ord(char) >= 32 or char in '\n\r\t')
    
    # Truncate to max length
    return sanitized[:max_length]


def create_response_metadata(
    session_id: str,
    message_id: str,
    query_type: str,
    response_time: float
) -> Dict[str, Any]:
    """
    Create response metadata dictionary.
    
    Args:
        session_id: Session identifier
        message_id: Message identifier
        query_type: Type of query processed
        response_time: Processing time in milliseconds
        
    Returns:
        Response metadata dictionary
    """
    return {
        'session_id': session_id,
        'message_id': message_id,
        'query_type': query_type,
        'response_time': response_time,
        'timestamp': get_current_timestamp()
    }