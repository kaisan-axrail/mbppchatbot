"""
Unit tests for enhanced error handling and isolation system.

This module tests the comprehensive error handling capabilities including
analytics error isolation, Bedrock service graceful degradation, and
actionable error logging.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from shared.error_handler import (
    ErrorHandler,
    ErrorSeverity,
    ServiceType,
    isolate_analytics_errors,
    with_bedrock_degradation
)
from shared.exceptions import (
    BedrockError,
    DatabaseError,
    StrandClientError,
    ChatbotError
)


class TestErrorHandler:
    """Test cases for the ErrorHandler class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_handle_analytics_error_isolation(self):
        """Test that analytics errors are properly isolated."""
        # Create a mock analytics error
        analytics_error = DatabaseError("DynamoDB connection failed", "DYNAMODB_ERROR")
        context = {
            'session_id': 'test-session-123',
            'operation': 'track_language_detection'
        }
        
        # Handle the analytics error
        result = self.error_handler.handle_analytics_error(
            analytics_error, 
            context, 
            continue_processing=True
        )
        
        # Verify that processing continues
        assert result is True
        
        # Verify service status was updated
        assert ServiceType.ANALYTICS.value in self.error_handler.service_status
        assert self.error_handler.service_status[ServiceType.ANALYTICS.value]['error_count'] == 1
    
    def test_handle_bedrock_error_with_fallback(self):
        """Test Bedrock error handling with fallback response."""
        # Create a mock Bedrock error
        bedrock_error = BedrockError("ValidationException: Model not found", "VALIDATION_ERROR")
        context = {
            'model_attempts': ['inference_profile_arn'],
            'message_count': 1
        }
        
        # Handle the Bedrock error
        result = self.error_handler.handle_bedrock_error(
            bedrock_error,
            context,
            fallback_enabled=True
        )
        
        # Verify error handling result
        assert result['success'] is False
        assert 'fallback_response' in result
        assert 'user_message' in result
        
        # Verify fallback response structure
        fallback_response = result['fallback_response']
        assert 'content' in fallback_response
        assert fallback_response['is_fallback'] is True
        assert 'error_type' in fallback_response
    
    def test_handle_database_error_critical_operation(self):
        """Test database error handling for critical operations."""
        # Create a mock database error
        db_error = DatabaseError("Float types are not supported", "DYNAMODB_TYPE_ERROR")
        context = {
            'session_id': 'test-session-456',
            'table_name': 'analytics-table'
        }
        
        # Handle the database error as critical
        result = self.error_handler.handle_database_error(
            db_error,
            context,
            operation='store_session',
            critical=True
        )
        
        # Verify error handling result
        assert result['success'] is False
        assert result['critical'] is True
        assert result['operation'] == 'store_session'
        assert 'user_message' in result
    
    def test_bedrock_error_severity_determination(self):
        """Test Bedrock error severity determination."""
        # Test ValidationException (high severity)
        validation_error = BedrockError("ValidationException: Invalid model", "VALIDATION_ERROR")
        severity = self.error_handler._determine_bedrock_error_severity(validation_error)
        assert severity == ErrorSeverity.HIGH
        
        # Test AccessDeniedException (critical severity)
        access_error = BedrockError("AccessDeniedException: Forbidden", "ACCESS_DENIED")
        severity = self.error_handler._determine_bedrock_error_severity(access_error)
        assert severity == ErrorSeverity.CRITICAL
        
        # Test ThrottlingException (medium severity)
        throttle_error = BedrockError("ThrottlingException: Rate limit exceeded", "THROTTLING")
        severity = self.error_handler._determine_bedrock_error_severity(throttle_error)
        assert severity == ErrorSeverity.MEDIUM
    
    def test_actionable_info_generation(self):
        """Test generation of actionable debugging information."""
        # Test Bedrock ValidationException
        validation_error = BedrockError("ValidationException: Model not found", "VALIDATION_ERROR")
        actionable_info = self.error_handler._get_bedrock_actionable_info(validation_error)
        
        assert 'issue' in actionable_info
        assert 'action' in actionable_info
        assert 'priority' in actionable_info
        assert actionable_info['priority'] == 'high'
        
        # Test database float type error
        float_error = DatabaseError("Float types are not supported", "DYNAMODB_TYPE_ERROR")
        actionable_info = self.error_handler._get_database_actionable_info(float_error, 'put_item')
        
        assert 'Decimal' in actionable_info['action']
        assert actionable_info['priority'] == 'high'
    
    def test_service_status_tracking(self):
        """Test service status tracking and updates."""
        # Initial status should show all services as available
        status = self.error_handler.get_service_status()
        assert status['overall_health'] is True
        
        # Simulate multiple Bedrock errors
        bedrock_error = BedrockError("Service unavailable", "SERVICE_ERROR")
        for _ in range(6):  # Exceed threshold of 5
            self.error_handler._update_service_status(ServiceType.BEDROCK, bedrock_error)
        
        # Check that service is marked as unavailable
        status = self.error_handler.get_service_status()
        assert status['services'][ServiceType.BEDROCK.value]['available'] is False
        assert status['overall_health'] is False
        
        # Mark service as successful to reset status
        self.error_handler._mark_service_success(ServiceType.BEDROCK)
        status = self.error_handler.get_service_status()
        assert status['services'][ServiceType.BEDROCK.value]['available'] is True
        assert status['services'][ServiceType.BEDROCK.value]['error_count'] == 0


class TestErrorHandlingDecorators:
    """Test cases for error handling decorators."""
    
    def test_isolate_analytics_errors_decorator(self):
        """Test the analytics error isolation decorator."""
        
        @isolate_analytics_errors
        def failing_analytics_function():
            raise DatabaseError("Analytics tracking failed", "ANALYTICS_ERROR")
        
        # Function should return None instead of raising exception
        result = failing_analytics_function()
        assert result is None
    
    def test_isolate_analytics_errors_success(self):
        """Test analytics isolation decorator with successful function."""
        
        @isolate_analytics_errors
        def successful_analytics_function():
            return "analytics_tracked"
        
        # Function should return normal result
        result = successful_analytics_function()
        assert result == "analytics_tracked"
    
    @pytest.mark.asyncio
    async def test_bedrock_degradation_decorator(self):
        """Test Bedrock graceful degradation decorator."""
        error_handler = ErrorHandler()
        
        @error_handler.with_graceful_degradation(ServiceType.BEDROCK)
        def failing_bedrock_function():
            raise BedrockError("Model unavailable", "MODEL_UNAVAILABLE")
        
        # Function should return error handling result
        result = failing_bedrock_function()
        assert isinstance(result, dict)
        assert 'success' in result
        assert result['success'] is False


class TestIntegratedErrorHandling:
    """Test cases for integrated error handling scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_handler = ErrorHandler()
    
    def test_analytics_error_does_not_interrupt_main_processing(self):
        """Test that analytics errors don't interrupt main request processing."""
        
        class MockChatbotEngine:
            def __init__(self):
                self.analytics_failed = False
                self.main_processing_completed = False
            
            def process_message(self, message):
                # Simulate analytics failure
                try:
                    self._track_analytics()
                except Exception as e:
                    self.error_handler.handle_analytics_error(
                        e, {'operation': 'track_message'}, continue_processing=True
                    )
                    self.analytics_failed = True
                
                # Main processing should continue
                self.main_processing_completed = True
                return "Response generated successfully"
            
            def _track_analytics(self):
                raise DatabaseError("Analytics DB unavailable", "DB_ERROR")
        
        # Test the scenario
        engine = MockChatbotEngine()
        engine.error_handler = self.error_handler
        
        result = engine.process_message("Hello")
        
        # Verify that main processing completed despite analytics failure
        assert engine.analytics_failed is True
        assert engine.main_processing_completed is True
        assert result == "Response generated successfully"
    
    def test_bedrock_fallback_response_generation(self):
        """Test fallback response generation for Bedrock failures."""
        # Test ValidationException fallback
        validation_error = BedrockError("ValidationException: Model not supported", "VALIDATION_ERROR")
        context = {'model_attempts': ['inference_profile']}
        
        result = self.error_handler.handle_bedrock_error(validation_error, context, fallback_enabled=True)
        fallback_response = result['fallback_response']
        
        # Verify fallback response contains appropriate message
        content = fallback_response['content'][0]['text']
        assert 'configuration issue' in content.lower()
        assert fallback_response['is_fallback'] is True
        
        # Test ThrottlingException fallback
        throttle_error = BedrockError("ThrottlingException: Rate limit exceeded", "THROTTLING")
        result = self.error_handler.handle_bedrock_error(throttle_error, context, fallback_enabled=True)
        fallback_response = result['fallback_response']
        
        content = fallback_response['content'][0]['text']
        assert 'many requests' in content.lower()
    
    def test_comprehensive_error_logging(self):
        """Test comprehensive error logging with context and actionable information."""
        with patch('shared.error_handler.logger') as mock_logger:
            # Test critical error logging
            critical_error = BedrockError("AccessDeniedException: Forbidden", "ACCESS_DENIED")
            context = {
                'session_id': 'test-session',
                'operation': 'generate_response'
            }
            actionable_info = {
                'issue': 'Permission denied',
                'action': 'Check IAM roles',
                'priority': 'critical'
            }
            
            self.error_handler.log_error_with_context(
                critical_error,
                context,
                ErrorSeverity.CRITICAL,
                actionable_info
            )
            
            # Verify critical logging was called
            mock_logger.critical.assert_called_once()
            
            # Verify log data structure
            call_args = mock_logger.critical.call_args
            log_data = call_args[1]['extra']
            
            assert 'error_context' in log_data
            assert 'actionable_info' in log_data
            assert log_data['severity'] == ErrorSeverity.CRITICAL.value
            assert 'stack_trace' in log_data


if __name__ == '__main__':
    pytest.main([__file__])