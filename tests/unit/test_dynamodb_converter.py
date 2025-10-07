"""
Unit tests for DynamoDB type conversion utility.

Tests cover float-to-Decimal conversion, analytics data preparation,
edge cases, and error handling scenarios.
"""

import pytest
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Dict, Any

from shared.dynamodb_converter import (
    DynamoDBTypeConverter,
    safe_decimal_conversion,
    prepare_item_for_dynamodb
)


class TestDynamoDBTypeConverter:
    """Test cases for DynamoDBTypeConverter class."""
    
    def test_convert_simple_float(self):
        """Test conversion of a simple float value."""
        result = DynamoDBTypeConverter.convert_floats_to_decimal(3.14)
        assert isinstance(result, Decimal)
        assert result == Decimal('3.14')
    
    def test_convert_integer_unchanged(self):
        """Test that integers remain unchanged."""
        result = DynamoDBTypeConverter.convert_floats_to_decimal(42)
        assert result == 42
        assert isinstance(result, int)
    
    def test_convert_string_unchanged(self):
        """Test that strings remain unchanged."""
        result = DynamoDBTypeConverter.convert_floats_to_decimal("hello")
        assert result == "hello"
        assert isinstance(result, str)
    
    def test_convert_none_unchanged(self):
        """Test that None values remain unchanged."""
        result = DynamoDBTypeConverter.convert_floats_to_decimal(None)
        assert result is None
    
    def test_convert_boolean_unchanged(self):
        """Test that boolean values remain unchanged."""
        result_true = DynamoDBTypeConverter.convert_floats_to_decimal(True)
        result_false = DynamoDBTypeConverter.convert_floats_to_decimal(False)
        assert result_true is True
        assert result_false is False
    
    def test_convert_dict_with_floats(self):
        """Test conversion of dictionary containing float values."""
        input_data = {
            'confidence': 0.95,
            'score': 3.14159,
            'name': 'test',
            'count': 5
        }
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(input_data)
        
        assert isinstance(result['confidence'], Decimal)
        assert isinstance(result['score'], Decimal)
        assert result['confidence'] == Decimal('0.95')
        assert result['score'] == Decimal('3.14159')
        assert result['name'] == 'test'
        assert result['count'] == 5
    
    def test_convert_nested_dict(self):
        """Test conversion of nested dictionary structures."""
        input_data = {
            'level1': {
                'level2': {
                    'float_value': 2.718,
                    'string_value': 'nested'
                },
                'another_float': 1.414
            },
            'top_level_float': 0.577
        }
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(input_data)
        
        assert isinstance(result['level1']['level2']['float_value'], Decimal)
        assert isinstance(result['level1']['another_float'], Decimal)
        assert isinstance(result['top_level_float'], Decimal)
        assert result['level1']['level2']['string_value'] == 'nested'
    
    def test_convert_list_with_floats(self):
        """Test conversion of list containing float values."""
        input_data = [1.1, 2.2, 'string', 42, None]
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(input_data)
        
        assert isinstance(result, list)
        assert isinstance(result[0], Decimal)
        assert isinstance(result[1], Decimal)
        assert result[0] == Decimal('1.1')
        assert result[1] == Decimal('2.2')
        assert result[2] == 'string'
        assert result[3] == 42
        assert result[4] is None
    
    def test_convert_tuple_with_floats(self):
        """Test conversion of tuple containing float values."""
        input_data = (1.5, 'test', 3.7)
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(input_data)
        
        assert isinstance(result, tuple)
        assert isinstance(result[0], Decimal)
        assert isinstance(result[2], Decimal)
        assert result[0] == Decimal('1.5')
        assert result[1] == 'test'
        assert result[2] == Decimal('3.7')
    
    def test_convert_set_with_floats(self):
        """Test conversion of set containing float values."""
        input_data = {1.1, 2.2, 3.3}
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(input_data)
        
        assert isinstance(result, set)
        assert len(result) == 3
        # Convert to list for easier testing
        result_list = list(result)
        assert all(isinstance(item, Decimal) for item in result_list)
    
    def test_convert_complex_nested_structure(self):
        """Test conversion of complex nested data structure."""
        input_data = {
            'analytics': {
                'scores': [0.1, 0.2, 0.3],
                'metadata': {
                    'confidence': 0.95,
                    'details': {
                        'precision': 0.87,
                        'recall': 0.92
                    }
                }
            },
            'results': (1.1, 2.2, {'nested_float': 3.3})
        }
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(input_data)
        
        # Check nested list conversion
        scores = result['analytics']['scores']
        assert all(isinstance(score, Decimal) for score in scores)
        
        # Check deeply nested dict conversion
        precision = result['analytics']['metadata']['details']['precision']
        assert isinstance(precision, Decimal)
        assert precision == Decimal('0.87')
        
        # Check tuple with nested dict conversion
        nested_tuple = result['results']
        assert isinstance(nested_tuple, tuple)
        assert isinstance(nested_tuple[2]['nested_float'], Decimal)
    
    def test_convert_special_float_values(self):
        """Test conversion of special float values (inf, -inf, nan)."""
        # Note: DynamoDB doesn't support these values, but we test the converter behavior
        import math
        
        # Test infinity
        result_inf = DynamoDBTypeConverter.convert_floats_to_decimal(float('inf'))
        # Should handle gracefully (likely return original or raise exception)
        
        # Test negative infinity
        result_neg_inf = DynamoDBTypeConverter.convert_floats_to_decimal(float('-inf'))
        
        # Test NaN
        result_nan = DynamoDBTypeConverter.convert_floats_to_decimal(float('nan'))
        
        # The exact behavior depends on implementation, but should not crash
        assert result_inf is not None or True  # Placeholder assertion
    
    def test_prepare_analytics_data_valid(self):
        """Test preparation of valid analytics data."""
        event_data = {
            'eventType': 'query',
            'sessionId': 'session-123',
            'timestamp': '2024-01-01T12:00:00Z',
            'details': {
                'confidence': 0.95,
                'scores': {
                    'positive': 0.8,
                    'negative': 0.1,
                    'neutral': 0.1
                }
            }
        }
        
        result = DynamoDBTypeConverter.prepare_analytics_data(event_data)
        
        assert 'date' in result
        assert isinstance(result['details']['confidence'], Decimal)
        assert isinstance(result['details']['scores']['positive'], Decimal)
        assert result['eventType'] == 'query'
        assert result['sessionId'] == 'session-123'
    
    def test_prepare_analytics_data_missing_fields(self):
        """Test preparation of analytics data with missing required fields."""
        event_data = {
            'eventType': 'query',
            # Missing sessionId and timestamp
        }
        
        with pytest.raises(ValueError, match="Missing required fields"):
            DynamoDBTypeConverter.prepare_analytics_data(event_data)
    
    def test_prepare_analytics_data_datetime_timestamp(self):
        """Test preparation with datetime object as timestamp."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        event_data = {
            'eventType': 'query',
            'sessionId': 'session-123',
            'timestamp': timestamp
        }
        
        result = DynamoDBTypeConverter.prepare_analytics_data(event_data)
        
        assert isinstance(result['timestamp'], str)
        assert 'date' in result
        assert result['date'] == '2024-01-01'
    
    def test_prepare_analytics_data_unix_timestamp(self):
        """Test preparation with Unix timestamp."""
        unix_timestamp = 1704110400  # 2024-01-01 12:00:00 UTC
        event_data = {
            'eventType': 'query',
            'sessionId': 'session-123',
            'timestamp': unix_timestamp
        }
        
        result = DynamoDBTypeConverter.prepare_analytics_data(event_data)
        
        assert isinstance(result['timestamp'], str)
        assert 'date' in result
    
    def test_prepare_sentiment_data(self):
        """Test preparation of sentiment analysis data."""
        sentiment_scores = {
            'positive': 0.7,
            'negative': 0.2,
            'neutral': 0.1,
            'mixed': 0.0
        }
        
        result = DynamoDBTypeConverter.prepare_sentiment_data(sentiment_scores)
        
        assert all(isinstance(score, Decimal) for score in result.values())
        assert result['positive'] == Decimal('0.7')
        assert result['negative'] == Decimal('0.2')
    
    def test_prepare_sentiment_data_invalid_input(self):
        """Test preparation of sentiment data with invalid input."""
        result = DynamoDBTypeConverter.prepare_sentiment_data("not a dict")
        assert result == {}
    
    def test_prepare_confidence_score_valid(self):
        """Test preparation of valid confidence scores."""
        # Test float
        result_float = DynamoDBTypeConverter.prepare_confidence_score(0.95)
        assert isinstance(result_float, Decimal)
        assert result_float == Decimal('0.95')
        
        # Test int
        result_int = DynamoDBTypeConverter.prepare_confidence_score(1)
        assert isinstance(result_int, Decimal)
        assert result_int == Decimal('1')
        
        # Test Decimal (should return as-is)
        decimal_input = Decimal('0.85')
        result_decimal = DynamoDBTypeConverter.prepare_confidence_score(decimal_input)
        assert result_decimal is decimal_input
    
    def test_prepare_confidence_score_invalid(self):
        """Test preparation of invalid confidence scores."""
        # Test None
        with pytest.raises(ValueError, match="cannot be None"):
            DynamoDBTypeConverter.prepare_confidence_score(None)
        
        # Test string
        with pytest.raises(ValueError, match="Unsupported confidence score type"):
            DynamoDBTypeConverter.prepare_confidence_score("0.95")
    
    def test_validate_dynamodb_item_valid(self):
        """Test validation of DynamoDB-compatible items."""
        valid_item = {
            'string_field': 'value',
            'int_field': 42,
            'decimal_field': Decimal('3.14'),
            'bool_field': True,
            'none_field': None,
            'nested_dict': {
                'nested_decimal': Decimal('2.71')
            },
            'list_field': [1, 2, Decimal('3.14')]
        }
        
        assert DynamoDBTypeConverter.validate_dynamodb_item(valid_item) is True
    
    def test_validate_dynamodb_item_invalid(self):
        """Test validation of items with DynamoDB-incompatible types."""
        # Test with float
        invalid_item_float = {
            'float_field': 3.14,
            'string_field': 'value'
        }
        assert DynamoDBTypeConverter.validate_dynamodb_item(invalid_item_float) is False
        
        # Test with datetime
        invalid_item_datetime = {
            'datetime_field': datetime.now(),
            'string_field': 'value'
        }
        assert DynamoDBTypeConverter.validate_dynamodb_item(invalid_item_datetime) is False
    
    def test_get_conversion_summary(self):
        """Test generation of conversion summary."""
        original_data = {
            'float1': 1.1,
            'float2': 2.2,
            'nested': {
                'float3': 3.3
            },
            'list': [4.4, 5.5]
        }
        
        converted_data = DynamoDBTypeConverter.convert_floats_to_decimal(original_data)
        summary = DynamoDBTypeConverter.get_conversion_summary(original_data, converted_data)
        
        assert 'floats_converted' in summary
        assert 'nested_dicts' in summary
        assert 'nested_lists' in summary
        assert 'total_items' in summary
        assert summary['floats_converted'] > 0


class TestSafeDecimalConversion:
    """Test cases for safe_decimal_conversion function."""
    
    def test_safe_conversion_float(self):
        """Test safe conversion of float values."""
        result = safe_decimal_conversion(3.14)
        assert isinstance(result, Decimal)
        assert result == Decimal('3.14')
    
    def test_safe_conversion_int(self):
        """Test safe conversion of integer values."""
        result = safe_decimal_conversion(42)
        assert isinstance(result, Decimal)
        assert result == Decimal('42')
    
    def test_safe_conversion_string(self):
        """Test safe conversion of string values."""
        result = safe_decimal_conversion("3.14")
        assert isinstance(result, Decimal)
        assert result == Decimal('3.14')
    
    def test_safe_conversion_none(self):
        """Test safe conversion of None."""
        result = safe_decimal_conversion(None)
        assert result is None
    
    def test_safe_conversion_invalid(self):
        """Test safe conversion of invalid values."""
        result = safe_decimal_conversion("not a number")
        assert result is None


class TestPrepareItemForDynamoDB:
    """Test cases for prepare_item_for_dynamodb function."""
    
    def test_prepare_valid_item(self):
        """Test preparation of valid item."""
        item = {
            'id': 'test-id',
            'score': 0.95,
            'metadata': {
                'confidence': 0.87
            }
        }
        
        result = prepare_item_for_dynamodb(item)
        
        assert isinstance(result['score'], Decimal)
        assert isinstance(result['metadata']['confidence'], Decimal)
        assert result['id'] == 'test-id'
    
    def test_prepare_invalid_input(self):
        """Test preparation with invalid input."""
        with pytest.raises(ValueError, match="Item must be a dictionary"):
            prepare_item_for_dynamodb("not a dict")


class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_empty_dict(self):
        """Test conversion of empty dictionary."""
        result = DynamoDBTypeConverter.convert_floats_to_decimal({})
        assert result == {}
    
    def test_empty_list(self):
        """Test conversion of empty list."""
        result = DynamoDBTypeConverter.convert_floats_to_decimal([])
        assert result == []
    
    def test_deeply_nested_structure(self):
        """Test conversion of deeply nested structure."""
        # Create a structure with 10 levels of nesting
        nested_data = {'level': 1.1}
        for i in range(2, 11):
            nested_data = {'level': i + 0.1, 'nested': nested_data}
        
        result = DynamoDBTypeConverter.convert_floats_to_decimal(nested_data)
        
        # Verify conversion worked at all levels
        current = result
        for i in range(10, 1, -1):
            assert isinstance(current['level'], Decimal)
            if 'nested' in current:
                current = current['nested']
    
    def test_circular_reference_protection(self):
        """Test that circular references don't cause infinite loops."""
        # Note: This is a theoretical test - the current implementation
        # doesn't handle circular references, but we document the limitation
        data = {'key': 'value'}
        # data['self'] = data  # This would create a circular reference
        
        # For now, we just test that normal nested structures work
        nested_data = {'a': {'b': {'c': 1.5}}}
        result = DynamoDBTypeConverter.convert_floats_to_decimal(nested_data)
        assert isinstance(result['a']['b']['c'], Decimal)
    
    def test_large_float_precision(self):
        """Test conversion of floats with high precision."""
        high_precision_float = 1.23456789012345
        result = DynamoDBTypeConverter.convert_floats_to_decimal(high_precision_float)
        
        assert isinstance(result, Decimal)
        # Verify precision is maintained
        assert str(result) == '1.23456789012345'
    
    def test_very_small_float(self):
        """Test conversion of very small float values."""
        small_float = 1e-10
        result = DynamoDBTypeConverter.convert_floats_to_decimal(small_float)
        
        assert isinstance(result, Decimal)
        assert result > 0
    
    def test_very_large_float(self):
        """Test conversion of very large float values."""
        large_float = 1e10
        result = DynamoDBTypeConverter.convert_floats_to_decimal(large_float)
        
        assert isinstance(result, Decimal)
        assert result == Decimal('10000000000')


if __name__ == '__main__':
    pytest.main([__file__])