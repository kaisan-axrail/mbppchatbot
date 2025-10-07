"""
Unit tests for error handling and retry logic.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from shared.exceptions import (
    ChatbotError,
    StrandClientError,
    McpHandlerError,
    DynamoDbError,
    TimeoutError,
    RateLimitError,
    NetworkError,
    get_user_friendly_message,
    create_error_context
)
from shared.retry_utils import (
    RetryConfig,
    CircuitBreaker,
    calculate_delay,
    is_retryable_error,
    retry_with_backoff,
    with_graceful_degradation,
    GracefulDegradationManager,
    handle_service_failure,
    health_check_service,
    STRAND_RETRY_CONFIG,
    MCP_RETRY_CONFIG,
    DATABASE_RETRY_CONFIG
)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_chatbot_error_base_class(self):
        """Test ChatbotError base class functionality."""
        error = ChatbotError("Test error", "TEST_ERROR")
        assert str(error) == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.user_message is not None
    
    def test_chatbot_error_with_custom_user_message(self):
        """Test ChatbotError with custom user message."""
        custom_message = "Custom user message"
        error = ChatbotError("Technical error", "TEST_ERROR", custom_message)
        assert error.user_message == custom_message
    
    def test_session_not_found_error(self):
        """Test SessionNotFoundError."""
        from shared.exceptions import SessionNotFoundError
        
        session_id = "test-session-123"
        error = SessionNotFoundError(session_id)
        assert error.session_id == session_id
        assert error.code == "SESSION_NOT_FOUND"
        assert session_id in str(error)
    
    def test_strand_client_error(self):
        """Test StrandClientError."""
        error = StrandClientError("Connection failed", "CONNECTION_ERROR")
        assert error.code == "CONNECTION_ERROR"
        assert "Strand client error" in str(error)
    
    def test_mcp_tool_error(self):
        """Test McpToolError."""
        from shared.exceptions import McpToolError
        
        tool_name = "search_documents"
        error = McpToolError(tool_name, "Tool execution failed")
        assert error.tool_name == tool_name
        assert error.code == "MCP_TOOL_ERROR"
        assert tool_name in str(error)
    
    def test_dynamodb_error(self):
        """Test DynamoDbError."""
        operation = "put_item"
        error = DynamoDbError("Connection timeout", operation)
        assert error.operation == operation
        assert error.code == "DYNAMODB_ERROR"
        assert operation in str(error)
    
    def test_timeout_error(self):
        """Test TimeoutError."""
        operation = "api_call"
        timeout_seconds = 30.0
        error = TimeoutError(operation, timeout_seconds)
        assert error.operation == operation
        assert error.timeout_seconds == timeout_seconds
        assert error.code == "TIMEOUT_ERROR"
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        service = "strand_api"
        retry_after = 60
        error = RateLimitError(service, retry_after)
        assert error.service == service
        assert error.retry_after == retry_after
        assert error.code == "RATE_LIMIT_ERROR"


class TestErrorUtilities:
    """Test error utility functions."""
    
    def test_get_user_friendly_message_with_chatbot_error(self):
        """Test get_user_friendly_message with ChatbotError."""
        error = ChatbotError("Technical error", "TEST_ERROR", "User friendly message")
        message = get_user_friendly_message(error)
        assert message == "User friendly message"
    
    def test_get_user_friendly_message_with_timeout(self):
        """Test get_user_friendly_message with timeout error."""
        error = Exception("Connection timeout occurred")
        message = get_user_friendly_message(error)
        assert "longer than expected" in message.lower()
    
    def test_get_user_friendly_message_with_rate_limit(self):
        """Test get_user_friendly_message with rate limit error."""
        error = Exception("Rate limit exceeded")
        message = get_user_friendly_message(error)
        assert "many requests" in message.lower()
    
    def test_get_user_friendly_message_with_generic_error(self):
        """Test get_user_friendly_message with generic error."""
        error = Exception("Some random error")
        message = get_user_friendly_message(error)
        assert "unexpected error" in message.lower()
    
    def test_create_error_context(self):
        """Test create_error_context function."""
        error = StrandClientError("Connection failed", "CONNECTION_ERROR")
        context = create_error_context(error, session_id="test-123")
        
        assert context["error_type"] == "StrandClientError"
        assert context["error_code"] == "CONNECTION_ERROR"
        assert context["session_id"] == "test-123"
        assert "user_friendly_message" in context
    
    def test_create_error_context_with_attributes(self):
        """Test create_error_context with error attributes."""
        from shared.exceptions import McpToolError
        
        error = McpToolError("search_tool", "Tool failed")
        context = create_error_context(error)
        
        assert context["tool_name"] == "search_tool"
        assert context["error_code"] == "MCP_TOOL_ERROR"


class TestRetryConfig:
    """Test RetryConfig class."""
    
    def test_default_retry_config(self):
        """Test default RetryConfig values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter is True
    
    def test_custom_retry_config(self):
        """Test custom RetryConfig values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            backoff_multiplier=1.5,
            jitter=False
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_multiplier == 1.5
        assert config.jitter is False


class TestCircuitBreaker:
    """Test CircuitBreaker class."""
    
    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker initial state."""
        cb = CircuitBreaker(threshold=3, timeout=60)
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert not cb.is_open()
    
    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(threshold=3, timeout=60)
        
        # Record failures up to threshold
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state == "OPEN"
        assert cb.is_open()
    
    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets on success."""
        cb = CircuitBreaker(threshold=3, timeout=60)
        
        # Record some failures
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        
        # Record success
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "CLOSED"
    
    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker goes to half-open after timeout."""
        cb = CircuitBreaker(threshold=2, timeout=0.1)  # Short timeout for testing
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"
        
        # Wait for timeout
        import time
        time.sleep(0.2)
        
        # Should be half-open now
        assert not cb.is_open()


class TestRetryUtilities:
    """Test retry utility functions."""
    
    def test_calculate_delay(self):
        """Test calculate_delay function."""
        config = RetryConfig(base_delay=1.0, backoff_multiplier=2.0, max_delay=10.0, jitter=False)
        
        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 2.0
        assert calculate_delay(2, config) == 4.0
        assert calculate_delay(3, config) == 8.0
        assert calculate_delay(4, config) == 10.0  # Capped at max_delay
    
    def test_calculate_delay_with_jitter(self):
        """Test calculate_delay with jitter."""
        config = RetryConfig(base_delay=1.0, backoff_multiplier=2.0, jitter=True)
        
        delay1 = calculate_delay(1, config)
        delay2 = calculate_delay(1, config)
        
        # With jitter, delays should be different
        assert delay1 != delay2
        assert 1.8 <= delay1 <= 2.2  # Should be around 2.0 with jitter
        assert 1.8 <= delay2 <= 2.2
    
    def test_is_retryable_error(self):
        """Test is_retryable_error function."""
        config = RetryConfig()
        
        # Test retryable errors
        assert is_retryable_error(TimeoutError("test", 30), config)
        assert is_retryable_error(RateLimitError("service", 60), config)
        assert is_retryable_error(NetworkError("connection failed"), config)
        assert is_retryable_error(ConnectionError("connection lost"), config)
        
        # Test non-retryable errors
        assert not is_retryable_error(ValueError("invalid input"), config)
        assert not is_retryable_error(KeyError("missing key"), config)
    
    def test_is_retryable_error_by_message(self):
        """Test is_retryable_error by error message patterns."""
        config = RetryConfig()
        
        # Test retryable error messages
        assert is_retryable_error(Exception("Connection timeout"), config)
        assert is_retryable_error(Exception("Rate limit exceeded"), config)
        assert is_retryable_error(Exception("Service unavailable"), config)
        assert is_retryable_error(Exception("Throttling error"), config)
        
        # Test non-retryable error messages
        assert not is_retryable_error(Exception("Invalid parameter"), config)
        assert not is_retryable_error(Exception("Access denied"), config)


class TestRetryDecorator:
    """Test retry_with_backoff decorator."""
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success_first_attempt(self):
        """Test retry decorator with success on first attempt."""
        call_count = 0
        
        @retry_with_backoff(config=RetryConfig(max_retries=3))
        async def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_function()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success_after_retries(self):
        """Test retry decorator with success after retries."""
        call_count = 0
        
        @retry_with_backoff(config=RetryConfig(max_retries=3, base_delay=0.01))
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("test", 30)
            return "success"
        
        result = await test_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_exhausted_retries(self):
        """Test retry decorator with exhausted retries."""
        call_count = 0
        
        @retry_with_backoff(config=RetryConfig(max_retries=2, base_delay=0.01))
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("test", 30)
        
        with pytest.raises(TimeoutError):
            await test_function()
        
        assert call_count == 3  # Initial attempt + 2 retries
    
    @pytest.mark.asyncio
    async def test_retry_decorator_with_fallback(self):
        """Test retry decorator with fallback value."""
        call_count = 0
        
        @retry_with_backoff(
            config=RetryConfig(max_retries=1, base_delay=0.01),
            fallback_value="fallback"
        )
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("test", 30)
        
        result = await test_function()
        assert result == "fallback"
        assert call_count == 2  # Initial attempt + 1 retry
    
    @pytest.mark.asyncio
    async def test_retry_decorator_non_retryable_error(self):
        """Test retry decorator with non-retryable error."""
        call_count = 0
        
        @retry_with_backoff(config=RetryConfig(max_retries=3))
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")
        
        with pytest.raises(ValueError):
            await test_function()
        
        assert call_count == 1  # No retries for non-retryable error


class TestGracefulDegradation:
    """Test graceful degradation functionality."""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_decorator(self):
        """Test with_graceful_degradation decorator."""
        @with_graceful_degradation(fallback_message="Service unavailable")
        async def test_function():
            raise Exception("Service error")
        
        result = await test_function()
        assert result == "Service unavailable"
    
    def test_graceful_degradation_manager(self):
        """Test GracefulDegradationManager."""
        manager = GracefulDegradationManager()
        
        # Test initial state
        assert manager.is_service_available("test_service")
        
        # Mark service down
        manager.mark_service_down("test_service")
        assert not manager.is_service_available("test_service")
        
        # Mark service up
        manager.mark_service_up("test_service")
        assert manager.is_service_available("test_service")
    
    def test_handle_service_failure(self):
        """Test handle_service_failure function."""
        error = TimeoutError("test", 30)
        message = handle_service_failure("test_service", error)
        
        assert isinstance(message, str)
        assert len(message) > 0
    
    @pytest.mark.asyncio
    async def test_health_check_service_success(self):
        """Test health_check_service with successful check."""
        async def healthy_check():
            return True
        
        result = await health_check_service("test_service", healthy_check)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_service_failure(self):
        """Test health_check_service with failed check."""
        async def unhealthy_check():
            raise Exception("Service down")
        
        result = await health_check_service("test_service", unhealthy_check)
        assert result is False


class TestPredefinedConfigs:
    """Test predefined retry configurations."""
    
    def test_strand_retry_config(self):
        """Test STRAND_RETRY_CONFIG."""
        assert STRAND_RETRY_CONFIG.max_retries == 3
        assert STRAND_RETRY_CONFIG.base_delay == 1.0
        assert STRAND_RETRY_CONFIG.max_delay == 30.0
    
    def test_mcp_retry_config(self):
        """Test MCP_RETRY_CONFIG."""
        assert MCP_RETRY_CONFIG.max_retries == 2
        assert MCP_RETRY_CONFIG.base_delay == 0.5
        assert MCP_RETRY_CONFIG.max_delay == 10.0
    
    def test_database_retry_config(self):
        """Test DATABASE_RETRY_CONFIG."""
        assert DATABASE_RETRY_CONFIG.max_retries == 3
        assert DATABASE_RETRY_CONFIG.base_delay == 0.5
        assert DATABASE_RETRY_CONFIG.max_delay == 15.0


if __name__ == "__main__":
    pytest.main([__file__])