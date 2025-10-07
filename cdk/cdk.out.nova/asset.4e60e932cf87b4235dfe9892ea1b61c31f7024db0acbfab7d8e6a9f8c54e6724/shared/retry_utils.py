"""
Retry utilities with exponential backoff and graceful degradation.

This module provides decorators and utilities for implementing retry logic
with exponential backoff for transient failures and graceful degradation
when external services are unavailable.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union, Tuple
from datetime import datetime, timedelta

from shared.exceptions import (
    TimeoutError,
    RateLimitError,
    NetworkError,
    AwsServiceError,
    StrandClientError,
    McpHandlerError,
    DatabaseError,
    get_user_friendly_message
)

# Configure logging
logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_JITTER = True

# Transient error types that should be retried
RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    RateLimitError,
    NetworkError,
    ConnectionError,
    OSError,
)

# AWS service error codes that indicate transient failures
RETRYABLE_AWS_ERROR_CODES = {
    'ThrottlingException',
    'ProvisionedThroughputExceededException',
    'RequestLimitExceeded',
    'ServiceUnavailable',
    'InternalServerError',
    'RequestTimeout',
    'SlowDown',
    'TooManyRequestsException',
}


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        jitter: bool = DEFAULT_JITTER,
        retryable_exceptions: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout


# Import enhanced circuit breaker functionality
from shared.circuit_breaker import (
    get_circuit_breaker as get_enhanced_circuit_breaker,
    EnhancedCircuitBreaker,
    CircuitBreakerState
)


class CircuitBreaker:
    """Legacy circuit breaker implementation for backward compatibility."""
    
    def __init__(self, threshold: int = 5, timeout: int = 60) -> None:
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.state == "OPEN":
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                self.state = "HALF_OPEN"
                return False
            return True
        return False
    
    def record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


# Global circuit breakers for different services (legacy)
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str, threshold: int = 5, timeout: int = 60) -> CircuitBreaker:
    """Get or create legacy circuit breaker for a service."""
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(threshold, timeout)
    return _circuit_breakers[service_name]


def get_enhanced_circuit_breaker_for_service(service_name: str) -> EnhancedCircuitBreaker:
    """Get enhanced circuit breaker for a service."""
    return get_enhanced_circuit_breaker(service_name)


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for retry attempt with exponential backoff."""
    delay = config.base_delay * (config.backoff_multiplier ** attempt)
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        # Add jitter to prevent thundering herd
        jitter_range = delay * 0.1
        delay += random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)


def is_retryable_error(error: Exception, config: RetryConfig) -> bool:
    """Check if an error is retryable."""
    # Check if it's a configured retryable exception
    if isinstance(error, config.retryable_exceptions):
        return True
    
    # Check for AWS service errors with retryable error codes
    if isinstance(error, AwsServiceError):
        error_code = getattr(error, 'error_code', '')
        return error_code in RETRYABLE_AWS_ERROR_CODES
    
    # Check for rate limit errors
    if isinstance(error, RateLimitError):
        return True
    
    # Check error message for common transient error patterns
    error_msg = str(error).lower()
    transient_patterns = [
        'timeout',
        'connection',
        'network',
        'throttl',
        'rate limit',
        'service unavailable',
        'internal server error',
        'temporary',
        'transient'
    ]
    
    return any(pattern in error_msg for pattern in transient_patterns)


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    service_name: Optional[str] = None,
    fallback_value: Any = None
) -> Callable:
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        config: Retry configuration
        service_name: Service name for circuit breaker
        fallback_value: Value to return if all retries fail
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Use enhanced circuit breaker if service name is provided
            enhanced_circuit_breaker = None
            legacy_circuit_breaker = None
            
            if service_name:
                enhanced_circuit_breaker = get_enhanced_circuit_breaker_for_service(service_name)
            else:
                legacy_circuit_breaker = get_circuit_breaker(service_name) if service_name else None
            
            # Check circuit breaker
            if enhanced_circuit_breaker and not enhanced_circuit_breaker.is_request_allowed():
                logger.warning(f"Enhanced circuit breaker blocking requests for {service_name}, returning fallback")
                if fallback_value is not None:
                    return fallback_value
                raise NetworkError(f"Service {service_name} is currently unavailable", service_name)
            elif legacy_circuit_breaker and legacy_circuit_breaker.is_open():
                logger.warning(f"Legacy circuit breaker open for {service_name}, returning fallback")
                if fallback_value is not None:
                    return fallback_value
                raise NetworkError(f"Service {service_name} is currently unavailable", service_name)
            
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    
                    # Record success in circuit breaker
                    if enhanced_circuit_breaker:
                        enhanced_circuit_breaker.record_success()
                    elif legacy_circuit_breaker:
                        legacy_circuit_breaker.record_success()
                    
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Record failure in circuit breaker
                    if enhanced_circuit_breaker:
                        enhanced_circuit_breaker.record_failure(e)
                    elif legacy_circuit_breaker:
                        legacy_circuit_breaker.record_failure()
                    
                    # Check if we should retry
                    if attempt < config.max_retries and is_retryable_error(e, config):
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Function {func.__name__} failed on attempt {attempt + 1}: {str(e)}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # No more retries or non-retryable error
                        logger.error(f"Function {func.__name__} failed after {attempt + 1} attempts: {str(e)}")
                        break
            
            # All retries exhausted, return fallback or raise
            if fallback_value is not None:
                logger.info(f"Returning fallback value for {func.__name__}")
                return fallback_value
            
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Use enhanced circuit breaker if service name is provided
            enhanced_circuit_breaker = None
            legacy_circuit_breaker = None
            
            if service_name:
                enhanced_circuit_breaker = get_enhanced_circuit_breaker_for_service(service_name)
            else:
                legacy_circuit_breaker = get_circuit_breaker(service_name) if service_name else None
            
            # Check circuit breaker
            if enhanced_circuit_breaker and not enhanced_circuit_breaker.is_request_allowed():
                logger.warning(f"Enhanced circuit breaker blocking requests for {service_name}, returning fallback")
                if fallback_value is not None:
                    return fallback_value
                raise NetworkError(f"Service {service_name} is currently unavailable", service_name)
            elif legacy_circuit_breaker and legacy_circuit_breaker.is_open():
                logger.warning(f"Legacy circuit breaker open for {service_name}, returning fallback")
                if fallback_value is not None:
                    return fallback_value
                raise NetworkError(f"Service {service_name} is currently unavailable", service_name)
            
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Record success in circuit breaker
                    if enhanced_circuit_breaker:
                        enhanced_circuit_breaker.record_success()
                    elif legacy_circuit_breaker:
                        legacy_circuit_breaker.record_success()
                    
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Record failure in circuit breaker
                    if enhanced_circuit_breaker:
                        enhanced_circuit_breaker.record_failure(e)
                    elif legacy_circuit_breaker:
                        legacy_circuit_breaker.record_failure()
                    
                    # Check if we should retry
                    if attempt < config.max_retries and is_retryable_error(e, config):
                        delay = calculate_delay(attempt, config)
                        logger.warning(
                            f"Function {func.__name__} failed on attempt {attempt + 1}: {str(e)}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        # No more retries or non-retryable error
                        logger.error(f"Function {func.__name__} failed after {attempt + 1} attempts: {str(e)}")
                        break
            
            # All retries exhausted, return fallback or raise
            if fallback_value is not None:
                logger.info(f"Returning fallback value for {func.__name__}")
                return fallback_value
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def with_graceful_degradation(
    fallback_message: str = "Service temporarily unavailable",
    log_errors: bool = True
) -> Callable:
    """
    Decorator for graceful degradation when services fail.
    
    Args:
        fallback_message: Message to return when service fails
        log_errors: Whether to log errors
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> str:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Service degradation in {func.__name__}: {str(e)}")
                
                # Return user-friendly message
                return get_user_friendly_message(e) if hasattr(e, 'user_message') else fallback_message
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> str:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Service degradation in {func.__name__}: {str(e)}")
                
                # Return user-friendly message
                return get_user_friendly_message(e) if hasattr(e, 'user_message') else fallback_message
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class GracefulDegradationManager:
    """Manager for handling graceful degradation scenarios."""
    
    def __init__(self) -> None:
        self.service_status: Dict[str, bool] = {}
        self.fallback_responses: Dict[str, str] = {
            'rag': "I'm having trouble accessing my knowledge base right now. Please try asking a general question instead.",
            'general': "I'm experiencing technical difficulties. Please try again in a few moments.",
            'mcp_tools': "I'm unable to access external tools right now. Please try rephrasing your request as a general question.",
            'session': "I'm having trouble with session management. Please refresh the page to start a new conversation.",
            'database': "I'm experiencing database issues. Your message may not be saved, but I'll try to help anyway.",
        }
    
    def mark_service_down(self, service_name: str) -> None:
        """Mark a service as down."""
        self.service_status[service_name] = False
        logger.warning(f"Service {service_name} marked as down")
    
    def mark_service_up(self, service_name: str) -> None:
        """Mark a service as up."""
        self.service_status[service_name] = True
        logger.info(f"Service {service_name} marked as up")
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if a service is available."""
        return self.service_status.get(service_name, True)
    
    def get_fallback_response(self, service_name: str) -> str:
        """Get fallback response for a service."""
        return self.fallback_responses.get(service_name, "Service temporarily unavailable")
    
    def set_fallback_response(self, service_name: str, response: str) -> None:
        """Set custom fallback response for a service."""
        self.fallback_responses[service_name] = response


# Global degradation manager instance
degradation_manager = GracefulDegradationManager()


def handle_service_failure(service_name: str, error: Exception) -> str:
    """
    Handle service failure with graceful degradation.
    
    Args:
        service_name: Name of the failed service
        error: Exception that occurred
        
    Returns:
        User-friendly fallback message
    """
    degradation_manager.mark_service_down(service_name)
    
    # Log the error with context
    logger.error(
        f"Service failure in {service_name}: {str(error)}",
        extra={
            "service": service_name,
            "error_type": type(error).__name__,
            "error_message": str(error)
        }
    )
    
    return degradation_manager.get_fallback_response(service_name)


async def health_check_service(service_name: str, check_func: Callable) -> bool:
    """
    Perform health check on a service.
    
    Args:
        service_name: Name of the service
        check_func: Function to perform health check
        
    Returns:
        True if service is healthy, False otherwise
    """
    try:
        if asyncio.iscoroutinefunction(check_func):
            await check_func()
        else:
            check_func()
        
        degradation_manager.mark_service_up(service_name)
        return True
        
    except Exception as e:
        logger.warning(f"Health check failed for {service_name}: {str(e)}")
        degradation_manager.mark_service_down(service_name)
        return False


# Predefined retry configurations for different services
STRAND_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    backoff_multiplier=2.0
)

MCP_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=0.5,
    max_delay=10.0,
    backoff_multiplier=2.0
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=0.5,
    max_delay=15.0,
    backoff_multiplier=1.5
)

OPENSEARCH_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=1.0,
    max_delay=20.0,
    backoff_multiplier=2.0
)