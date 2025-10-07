"""
Custom exceptions for the chatbot system.

This module provides a comprehensive set of custom exception classes following
clean code naming conventions and providing user-friendly error messages.
"""

from typing import Optional, Dict, Any


class ChatbotError(Exception):
    """Base exception for chatbot system errors."""
    
    def __init__(self, message: str, code: str, user_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.user_message = user_message or self._generate_user_friendly_message(message, code)
    
    def _generate_user_friendly_message(self, message: str, code: str) -> str:
        """Generate a user-friendly error message based on the error code."""
        user_friendly_messages = {
            "SESSION_NOT_FOUND": "Your session has expired. Please refresh the page to start a new conversation.",
            "MODEL_UNAVAILABLE": "I'm temporarily unavailable. Please try again in a few moments.",
            "MCP_TOOL_ERROR": "I encountered an issue while processing your request. Please try again.",
            "VALIDATION_ERROR": "There was an issue with your request. Please check your input and try again.",
            "DATABASE_ERROR": "I'm experiencing technical difficulties. Please try again shortly.",
            "TIMEOUT_ERROR": "Your request is taking longer than expected. Please try again.",
            "RATE_LIMIT_ERROR": "I'm currently handling many requests. Please wait a moment and try again.",
            "AUTHENTICATION_ERROR": "There was an authentication issue. Please refresh the page.",
            "CONFIGURATION_ERROR": "I'm experiencing a configuration issue. Please contact support if this persists.",
            "NETWORK_ERROR": "I'm having trouble connecting to external services. Please try again.",
        }
        return user_friendly_messages.get(code, "I encountered an unexpected error. Please try again.")


# Session-related errors
class SessionNotFoundError(ChatbotError):
    """Exception raised when a session is not found."""
    
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session {session_id} not found", 
            "SESSION_NOT_FOUND"
        )
        self.session_id = session_id


class SessionExpiredError(ChatbotError):
    """Exception raised when a session has expired."""
    
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session {session_id} has expired", 
            "SESSION_EXPIRED"
        )
        self.session_id = session_id


class SessionManagerError(ChatbotError):
    """Exception raised for session management errors."""
    
    def __init__(self, message: str) -> None:
        super().__init__(
            f"Session manager error: {message}", 
            "SESSION_MANAGER_ERROR"
        )


# Model and AI service errors
class ModelUnavailableError(ChatbotError):
    """Exception raised when the language model is unavailable."""
    
    def __init__(self, model_name: Optional[str] = None) -> None:
        message = f"Model {model_name} is unavailable" if model_name else "Language model is unavailable"
        super().__init__(message, "MODEL_UNAVAILABLE")
        self.model_name = model_name


class StrandClientError(ChatbotError):
    """Exception raised for Strand SDK client errors."""
    
    def __init__(self, message: str, error_code: str = "STRAND_ERROR") -> None:
        super().__init__(f"Strand client error: {message}", error_code)


class BedrockError(ChatbotError):
    """Exception raised for AWS Bedrock service errors."""
    
    def __init__(self, message: str, error_code: str = "BEDROCK_ERROR") -> None:
        super().__init__(f"Bedrock service error: {message}", error_code)


# MCP-related errors
class McpToolError(ChatbotError):
    """Exception raised when an MCP tool fails."""
    
    def __init__(self, tool_name: str, message: str) -> None:
        super().__init__(
            f"MCP tool {tool_name} failed: {message}", 
            "MCP_TOOL_ERROR"
        )
        self.tool_name = tool_name


class McpHandlerError(ChatbotError):
    """Exception raised for MCP handler errors."""
    
    def __init__(self, message: str, error_code: str = "MCP_HANDLER_ERROR") -> None:
        super().__init__(f"MCP handler error: {message}", error_code)


class McpCommunicationError(McpHandlerError):
    """Exception raised for MCP communication errors."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "MCP_COMMUNICATION_ERROR")


# RAG-related errors
class RagHandlerError(ChatbotError):
    """Exception raised for RAG handler errors."""
    
    def __init__(self, message: str, error_code: str = "RAG_ERROR") -> None:
        super().__init__(f"RAG handler error: {message}", error_code)


class DocumentSearchError(RagHandlerError):
    """Exception raised when document search fails."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "DOCUMENT_SEARCH_ERROR")


class EmbeddingGenerationError(RagHandlerError):
    """Exception raised when embedding generation fails."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "EMBEDDING_GENERATION_ERROR")


# Database-related errors
class DatabaseError(ChatbotError):
    """Exception raised for database operation errors."""
    
    def __init__(self, message: str, error_code: str = "DATABASE_ERROR") -> None:
        super().__init__(f"Database error: {message}", error_code)


class DynamoDbError(DatabaseError):
    """Exception raised for DynamoDB operation errors."""
    
    def __init__(self, message: str, operation: Optional[str] = None) -> None:
        error_message = f"DynamoDB {operation} error: {message}" if operation else f"DynamoDB error: {message}"
        super().__init__(error_message, "DYNAMODB_ERROR")
        self.operation = operation


class OpenSearchError(DatabaseError):
    """Exception raised for OpenSearch operation errors."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message, "OPENSEARCH_ERROR")


# Validation and input errors
class ValidationError(ChatbotError):
    """Exception raised for input validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None) -> None:
        error_message = f"Validation error for {field}: {message}" if field else f"Validation error: {message}"
        super().__init__(error_message, "VALIDATION_ERROR")
        self.field = field


class SchemaValidationError(ValidationError):
    """Exception raised for schema validation errors."""
    
    def __init__(self, message: str, schema_path: Optional[str] = None) -> None:
        error_message = f"Schema validation error at {schema_path}: {message}" if schema_path else f"Schema validation error: {message}"
        super().__init__(error_message, "SCHEMA_VALIDATION_ERROR")
        self.schema_path = schema_path


# Network and service errors
class NetworkError(ChatbotError):
    """Exception raised for network-related errors."""
    
    def __init__(self, message: str, service: Optional[str] = None) -> None:
        error_message = f"Network error connecting to {service}: {message}" if service else f"Network error: {message}"
        super().__init__(error_message, "NETWORK_ERROR")
        self.service = service


class TimeoutError(ChatbotError):
    """Exception raised when operations timeout."""
    
    def __init__(self, operation: str, timeout_seconds: Optional[float] = None) -> None:
        message = f"Operation '{operation}' timed out"
        if timeout_seconds:
            message += f" after {timeout_seconds} seconds"
        super().__init__(message, "TIMEOUT_ERROR")
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class RateLimitError(ChatbotError):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(self, service: str, retry_after: Optional[int] = None) -> None:
        message = f"Rate limit exceeded for {service}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, "RATE_LIMIT_ERROR")
        self.service = service
        self.retry_after = retry_after


# Configuration and authentication errors
class ConfigurationError(ChatbotError):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None) -> None:
        error_message = f"Configuration error for {config_key}: {message}" if config_key else f"Configuration error: {message}"
        super().__init__(error_message, "CONFIGURATION_ERROR")
        self.config_key = config_key


class AuthenticationError(ChatbotError):
    """Exception raised for authentication errors."""
    
    def __init__(self, message: str, service: Optional[str] = None) -> None:
        error_message = f"Authentication error for {service}: {message}" if service else f"Authentication error: {message}"
        super().__init__(error_message, "AUTHENTICATION_ERROR")
        self.service = service


class SecretNotFoundError(AuthenticationError):
    """Exception raised when required secrets are not found."""
    
    def __init__(self, secret_name: str) -> None:
        super().__init__(f"Secret {secret_name} not found", "SECRET_NOT_FOUND")
        self.secret_name = secret_name


# Chatbot engine errors
class ChatbotEngineError(ChatbotError):
    """Exception raised for chatbot engine errors."""
    
    def __init__(self, message: str, error_code: str = "CHATBOT_ERROR") -> None:
        super().__init__(f"Chatbot engine error: {message}", error_code)


class QueryProcessingError(ChatbotEngineError):
    """Exception raised when query processing fails."""
    
    def __init__(self, message: str, query_type: Optional[str] = None) -> None:
        error_message = f"Query processing error for {query_type}: {message}" if query_type else f"Query processing error: {message}"
        super().__init__(error_message, "QUERY_PROCESSING_ERROR")
        self.query_type = query_type


# Lambda and AWS service errors
class LambdaExecutionError(ChatbotError):
    """Exception raised for Lambda execution errors."""
    
    def __init__(self, function_name: str, message: str) -> None:
        super().__init__(
            f"Lambda function {function_name} execution error: {message}", 
            "LAMBDA_EXECUTION_ERROR"
        )
        self.function_name = function_name


class AwsServiceError(ChatbotError):
    """Exception raised for general AWS service errors."""
    
    def __init__(self, service: str, message: str, error_code: Optional[str] = None) -> None:
        super().__init__(
            f"AWS {service} error: {message}", 
            error_code or "AWS_SERVICE_ERROR"
        )
        self.service = service


# Utility functions for error handling
def get_user_friendly_message(error: Exception) -> str:
    """
    Extract user-friendly message from any exception.
    
    Args:
        error: Exception instance
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, ChatbotError):
        return error.user_message
    
    # Handle common AWS errors
    error_str = str(error).lower()
    if "timeout" in error_str:
        return "Your request is taking longer than expected. Please try again."
    elif "rate limit" in error_str or "throttl" in error_str:
        return "I'm currently handling many requests. Please wait a moment and try again."
    elif "unauthorized" in error_str or "forbidden" in error_str:
        return "There was an authentication issue. Please refresh the page."
    elif "not found" in error_str:
        return "The requested resource was not found. Please try again."
    elif "service unavailable" in error_str or "internal server error" in error_str:
        return "I'm experiencing technical difficulties. Please try again shortly."
    else:
        return "I encountered an unexpected error. Please try again."


def create_error_context(error: Exception, **kwargs) -> Dict[str, Any]:
    """
    Create error context dictionary for logging and monitoring.
    
    Args:
        error: Exception instance
        **kwargs: Additional context information
        
    Returns:
        Dictionary containing error context
    """
    context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "user_friendly_message": get_user_friendly_message(error),
        **kwargs
    }
    
    if isinstance(error, ChatbotError):
        context["error_code"] = error.code
        
        # Add specific error attributes
        if hasattr(error, 'session_id'):
            context["session_id"] = error.session_id
        if hasattr(error, 'tool_name'):
            context["tool_name"] = error.tool_name
        if hasattr(error, 'operation'):
            context["operation"] = error.operation
        if hasattr(error, 'service'):
            context["service"] = error.service
    
    return context