"""
DynamoDB type conversion utility for handling data type compatibility.

This module provides utilities to convert Python data types to DynamoDB-compatible
formats, specifically handling the conversion of float values to Decimal types
which are required for DynamoDB storage operations.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Union, Optional
from datetime import datetime, date


logger = logging.getLogger(__name__)


class DynamoDBTypeConverter:
    """
    Utility class for converting Python data types to DynamoDB-compatible formats.
    
    DynamoDB does not support Python's native float type and requires Decimal
    for numeric values with decimal places. This class provides methods to
    recursively convert data structures containing floats to use Decimal types.
    """
    
    @staticmethod
    def convert_floats_to_decimal(data: Any) -> Any:
        """
        Recursively convert float values to Decimal for DynamoDB compatibility.
        
        This method traverses nested data structures (dicts, lists, tuples) and
        converts any float values to Decimal objects while preserving the
        structure and other data types.
        
        Args:
            data: Input data of any type that may contain float values
            
        Returns:
            Data with all float values converted to Decimal objects
            
        Raises:
            InvalidOperation: If a float value cannot be converted to Decimal
        """
        if isinstance(data, float):
            try:
                # Convert float to string first to avoid precision issues
                return Decimal(str(data))
            except (InvalidOperation, ValueError) as e:
                logger.warning(f"Failed to convert float {data} to Decimal: {e}")
                # Return the original value if conversion fails
                return data
        
        elif isinstance(data, dict):
            return {
                key: DynamoDBTypeConverter.convert_floats_to_decimal(value)
                for key, value in data.items()
            }
        
        elif isinstance(data, (list, tuple)):
            converted_list = [
                DynamoDBTypeConverter.convert_floats_to_decimal(item)
                for item in data
            ]
            # Preserve original type (list or tuple)
            return type(data)(converted_list)
        
        elif isinstance(data, set):
            return {
                DynamoDBTypeConverter.convert_floats_to_decimal(item)
                for item in data
            }
        
        else:
            # Return unchanged for other types (str, int, bool, None, etc.)
            return data
    
    @staticmethod
    def prepare_analytics_data(event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare analytics event data for DynamoDB storage.
        
        This method specifically handles analytics data preparation by:
        1. Converting all float values to Decimal
        2. Ensuring timestamp formats are consistent
        3. Validating required fields
        4. Handling nested data structures in event details
        
        Args:
            event_data: Analytics event data dictionary
            
        Returns:
            Dict[str, Any]: Prepared data ready for DynamoDB storage
            
        Raises:
            ValueError: If required fields are missing
        """
        if not isinstance(event_data, dict):
            raise ValueError("Event data must be a dictionary")
        
        # Validate required fields for analytics events
        required_fields = ['eventType', 'sessionId', 'timestamp']
        missing_fields = [field for field in required_fields if field not in event_data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Create a copy to avoid modifying the original data
        prepared_data = event_data.copy()
        
        # Convert all float values to Decimal
        prepared_data = DynamoDBTypeConverter.convert_floats_to_decimal(prepared_data)
        
        # Ensure timestamp is in ISO format string
        if 'timestamp' in prepared_data:
            timestamp = prepared_data['timestamp']
            if isinstance(timestamp, datetime):
                prepared_data['timestamp'] = timestamp.isoformat()
            elif isinstance(timestamp, (int, float)):
                # Assume Unix timestamp
                dt = datetime.fromtimestamp(timestamp)
                prepared_data['timestamp'] = dt.isoformat()
        
        # Add date field if not present (required for DynamoDB partitioning)
        if 'date' not in prepared_data and 'timestamp' in prepared_data:
            try:
                if isinstance(prepared_data['timestamp'], str):
                    dt = datetime.fromisoformat(prepared_data['timestamp'].replace('Z', '+00:00'))
                    prepared_data['date'] = dt.strftime('%Y-%m-%d')
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to extract date from timestamp: {e}")
                # Use current date as fallback
                prepared_data['date'] = datetime.now().strftime('%Y-%m-%d')
        
        logger.debug(
            "Analytics data prepared for DynamoDB",
            extra={
                'event_type': prepared_data.get('eventType'),
                'session_id': prepared_data.get('sessionId'),
                'has_details': 'details' in prepared_data
            }
        )
        
        return prepared_data
    
    @staticmethod
    def prepare_sentiment_data(sentiment_scores: Dict[str, float]) -> Dict[str, Decimal]:
        """
        Prepare sentiment analysis data for DynamoDB storage.
        
        Converts sentiment score dictionaries (typically containing float values)
        to use Decimal types for DynamoDB compatibility.
        
        Args:
            sentiment_scores: Dictionary of sentiment scores with float values
            
        Returns:
            Dict[str, Decimal]: Sentiment scores with Decimal values
        """
        if not isinstance(sentiment_scores, dict):
            logger.warning("Sentiment scores must be a dictionary")
            return {}
        
        converted_scores = {}
        for sentiment_type, score in sentiment_scores.items():
            if isinstance(score, (int, float)):
                try:
                    converted_scores[sentiment_type] = Decimal(str(score))
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Failed to convert sentiment score {score}: {e}")
                    # Skip invalid scores
                    continue
            else:
                # Keep non-numeric values as-is
                converted_scores[sentiment_type] = score
        
        return converted_scores
    
    @staticmethod
    def prepare_confidence_score(confidence: Union[float, int, Decimal]) -> Decimal:
        """
        Prepare a confidence score for DynamoDB storage.
        
        Converts numeric confidence values to Decimal type with appropriate
        precision for DynamoDB storage.
        
        Args:
            confidence: Confidence score as float, int, or Decimal
            
        Returns:
            Decimal: Confidence score as Decimal
            
        Raises:
            ValueError: If confidence value is invalid
        """
        if confidence is None:
            raise ValueError("Confidence score cannot be None")
        
        if isinstance(confidence, Decimal):
            return confidence
        
        if isinstance(confidence, (int, float)):
            try:
                # Ensure confidence is within valid range [0, 1]
                if not (0 <= confidence <= 1):
                    logger.warning(f"Confidence score {confidence} outside valid range [0, 1]")
                
                return Decimal(str(confidence))
            except (InvalidOperation, ValueError) as e:
                raise ValueError(f"Invalid confidence score {confidence}: {e}") from e
        
        raise ValueError(f"Unsupported confidence score type: {type(confidence)}")
    
    @staticmethod
    def validate_dynamodb_item(item: Dict[str, Any]) -> bool:
        """
        Validate that a dictionary contains only DynamoDB-compatible data types.
        
        Checks for common incompatible types like float, datetime objects, etc.
        
        Args:
            item: Dictionary to validate
            
        Returns:
            bool: True if all values are DynamoDB-compatible, False otherwise
        """
        def _check_value(value: Any) -> bool:
            """Recursively check if a value is DynamoDB-compatible."""
            if isinstance(value, float):
                return False  # Floats are not supported
            elif isinstance(value, (datetime, date)):
                return False  # Should be converted to string
            elif isinstance(value, dict):
                return all(_check_value(v) for v in value.values())
            elif isinstance(value, (list, tuple, set)):
                return all(_check_value(item) for item in value)
            else:
                # Other types (str, int, bool, Decimal, None) are supported
                return True
        
        if not isinstance(item, dict):
            return False
        
        return all(_check_value(value) for value in item.values())
    
    @staticmethod
    def get_conversion_summary(original_data: Any, converted_data: Any) -> Dict[str, int]:
        """
        Get a summary of conversions performed on the data.
        
        Useful for debugging and monitoring data conversion operations.
        
        Args:
            original_data: Original data before conversion
            converted_data: Data after conversion
            
        Returns:
            Dict[str, int]: Summary with counts of different conversion types
        """
        summary = {
            'floats_converted': 0,
            'nested_dicts': 0,
            'nested_lists': 0,
            'total_items': 0
        }
        
        def _count_conversions(orig: Any, conv: Any) -> None:
            """Recursively count conversions."""
            summary['total_items'] += 1
            
            if isinstance(orig, float) and isinstance(conv, Decimal):
                summary['floats_converted'] += 1
            elif isinstance(orig, dict) and isinstance(conv, dict):
                summary['nested_dicts'] += 1
                for key in orig:
                    if key in conv:
                        _count_conversions(orig[key], conv[key])
            elif isinstance(orig, (list, tuple)) and isinstance(conv, (list, tuple)):
                summary['nested_lists'] += 1
                for i, item in enumerate(orig):
                    if i < len(conv):
                        _count_conversions(item, conv[i])
        
        try:
            _count_conversions(original_data, converted_data)
        except Exception as e:
            logger.warning(f"Failed to generate conversion summary: {e}")
        
        return summary


def safe_decimal_conversion(value: Union[float, int, str]) -> Optional[Decimal]:
    """
    Safely convert a value to Decimal with error handling.
    
    This is a convenience function for converting individual values
    to Decimal with proper error handling and logging.
    
    Args:
        value: Value to convert to Decimal
        
    Returns:
        Optional[Decimal]: Converted Decimal value or None if conversion fails
    """
    if value is None:
        return None
    
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.warning(f"Failed to convert {value} (type: {type(value)}) to Decimal: {e}")
        return None


def prepare_item_for_dynamodb(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to prepare any dictionary for DynamoDB storage.
    
    This function combines type conversion and validation to ensure
    the item is ready for DynamoDB operations.
    
    Args:
        item: Dictionary to prepare for DynamoDB
        
    Returns:
        Dict[str, Any]: Prepared dictionary
        
    Raises:
        ValueError: If the item cannot be prepared for DynamoDB
    """
    if not isinstance(item, dict):
        raise ValueError("Item must be a dictionary")
    
    # Convert float values to Decimal
    converted_item = DynamoDBTypeConverter.convert_floats_to_decimal(item)
    
    # Validate the result
    if not DynamoDBTypeConverter.validate_dynamodb_item(converted_item):
        raise ValueError("Item contains DynamoDB-incompatible data types after conversion")
    
    return converted_item