"""
Unit tests for shared utility functions.
"""

import pytest
import uuid
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from shared.utils import (
    generate_session_id,
    generate_message_id,
    get_current_timestamp,
    get_ttl_timestamp,
    validate_session_id,
    validate_message_id,
    format_timestamp,
    parse_timestamp,
    calculate_time_difference,
    sanitize_input,
    create_response_metadata,
    format_error_response
)


class TestIdGeneration:
    """Test cases for ID generation functions."""
    
    def test_generate_session_id(self):
        """Test session ID generation."""
        session_id = generate_session_id()
        
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID4 format
        assert session_id.count('-') == 4  # UUID4 has 4 hyphens
        
        # Verify it's a valid UUID
        uuid.UUID(session_id)
    
    def test_generate_session_id_uniqueness(self):
        """Test that generated session IDs are unique."""
        ids = [generate_session_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All should be unique
    
    def test_generate_message_id(self):
        """Test message ID generation."""
        message_id = generate_message_id()
        
        assert isinstance(message_id, str)
        assert len(message_id) == 36  # UUID4 format
        assert message_id.count('-') == 4  # UUID4 has 4 hyphens
        
        # Verify it's a valid UUID
        uuid.UUID(message_id)
    
    def test_generate_message_id_uniqueness(self):
        """Test that generated message IDs are unique."""
        ids = [generate_message_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All should be unique


class TestTimestampFunctions:
    """Test cases for timestamp utility functions."""
    
    def test_get_current_timestamp(self):
        """Test current timestamp generation."""
        timestamp = get_current_timestamp()
        
        assert isinstance(timestamp, str)
        assert 'T' in timestamp  # ISO format
        
        # Verify it's a valid ISO timestamp
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert parsed is not None
    
    def test_get_ttl_timestamp_default(self):
        """Test TTL timestamp generation with default hours."""
        ttl = get_ttl_timestamp()
        current_time = int(time.time())
        
        assert isinstance(ttl, int)
        assert ttl > current_time  # Should be in the future
        assert ttl <= current_time + (24 * 60 * 60) + 1  # Within 24 hours + 1 second tolerance
    
    def test_get_ttl_timestamp_custom_hours(self):
        """Test TTL timestamp generation with custom hours."""
        hours = 12
        ttl = get_ttl_timestamp(hours)
        current_time = int(time.time())
        expected_ttl = current_time + (hours * 60 * 60)
        
        assert isinstance(ttl, int)
        assert abs(ttl - expected_ttl) <= 1  # Within 1 second tolerance
    
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2024, 1, 1, 12, 30, 45, tzinfo=timezone.utc)
        formatted = format_timestamp(dt)
        
        assert formatted == "2024-01-01T12:30:45+00:00"
    
    def test_parse_timestamp_valid(self):
        """Test timestamp parsing."""
        timestamp_str = "2024-01-01T12:30:45+00:00"
        dt = parse_timestamp(timestamp_str)
        
        assert isinstance(dt, datetime)
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 30
        assert dt.second == 45
    
    def test_parse_timestamp_invalid(self):
        """Test parsing invalid timestamp."""
        invalid_timestamp = "not-a-timestamp"
        dt = parse_timestamp(invalid_timestamp)
        
        assert dt is None
    
    def test_calculate_time_difference(self):
        """Test time difference calculation."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 5, 30, tzinfo=timezone.utc)
        
        diff_seconds = calculate_time_difference(start, end)
        
        assert diff_seconds == 330  # 5 minutes 30 seconds


class TestValidationFunctions:
    """Test cases for validation utility functions."""
    
    def test_validate_session_id_valid(self):
        """Test validation of valid session ID."""
        valid_id = str(uuid.uuid4())
        assert validate_session_id(valid_id) is True
    
    def test_validate_session_id_invalid(self):
        """Test validation of invalid session IDs."""
        assert validate_session_id("invalid-id") is False
        assert validate_session_id("") is False
        assert validate_session_id("12345") is False
    
    def test_validate_message_id_valid(self):
        """Test validation of valid message ID."""
        valid_id = str(uuid.uuid4())
        assert validate_message_id(valid_id) is True
    
    def test_validate_message_id_invalid(self):
        """Test validation of invalid message IDs."""
        assert validate_message_id("invalid-id") is False
        assert validate_message_id("") is False


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        input_str = "Hello\x00World\x01Test"
        sanitized = sanitize_input(input_str)
        
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert "HelloWorldTest" == sanitized
    
    def test_sanitize_input_max_length(self):
        """Test input sanitization with max length."""
        long_input = "a" * 2000
        sanitized = sanitize_input(long_input, max_length=100)
        
        assert len(sanitized) == 100
        assert sanitized == "a" * 100
    
    def test_sanitize_input_non_string(self):
        """Test sanitization of non-string input."""
        assert sanitize_input(None) == ""
        assert sanitize_input(123) == ""
        assert sanitize_input([]) == ""
    
    def test_create_response_metadata(self):
        """Test response metadata creation."""
        metadata = create_response_metadata(
            session_id="test-session",
            message_id="test-message",
            query_type="general",
            response_time=150.5
        )
        
        assert metadata['session_id'] == "test-session"
        assert metadata['message_id'] == "test-message"
        assert metadata['query_type'] == "general"
        assert metadata['response_time'] == 150.5
        assert 'timestamp' in metadata
    
    def test_format_error_response(self):
        """Test error response formatting."""
        error_response = format_error_response("INVALID_INPUT", "Input validation failed")
        
        assert 'error' in error_response
        assert error_response['error']['code'] == "INVALID_INPUT"
        assert error_response['error']['message'] == "Input validation failed"
        assert 'timestamp' in error_response['error']


if __name__ == "__main__":
    pytest.main([__file__])