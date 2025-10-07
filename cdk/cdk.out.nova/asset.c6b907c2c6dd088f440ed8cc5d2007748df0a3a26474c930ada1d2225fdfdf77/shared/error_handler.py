"""
Enhanced error handling and isolation system for the websocket chatbot.

This module provides comprehensive error handling with isolation between
analytics and main processing, graceful degradation for service failures,
and actionable error logging.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime, timezone
from enum import Enum
from functools import wraps

from shared.exceptions import (
    ChatbotError,
    BedrockError,
    DatabaseError,
    NetworkError,
    TimeoutError,
    RateLimitError,
    get_user_friendly_message,
    create_error_context
)
from shared.circuit_breaker import (
    get_circuit_breaker,
    get_all_circuit_breaker_statuses,
    ServiceType as CircuitBreakerServiceType
)


# Configure structured logging
logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for categorization and handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceType(Enum):
    """Service types for error isolation and circuit breaker management."""
    BEDROCK = "bedrock"
    DYNAMODB = "dynamodb"
    ANALYTICS = "analytics"
    MCP = "mcp"
    WEBSOCKET = "websocket"


class ErrorHandler:
    """
    Enhanced error handler with service isolation and graceful degradation.
    
    This class provides comprehensive error handling capabilities including:
    - Service-specific error isolation
    - Analytics error separation from main processing
    - Graceful degradation for service failures
    - Actionable error logging and monitoring
    """
    
    def __init__(self):
        """Initialize the error handler with default configuration."""
        self.error_counts = {}
        self.service_status = {}
        self.fallback_responses = {}
        
        # Initialize service status tracking
        for service in ServiceType:
            self.service_status[service.value] = {
                'available': True,
                'last_error': None,
                'error_count': 0,
                'last_success': datetime.now(timezone.utc)
            }
        
        logger.info("ErrorHandler initialized with service isolation")
    
    def handle_analytics_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        continue_processing: bool = True
    ) -> bool:
        """
        Handle analytics errors with isolation from main processing.
        
        Args:
            error: The analytics error that occurred
            context: Context information about the error
            continue_processing: Whether to continue main processing
            
        Returns:
            True if main processing should continue, False otherwise
        """
        try:
            # Log analytics error with detailed context
            error_context = create_error_context(
                error,
                service=ServiceType.ANALYTICS.value,
                severity=ErrorSeverity.LOW.value,
                isolated=True,
                **context
            )
            
            logger.warning(
                "Analytics error isolated from main processing",
                extra={
                    'error_handler': 'analytics_isolation',
                    'error_context': error_context,
                    'continue_processing': continue_processing
                }
            )
            
            # Update service status
            self._update_service_status(ServiceType.ANALYTICS, error)
            
            # Analytics errors should not interrupt main processing
            return continue_processing
            
        except Exception as logging_error:
            # Even if logging fails, don't interrupt main processing
            logger.error(f"Failed to log analytics error: {logging_error}")
            return continue_processing
    
    def handle_bedrock_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        fallback_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Handle Bedrock service errors with graceful degradation.
        
        Args:
            error: The Bedrock error that occurred
            context: Context information about the error
            fallback_enabled: Whether to provide fallback response
            
        Returns:
            Error handling result with fallback response if applicable
        """
        try:
            # Determine error severity
            severity = self._determine_bedrock_error_severity(error)
            
            # Log Bedrock error with actionable information
            error_context = create_error_context(
                error,
                service=ServiceType.BEDROCK.value,
                severity=severity.value,
                **context
            )
            
            logger.error(
                "Bedrock service error detected",
                extra={
                    'error_handler': 'bedrock_degradation',
                    'error_context': error_context,
                    'fallback_enabled': fallback_enabled,
                    'actionable_info': self._get_bedrock_actionable_info(error)
                }
            )
            
            # Update service status
            self._update_service_status(ServiceType.BEDROCK, error)
            
            # Provide fallback response if enabled
            if fallback_enabled:
                fallback_response = self._create_bedrock_fallback_response(error, context)
                return {
                    'success': False,
                    'error': error,
                    'fallback_response': fallback_response,
                    'user_message': get_user_friendly_message(error)
                }
            else:
                return {
                    'success': False,
                    'error': error,
                    'user_message': get_user_friendly_message(error)
                }
                
        except Exception as handling_error:
            logger.error(f"Failed to handle Bedrock error: {handling_error}")
            return {
                'success': False,
                'error': error,
                'user_message': "I'm experiencing technical difficulties. Please try again."
            }
    
    def handle_database_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        operation: str,
        critical: bool = False
    ) -> Dict[str, Any]:
        """
        Handle database errors with appropriate isolation and logging.
        
        Args:
            error: The database error that occurred
            context: Context information about the error
            operation: The database operation that failed
            critical: Whether this is a critical operation
            
        Returns:
            Error handling result
        """
        try:
            # Determine severity based on operation criticality
            severity = ErrorSeverity.CRITICAL if critical else ErrorSeverity.MEDIUM
            
            # Log database error with operational context
            error_context = create_error_context(
                error,
                service=ServiceType.DYNAMODB.value,
                severity=severity.value,
                operation=operation,
                **context
            )
            
            logger.error(
                f"Database error in {operation} operation",
                extra={
                    'error_handler': 'database_isolation',
                    'error_context': error_context,
                    'critical_operation': critical,
                    'actionable_info': self._get_database_actionable_info(error, operation)
                }
            )
            
            # Update service status
            self._update_service_status(ServiceType.DYNAMODB, error)
            
            return {
                'success': False,
                'error': error,
                'operation': operation,
                'critical': critical,
                'user_message': get_user_friendly_message(error)
            }
            
        except Exception as handling_error:
            logger.error(f"Failed to handle database error: {handling_error}")
            return {
                'success': False,
                'error': error,
                'user_message': "I'm experiencing technical difficulties. Please try again."
            }
    
    def with_analytics_isolation(self, func: Callable) -> Callable:
        """
        Decorator to isolate analytics operations from main processing.
        
        Args:
            func: Function to wrap with analytics isolation
            
        Returns:
            Wrapped function with error isolation
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract context from function arguments
                context = {
                    'function_name': func.__name__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                
                # Handle analytics error in isolation
                self.handle_analytics_error(e, context, continue_processing=True)
                
                # Return None or default value to indicate analytics failure
                return None
        
        return wrapper
    
    def with_graceful_degradation(
        self,
        service_type: ServiceType,
        fallback_response: Optional[Any] = None
    ) -> Callable:
        """
        Decorator to provide graceful degradation for service failures.
        
        Args:
            service_type: Type of service to monitor
            fallback_response: Default fallback response
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    result = func(*args, **kwargs)
                    # Mark service as successful
                    self._mark_service_success(service_type)
                    return result
                except Exception as e:
                    # Handle service error with degradation
                    context = {
                        'function_name': func.__name__,
                        'service_type': service_type.value
                    }
                    
                    if service_type == ServiceType.BEDROCK:
                        return self.handle_bedrock_error(e, context)
                    elif service_type == ServiceType.DYNAMODB:
                        return self.handle_database_error(e, context, func.__name__)
                    else:
                        # Generic service error handling
                        logger.error(f"Service {service_type.value} error in {func.__name__}: {e}")
                        return fallback_response
            
            return wrapper
        return decorator
    
    def _determine_bedrock_error_severity(self, error: Exception) -> ErrorSeverity:
        """
        Determine the severity of a Bedrock error.
        
        Args:
            error: The Bedrock error
            
        Returns:
            Error severity level
        """
        error_str = str(error).lower()
        
        if "validationexception" in error_str:
            return ErrorSeverity.HIGH  # Configuration issue
        elif "throttlingexception" in error_str or "rate limit" in error_str:
            return ErrorSeverity.MEDIUM  # Temporary throttling
        elif "accessdeniedexception" in error_str:
            return ErrorSeverity.CRITICAL  # Permission issue
        elif "timeout" in error_str:
            return ErrorSeverity.MEDIUM  # Network issue
        else:
            return ErrorSeverity.HIGH  # Unknown error
    
    def _get_bedrock_actionable_info(self, error: Exception) -> Dict[str, str]:
        """
        Get actionable information for Bedrock errors.
        
        Args:
            error: The Bedrock error
            
        Returns:
            Dictionary with actionable information
        """
        error_str = str(error).lower()
        
        if "validationexception" in error_str:
            return {
                'issue': 'Model configuration error',
                'action': 'Check inference profile ARN and model access permissions',
                'priority': 'high'
            }
        elif "throttlingexception" in error_str:
            return {
                'issue': 'Rate limiting active',
                'action': 'Implement exponential backoff or request quota increase',
                'priority': 'medium'
            }
        elif "accessdeniedexception" in error_str:
            return {
                'issue': 'Permission denied',
                'action': 'Verify IAM roles and Bedrock model access permissions',
                'priority': 'critical'
            }
        else:
            return {
                'issue': 'Unknown Bedrock error',
                'action': 'Check AWS service status and configuration',
                'priority': 'high'
            }
    
    def _get_database_actionable_info(self, error: Exception, operation: str) -> Dict[str, str]:
        """
        Get actionable information for database errors.
        
        Args:
            error: The database error
            operation: The failed operation
            
        Returns:
            Dictionary with actionable information
        """
        error_str = str(error).lower()
        
        if "float types are not supported" in error_str:
            return {
                'issue': 'DynamoDB type conversion error',
                'action': 'Ensure all float values are converted to Decimal before storage',
                'priority': 'high'
            }
        elif "throttlingexception" in error_str:
            return {
                'issue': 'DynamoDB throttling',
                'action': 'Check table capacity and implement exponential backoff',
                'priority': 'medium'
            }
        elif "resourcenotfoundexception" in error_str:
            return {
                'issue': 'Table or resource not found',
                'action': f'Verify table exists and permissions for operation: {operation}',
                'priority': 'critical'
            }
        else:
            return {
                'issue': f'Database error in {operation}',
                'action': 'Check DynamoDB service status and table configuration',
                'priority': 'high'
            }
    
    def _create_bedrock_fallback_response(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a fallback response for Bedrock service failures.
        
        Args:
            error: The Bedrock error
            context: Error context
            
        Returns:
            Fallback response dictionary
        """
        # Determine appropriate fallback message based on error type
        error_str = str(error).lower()
        
        if "validationexception" in error_str:
            message = (
                "I'm currently experiencing a configuration issue. "
                "Please try again in a few moments while I resolve this."
            )
        elif "throttlingexception" in error_str:
            message = (
                "I'm currently handling many requests. "
                "Please wait a moment and try again."
            )
        elif "accessdeniedexception" in error_str:
            message = (
                "I'm experiencing an authentication issue. "
                "Please contact support if this persists."
            )
        else:
            message = (
                "I'm temporarily unavailable due to a technical issue. "
                "Please try again in a few moments."
            )
        
        return {
            "content": [{"type": "text", "text": message}],
            "usage": {"input_tokens": 0, "output_tokens": len(message.split())},
            "model": "fallback",
            "is_fallback": True,
            "error_type": type(error).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _update_service_status(self, service_type: ServiceType, error: Exception) -> None:
        """
        Update service status tracking for monitoring and circuit breaker logic.
        
        Args:
            service_type: Type of service that failed
            error: The error that occurred
        """
        service_key = service_type.value
        
        if service_key not in self.service_status:
            self.service_status[service_key] = {
                'available': True,
                'last_error': None,
                'error_count': 0,
                'last_success': datetime.now(timezone.utc)
            }
        
        self.service_status[service_key]['last_error'] = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.service_status[service_key]['error_count'] += 1
        
        # Update enhanced circuit breaker
        try:
            circuit_breaker = get_circuit_breaker(service_key)
            circuit_breaker.record_failure(error)
        except Exception as cb_error:
            logger.error(f"Failed to update circuit breaker for {service_key}: {cb_error}")
        
        # Mark service as unavailable if error count exceeds threshold
        if self.service_status[service_key]['error_count'] >= 5:
            self.service_status[service_key]['available'] = False
            logger.warning(f"Service {service_key} marked as unavailable due to repeated failures")
    
    def _mark_service_success(self, service_type: ServiceType) -> None:
        """
        Mark a service as successful, resetting error counts.
        
        Args:
            service_type: Type of service that succeeded
        """
        service_key = service_type.value
        
        if service_key in self.service_status:
            self.service_status[service_key]['available'] = True
            self.service_status[service_key]['error_count'] = 0
            self.service_status[service_key]['last_success'] = datetime.now(timezone.utc)
        
        # Update enhanced circuit breaker
        try:
            circuit_breaker = get_circuit_breaker(service_key)
            circuit_breaker.record_success()
        except Exception as cb_error:
            logger.error(f"Failed to update circuit breaker for {service_key}: {cb_error}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Get current status of all monitored services.
        
        Returns:
            Dictionary with service status information
        """
        # Get circuit breaker statuses
        circuit_breaker_statuses = get_all_circuit_breaker_statuses()
        
        return {
            'services': self.service_status,
            'circuit_breakers': circuit_breaker_statuses,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_health': all(
                status['available'] for status in self.service_status.values()
            )
        }
    
    def log_error_with_context(
        self,
        error: Exception,
        context: Dict[str, Any],
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        actionable_info: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Log error with comprehensive context and actionable information.
        
        Args:
            error: The error to log
            context: Context information
            severity: Error severity level
            actionable_info: Actionable information for debugging
        """
        try:
            error_context = create_error_context(error, **context)
            
            log_data = {
                'error_handler': 'comprehensive_logging',
                'error_context': error_context,
                'severity': severity.value,
                'stack_trace': traceback.format_exc(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            if actionable_info:
                log_data['actionable_info'] = actionable_info
            
            # Log at appropriate level based on severity
            if severity == ErrorSeverity.CRITICAL:
                logger.critical("Critical error detected", extra=log_data)
            elif severity == ErrorSeverity.HIGH:
                logger.error("High severity error detected", extra=log_data)
            elif severity == ErrorSeverity.MEDIUM:
                logger.warning("Medium severity error detected", extra=log_data)
            else:
                logger.info("Low severity error detected", extra=log_data)
                
        except Exception as logging_error:
            # Fallback logging if structured logging fails
            logger.error(f"Failed to log error with context: {logging_error}")
            logger.error(f"Original error: {error}")


# Global error handler instance
error_handler = ErrorHandler()


# Convenience decorators
def isolate_analytics_errors(func: Callable) -> Callable:
    """Decorator to isolate analytics errors from main processing."""
    return error_handler.with_analytics_isolation(func)


def with_bedrock_degradation(func: Callable) -> Callable:
    """Decorator to provide graceful degradation for Bedrock failures."""
    return error_handler.with_graceful_degradation(ServiceType.BEDROCK)(func)


def with_database_isolation(func: Callable) -> Callable:
    """Decorator to provide isolation for database operations."""
    return error_handler.with_graceful_degradation(ServiceType.DYNAMODB)(func)