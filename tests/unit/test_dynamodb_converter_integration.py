"""
Integration tests for DynamoDB type converter with analytics tracker.

Tests the integration between the DynamoDB type converter and the analytics
tracking system to ensure float values are properly converted before storage.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from datetime import datetime

from shared.dynamodb_converter import DynamoDBTypeConverter, prepare_item_for_dynamodb
from shared.analytics_tracker import AnalyticsTracker, EventType
from shared.models import QueryType


class TestDynamoDBConverterIntegration:
    """Integration tests for DynamoDB converter with analytics tracker."""
    
    @pytest.fixture
    def mock_analytics_tracker(self):
        """Create a mock analytics tracker for testing."""
        with patch('shared.analytics_tracker.boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            tracker = AnalyticsTracker(
                table_name='test-analytics-table',
                region_name='us-east-1'
            )
            tracker.table = mock_table
            return tracker, mock_table
    
    def test_track_language_detection_with_converter(self, mock_analytics_tracker):
        """Test language detection tracking with float-to-Decimal conversion."""
        tracker, mock_table = mock_analytics_tracker
        
        # Simulate tracking language detection with float confidence
        session_id = 'test-session-123'
        detected_language = 'en'
        confidence = 0.95  # This is a float that gets automatically converted
        user_text = 'Hello, how are you?'
        context = {'additional_score': 0.88}  # Additional float to test context conversion
        
        # Mock the put_item method to capture the item being stored
        mock_table.put_item = Mock()
        
        # Track the event
        result = tracker.track_language_detection(
            session_id=session_id,
            detected_language=detected_language,
            confidence=confidence,
            user_text=user_text,
            context=context
        )
        
        # Verify the method succeeded
        assert result is True
        
        # Verify put_item was called
        assert mock_table.put_item.called
        
        # Get the item that was stored
        call_args = mock_table.put_item.call_args
        stored_item = call_args[1]['Item']  # kwargs['Item']
        
        # The confidence should now be automatically converted to Decimal
        details = stored_item['details']
        assert 'confidence' in details
        assert isinstance(details['confidence'], Decimal)
        assert details['confidence'] == Decimal('0.95')
        
        # Verify context floats were also converted
        assert isinstance(details['additional_score'], Decimal)
        assert details['additional_score'] == Decimal('0.88')
        
        # Verify other fields are preserved correctly
        assert details['detected_language'] == 'en'
        assert details['text_length'] == len(user_text)
        assert details['is_supported'] is True
        assert details['event_subtype'] == 'language_detection'
    
    def test_track_sentiment_analysis_with_converter(self, mock_analytics_tracker):
        """Test sentiment analysis tracking with float-to-Decimal conversion."""
        tracker, mock_table = mock_analytics_tracker
        
        # Simulate tracking sentiment analysis with float scores
        session_id = 'test-session-456'
        sentiment = 'POSITIVE'
        confidence = 0.87
        sentiment_scores = {
            'positive': 0.8,
            'negative': 0.1,
            'neutral': 0.1,
            'mixed': 0.0
        }
        context = {'processing_time': 123.45}  # Additional float to test context conversion
        
        # Mock the put_item method
        mock_table.put_item = Mock()
        
        # Track the event
        result = tracker.track_sentiment_analysis(
            session_id=session_id,
            sentiment=sentiment,
            confidence=confidence,
            sentiment_scores=sentiment_scores,
            context=context
        )
        
        # Verify the method succeeded
        assert result is True
        
        # Get the stored item - should already be converted
        call_args = mock_table.put_item.call_args
        stored_item = call_args[1]['Item']
        details = stored_item['details']
        
        # Verify all float values were automatically converted to Decimal
        assert isinstance(details['confidence'], Decimal)
        assert isinstance(details['sentiment_scores']['positive'], Decimal)
        assert isinstance(details['sentiment_scores']['negative'], Decimal)
        assert isinstance(details['sentiment_scores']['neutral'], Decimal)
        assert isinstance(details['sentiment_scores']['mixed'], Decimal)
        
        # Verify context floats were also converted
        assert isinstance(details['processing_time'], Decimal)
        assert details['processing_time'] == Decimal('123.45')
        
        # Verify values are correct
        assert details['confidence'] == Decimal('0.87')
        assert details['sentiment_scores']['positive'] == Decimal('0.8')
        assert details['sentiment_scores']['negative'] == Decimal('0.1')
        assert details['sentiment_scores']['neutral'] == Decimal('0.1')
        assert details['sentiment_scores']['mixed'] == Decimal('0.0')
        
        # Verify other fields are preserved
        assert details['sentiment'] == 'POSITIVE'
        assert details['requires_attention'] is False
        assert details['priority'] == 'low'
        assert details['event_subtype'] == 'sentiment_analysis'
    
    def test_track_multilingual_interaction_with_converter(self, mock_analytics_tracker):
        """Test multilingual interaction tracking with float-to-Decimal conversion."""
        tracker, mock_table = mock_analytics_tracker
        
        # Simulate tracking multilingual interaction
        session_id = 'test-session-789'
        user_language = 'ms'
        response_language = 'ms'
        language_confidence = 0.92
        sentiment_data = {
            'sentiment': 'POSITIVE',
            'confidence': 0.85,
            'scores': {
                'positive': 0.7,
                'negative': 0.2,
                'neutral': 0.1
            }
        }
        context = {'response_time': 456.78}  # Additional float to test context conversion
        
        # Mock the put_item method
        mock_table.put_item = Mock()
        
        # Track the event
        result = tracker.track_multilingual_interaction(
            session_id=session_id,
            user_language=user_language,
            response_language=response_language,
            language_confidence=language_confidence,
            sentiment_data=sentiment_data,
            context=context
        )
        
        # Verify the method succeeded
        assert result is True
        
        # Get the stored item - should already be converted
        call_args = mock_table.put_item.call_args
        stored_item = call_args[1]['Item']
        details = stored_item['details']
        
        # Verify float conversions were done automatically
        assert isinstance(details['language_confidence'], Decimal)
        assert isinstance(details['sentiment_data']['confidence'], Decimal)
        assert isinstance(details['sentiment_data']['scores']['positive'], Decimal)
        assert isinstance(details['sentiment_data']['scores']['negative'], Decimal)
        assert isinstance(details['sentiment_data']['scores']['neutral'], Decimal)
        
        # Verify context floats were also converted
        assert isinstance(details['response_time'], Decimal)
        assert details['response_time'] == Decimal('456.78')
        
        # Verify values are correct
        assert details['language_confidence'] == Decimal('0.92')
        assert details['sentiment_data']['confidence'] == Decimal('0.85')
        assert details['sentiment_data']['scores']['positive'] == Decimal('0.7')
        assert details['sentiment_data']['scores']['negative'] == Decimal('0.2')
        assert details['sentiment_data']['scores']['neutral'] == Decimal('0.1')
        
        # Verify other fields are preserved
        assert details['user_language'] == 'ms'
        assert details['response_language'] == 'ms'
        assert details['is_multilingual'] is True
        assert details['language_match'] is True
        assert details['event_subtype'] == 'multilingual_interaction'
    
    def test_prepare_analytics_data_integration(self):
        """Test the prepare_analytics_data method with realistic analytics data."""
        # Simulate a complete analytics event with various float values
        event_data = {
            'eventType': 'query',
            'sessionId': 'session-integration-test',
            'timestamp': datetime.now().isoformat(),
            'details': {
                'query_type': 'rag',
                'success': True,
                'response_time_ms': 1250,
                'confidence_scores': {
                    'language_detection': 0.95,
                    'sentiment_analysis': 0.87,
                    'intent_classification': 0.92
                },
                'performance_metrics': {
                    'embedding_time': 45.7,
                    'retrieval_time': 123.4,
                    'generation_time': 567.8
                },
                'multilingual_data': {
                    'detected_language': 'en',
                    'confidence': 0.98,
                    'sentiment_scores': {
                        'positive': 0.8,
                        'negative': 0.1,
                        'neutral': 0.1
                    }
                }
            }
        }
        
        # Prepare the data for DynamoDB
        prepared_data = DynamoDBTypeConverter.prepare_analytics_data(event_data)
        
        # Verify the structure is maintained
        assert prepared_data['eventType'] == 'query'
        assert prepared_data['sessionId'] == 'session-integration-test'
        assert 'date' in prepared_data
        
        # Verify all float values were converted to Decimal
        details = prepared_data['details']
        
        # Check confidence scores
        confidence_scores = details['confidence_scores']
        assert isinstance(confidence_scores['language_detection'], Decimal)
        assert isinstance(confidence_scores['sentiment_analysis'], Decimal)
        assert isinstance(confidence_scores['intent_classification'], Decimal)
        
        # Check performance metrics
        performance_metrics = details['performance_metrics']
        assert isinstance(performance_metrics['embedding_time'], Decimal)
        assert isinstance(performance_metrics['retrieval_time'], Decimal)
        assert isinstance(performance_metrics['generation_time'], Decimal)
        
        # Check nested multilingual data
        multilingual_data = details['multilingual_data']
        assert isinstance(multilingual_data['confidence'], Decimal)
        sentiment_scores = multilingual_data['sentiment_scores']
        assert isinstance(sentiment_scores['positive'], Decimal)
        assert isinstance(sentiment_scores['negative'], Decimal)
        assert isinstance(sentiment_scores['neutral'], Decimal)
        
        # Verify values are correct
        assert confidence_scores['language_detection'] == Decimal('0.95')
        assert performance_metrics['embedding_time'] == Decimal('45.7')
        assert multilingual_data['confidence'] == Decimal('0.98')
    
    def test_converter_with_tool_usage_tracking(self, mock_analytics_tracker):
        """Test converter integration with tool usage tracking."""
        tracker, mock_table = mock_analytics_tracker
        
        # Simulate tool usage with execution time (float)
        session_id = 'tool-test-session'
        tool_name = 'document_search'
        execution_time_ms = 234.5  # Float value
        tool_parameters = {
            'query': 'test query',
            'threshold': 0.75,  # Float threshold
            'max_results': 10
        }
        
        # Mock the put_item method
        mock_table.put_item = Mock()
        
        # Track tool usage
        result = tracker.track_tool_usage(
            session_id=session_id,
            tool_name=tool_name,
            execution_time_ms=execution_time_ms,
            tool_parameters=tool_parameters,
            success=True
        )
        
        # Verify success (returns event ID string)
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Get and convert the stored item
        call_args = mock_table.put_item.call_args
        stored_item = call_args[1]['Item']
        converted_item = prepare_item_for_dynamodb(stored_item)
        
        # Verify float conversions in tool parameters
        converted_details = converted_item['details']
        assert isinstance(converted_details['execution_time_ms'], Decimal)
        assert isinstance(converted_details['tool_parameters']['threshold'], Decimal)
        
        # Verify values
        assert converted_details['execution_time_ms'] == Decimal('234.5')
        assert converted_details['tool_parameters']['threshold'] == Decimal('0.75')
        assert converted_details['tool_parameters']['max_results'] == 10  # int unchanged
    
    def test_validation_after_conversion(self):
        """Test that converted items pass DynamoDB validation."""
        # Create test data with various float values
        test_data = {
            'id': 'test-item',
            'scores': {
                'accuracy': 0.95,
                'precision': 0.87,
                'recall': 0.92
            },
            'metrics': [1.1, 2.2, 3.3],
            'metadata': {
                'version': '1.0',
                'confidence': 0.99,
                'nested': {
                    'deep_score': 0.88
                }
            }
        }
        
        # Convert the data
        converted_data = prepare_item_for_dynamodb(test_data)
        
        # Validate that the converted data is DynamoDB-compatible
        is_valid = DynamoDBTypeConverter.validate_dynamodb_item(converted_data)
        assert is_valid is True
        
        # Verify specific conversions
        assert isinstance(converted_data['scores']['accuracy'], Decimal)
        assert isinstance(converted_data['metrics'][0], Decimal)
        assert isinstance(converted_data['metadata']['confidence'], Decimal)
        assert isinstance(converted_data['metadata']['nested']['deep_score'], Decimal)


if __name__ == '__main__':
    pytest.main([__file__])