"""
Analytics and tool usage tracking system for the websocket chatbot.

This module provides functionality to track and store analytics data including
tool usage, query types, session events, and performance metrics to DynamoDB
with efficient data storage and retrieval patterns.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional, Union
from dataclasses import asdict
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from shared.models import AnalyticsRecord, QueryType
from shared.exceptions import DatabaseError
from shared.dynamodb_converter import DynamoDBTypeConverter
from shared.error_handler import error_handler, isolate_analytics_errors


# Configure structured logging
logger = logging.getLogger(__name__)


class EventType(Enum):
    """Enumeration of analytics event types."""
    QUERY = 'query'
    TOOL_USAGE = 'tool_usage'
    SESSION_CREATED = 'session_created'
    SESSION_CLOSED = 'session_closed'
    ERROR_OCCURRED = 'error_occurred'
    RESPONSE_GENERATED = 'response_generated'


class AnalyticsTracker:
    """
    Handles analytics data collection and storage to DynamoDB.
    
    This class manages the collection and storage of analytics data including
    tool usage tracking, query type analysis, session events, and performance
    metrics with efficient indexing for analytics queries.
    """
    
    def __init__(self, table_name: str, region_name: str = 'us-east-1'):
        """
        Initialize the analytics tracker.
        
        Args:
            table_name: Name of the DynamoDB analytics table
            region_name: AWS region name (default: us-east-1)
        """
        self.table_name = table_name
        self.region_name = region_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        
        logger.info(
            "AnalyticsTracker initialized",
            extra={
                'table_name': table_name,
                'region': region_name
            }
        )
    
    def track_query_event(
        self,
        session_id: str,
        query_type: QueryType,
        response_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track a query processing event.
        
        Args:
            session_id: Session identifier
            query_type: Type of query processed
            response_time_ms: Response time in milliseconds
            success: Whether the query was successful
            error_message: Error message if query failed
            metadata: Additional metadata
            
        Returns:
            str: Event ID of the tracked event
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        event_details = {
            'query_type': query_type.value,
            'success': success,
            'response_time_ms': response_time_ms
        }
        
        if error_message:
            event_details['error_message'] = error_message
        
        if metadata:
            event_details.update(metadata)
        
        return self._track_event(
            event_type=EventType.QUERY,
            session_id=session_id,
            details=event_details
        )
    
    def track_tool_usage(
        self,
        session_id: str,
        tool_name: str,
        tool_parameters: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        result_summary: Optional[str] = None
    ) -> str:
        """
        Track MCP tool usage event.
        
        Args:
            session_id: Session identifier
            tool_name: Name of the MCP tool used
            tool_parameters: Parameters passed to the tool
            execution_time_ms: Tool execution time in milliseconds
            success: Whether the tool execution was successful
            error_message: Error message if tool failed
            result_summary: Summary of tool results
            
        Returns:
            str: Event ID of the tracked event
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        event_details = {
            'tool_name': tool_name,
            'success': success,
            'execution_time_ms': execution_time_ms
        }
        
        if tool_parameters:
            event_details['tool_parameters'] = tool_parameters
        
        if error_message:
            event_details['error_message'] = error_message
        
        if result_summary:
            event_details['result_summary'] = result_summary
        
        return self._track_event(
            event_type=EventType.TOOL_USAGE,
            session_id=session_id,
            details=event_details
        )
    
    def track_session_event(
        self,
        session_id: str,
        event_type: EventType,
        client_info: Optional[Dict[str, str]] = None,
        session_duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track session lifecycle events.
        
        Args:
            session_id: Session identifier
            event_type: Type of session event (SESSION_CREATED or SESSION_CLOSED)
            client_info: Client information (user agent, IP, etc.)
            session_duration_ms: Session duration in milliseconds (for close events)
            metadata: Additional metadata
            
        Returns:
            str: Event ID of the tracked event
            
        Raises:
            DatabaseError: If DynamoDB operation fails
            ValueError: If event_type is not a session event
        """
        if event_type not in [EventType.SESSION_CREATED, EventType.SESSION_CLOSED]:
            raise ValueError(f"Invalid session event type: {event_type}")
        
        event_details = {}
        
        if client_info:
            event_details['client_info'] = client_info
        
        if session_duration_ms is not None:
            event_details['session_duration_ms'] = session_duration_ms
        
        if metadata:
            event_details.update(metadata)
        
        return self._track_event(
            event_type=event_type,
            session_id=session_id,
            details=event_details
        )
    
    def track_error_event(
        self,
        session_id: str,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Track error events for debugging and monitoring.
        
        Args:
            session_id: Session identifier
            error_type: Type/category of error
            error_message: Error message
            stack_trace: Stack trace if available
            context: Additional context information
            
        Returns:
            str: Event ID of the tracked event
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        event_details = {
            'error_type': error_type,
            'error_message': error_message
        }
        
        if stack_trace:
            event_details['stack_trace'] = stack_trace
        
        if context:
            event_details['context'] = context
        
        return self._track_event(
            event_type=EventType.ERROR_OCCURRED,
            session_id=session_id,
            details=event_details
        )
    
    def get_analytics_by_date(
        self,
        target_date: Union[str, date],
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[AnalyticsRecord]:
        """
        Retrieve analytics data for a specific date.
        
        Args:
            target_date: Date to query (YYYY-MM-DD string or date object)
            event_type: Optional filter by event type
            limit: Maximum number of records to retrieve
            
        Returns:
            List[AnalyticsRecord]: List of analytics records
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        if isinstance(target_date, date):
            date_str = target_date.strftime('%Y-%m-%d')
        else:
            date_str = target_date
        
        try:
            query_kwargs = {
                'KeyConditionExpression': '#date = :date',
                'ExpressionAttributeNames': {'#date': 'date'},
                'ExpressionAttributeValues': {':date': date_str},
                'ScanIndexForward': False,  # Most recent first
                'Limit': limit
            }
            
            if event_type:
                query_kwargs['FilterExpression'] = 'eventType = :event_type'
                query_kwargs['ExpressionAttributeValues'][':event_type'] = event_type.value
            
            response = self.table.query(**query_kwargs)
            
            analytics_records = []
            for item in response['Items']:
                record = self._item_to_analytics_record(item)
                analytics_records.append(record)
            
            logger.info(
                "Analytics data retrieved by date",
                extra={
                    'date': date_str,
                    'event_type': event_type.value if event_type else None,
                    'records_count': len(analytics_records)
                }
            )
            
            return analytics_records
            
        except ClientError as e:
            error_msg = f"Failed to retrieve analytics by date: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'date': date_str,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def get_tool_usage_stats(
        self,
        start_date: Union[str, date],
        end_date: Union[str, date]
    ) -> Dict[str, Any]:
        """
        Get tool usage statistics for a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD string or date object)
            end_date: End date (YYYY-MM-DD string or date object)
            
        Returns:
            Dict[str, Any]: Tool usage statistics
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        if isinstance(start_date, date):
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = start_date
        
        if isinstance(end_date, date):
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date_str = end_date
        
        try:
            # Query for tool usage events in the date range
            response = self.table.scan(
                FilterExpression='eventType = :event_type AND #date BETWEEN :start_date AND :end_date',
                ExpressionAttributeNames={'#date': 'date'},
                ExpressionAttributeValues={
                    ':event_type': EventType.TOOL_USAGE.value,
                    ':start_date': start_date_str,
                    ':end_date': end_date_str
                }
            )
            
            # Process statistics
            tool_stats = {}
            total_usage = 0
            successful_usage = 0
            total_execution_time = 0
            
            for item in response['Items']:
                details = item.get('details', {})
                tool_name = details.get('tool_name', 'unknown')
                success = details.get('success', False)
                execution_time = details.get('execution_time_ms', 0)
                
                if tool_name not in tool_stats:
                    tool_stats[tool_name] = {
                        'total_usage': 0,
                        'successful_usage': 0,
                        'failed_usage': 0,
                        'avg_execution_time_ms': 0,
                        'total_execution_time_ms': 0
                    }
                
                tool_stats[tool_name]['total_usage'] += 1
                total_usage += 1
                
                if success:
                    tool_stats[tool_name]['successful_usage'] += 1
                    successful_usage += 1
                else:
                    tool_stats[tool_name]['failed_usage'] += 1
                
                if execution_time:
                    tool_stats[tool_name]['total_execution_time_ms'] += execution_time
                    total_execution_time += execution_time
            
            # Calculate averages
            for tool_name, stats in tool_stats.items():
                if stats['total_usage'] > 0:
                    stats['avg_execution_time_ms'] = (
                        stats['total_execution_time_ms'] / stats['total_usage']
                    )
            
            result = {
                'date_range': {
                    'start_date': start_date_str,
                    'end_date': end_date_str
                },
                'summary': {
                    'total_tool_usage': total_usage,
                    'successful_usage': successful_usage,
                    'failed_usage': total_usage - successful_usage,
                    'success_rate': successful_usage / total_usage if total_usage > 0 else 0,
                    'avg_execution_time_ms': total_execution_time / total_usage if total_usage > 0 else 0
                },
                'tool_breakdown': tool_stats
            }
            
            logger.info(
                "Tool usage statistics calculated",
                extra={
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'total_usage': total_usage,
                    'unique_tools': len(tool_stats)
                }
            )
            
            return result
            
        except ClientError as e:
            error_msg = f"Failed to get tool usage stats: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def get_query_type_stats(
        self,
        start_date: Union[str, date],
        end_date: Union[str, date]
    ) -> Dict[str, Any]:
        """
        Get query type statistics for a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD string or date object)
            end_date: End date (YYYY-MM-DD string or date object)
            
        Returns:
            Dict[str, Any]: Query type statistics
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        if isinstance(start_date, date):
            start_date_str = start_date.strftime('%Y-%m-%d')
        else:
            start_date_str = start_date
        
        if isinstance(end_date, date):
            end_date_str = end_date.strftime('%Y-%m-%d')
        else:
            end_date_str = end_date
        
        try:
            # Query for query events in the date range
            response = self.table.scan(
                FilterExpression='eventType = :event_type AND #date BETWEEN :start_date AND :end_date',
                ExpressionAttributeNames={'#date': 'date'},
                ExpressionAttributeValues={
                    ':event_type': EventType.QUERY.value,
                    ':start_date': start_date_str,
                    ':end_date': end_date_str
                }
            )
            
            # Process statistics
            query_stats = {}
            total_queries = 0
            successful_queries = 0
            total_response_time = 0
            
            for item in response['Items']:
                details = item.get('details', {})
                query_type = details.get('query_type', 'unknown')
                success = details.get('success', False)
                response_time = details.get('response_time_ms', 0)
                
                if query_type not in query_stats:
                    query_stats[query_type] = {
                        'total_queries': 0,
                        'successful_queries': 0,
                        'failed_queries': 0,
                        'avg_response_time_ms': 0,
                        'total_response_time_ms': 0
                    }
                
                query_stats[query_type]['total_queries'] += 1
                total_queries += 1
                
                if success:
                    query_stats[query_type]['successful_queries'] += 1
                    successful_queries += 1
                else:
                    query_stats[query_type]['failed_queries'] += 1
                
                if response_time:
                    query_stats[query_type]['total_response_time_ms'] += response_time
                    total_response_time += response_time
            
            # Calculate averages
            for query_type, stats in query_stats.items():
                if stats['total_queries'] > 0:
                    stats['avg_response_time_ms'] = (
                        stats['total_response_time_ms'] / stats['total_queries']
                    )
            
            result = {
                'date_range': {
                    'start_date': start_date_str,
                    'end_date': end_date_str
                },
                'summary': {
                    'total_queries': total_queries,
                    'successful_queries': successful_queries,
                    'failed_queries': total_queries - successful_queries,
                    'success_rate': successful_queries / total_queries if total_queries > 0 else 0,
                    'avg_response_time_ms': total_response_time / total_queries if total_queries > 0 else 0
                },
                'query_type_breakdown': query_stats
            }
            
            logger.info(
                "Query type statistics calculated",
                extra={
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'total_queries': total_queries,
                    'query_types': len(query_stats)
                }
            )
            
            return result
            
        except ClientError as e:
            error_msg = f"Failed to get query type stats: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def _track_event(
        self,
        event_type: EventType,
        session_id: str,
        details: Dict[str, Any]
    ) -> str:
        """
        Internal method to track an analytics event with error isolation.
        
        Args:
            event_type: Type of event to track
            session_id: Session identifier
            details: Event details dictionary
            
        Returns:
            str: Event ID of the tracked event, or None if tracking failed
        """
        event_id = self._generate_event_id()
        timestamp = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        analytics_record = AnalyticsRecord(
            date=date_str,
            eventId=event_id,
            eventType=event_type.value,
            sessionId=session_id,
            details=details,
            timestamp=timestamp
        )
        
        try:
            item = self._analytics_record_to_item(analytics_record)
            # Ensure all data is DynamoDB-compatible by converting floats to Decimal
            prepared_item = DynamoDBTypeConverter.prepare_analytics_data(item)
            self.table.put_item(Item=prepared_item)
            
            logger.info(
                "Analytics event tracked successfully",
                extra={
                    'event_type': event_type.value,
                    'event_id': event_id,
                    'session_id': session_id,
                    'timestamp': timestamp
                }
            )
            
            return event_id
            
        except Exception as e:
            # Use error handler for analytics error isolation
            context = {
                'event_type': event_type.value,
                'event_id': event_id,
                'session_id': session_id,
                'operation': 'track_event'
            }
            
            error_handler.handle_analytics_error(e, context, continue_processing=True)
            
            # Return None to indicate tracking failure without interrupting main processing
            return None
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID using UUID4."""
        return str(uuid.uuid4())
    
    def _analytics_record_to_item(self, record: AnalyticsRecord) -> Dict[str, Any]:
        """Convert AnalyticsRecord to DynamoDB item format."""
        return {
            'date': record.date,
            'eventId': record.eventId,
            'eventType': record.eventType,
            'sessionId': record.sessionId,
            'details': record.details,
            'timestamp': record.timestamp
        }
    
    def _item_to_analytics_record(self, item: Dict[str, Any]) -> AnalyticsRecord:
        """Convert DynamoDB item to AnalyticsRecord."""
        return AnalyticsRecord(
            date=item['date'],
            eventId=item['eventId'],
            eventType=item['eventType'],
            sessionId=item['sessionId'],
            details=item['details'],
            timestamp=item['timestamp']
        )
    
    @isolate_analytics_errors
    def track_language_detection(
        self,
        session_id: str,
        detected_language: str,
        confidence: float,
        user_text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Track language detection events for MBPP compliance with error isolation.
        
        Args:
            session_id: Session identifier
            detected_language: Detected language code (en, ms, zh, ta)
            confidence: Detection confidence score
            user_text: Original user text (truncated for privacy)
            context: Additional context data
            
        Returns:
            True if tracking was successful, False otherwise
        """
        # Convert confidence score to Decimal for DynamoDB compatibility
        confidence_decimal = DynamoDBTypeConverter.prepare_confidence_score(confidence)
        
        details = {
            'detected_language': detected_language,
            'confidence': confidence_decimal,
            'text_length': len(user_text) if user_text else 0,
            'text_preview': user_text[:50] + '...' if user_text and len(user_text) > 50 else user_text,
            'is_supported': detected_language in ['en', 'ms', 'zh', 'ta']
        }
        
        if context:
            # Convert any float values in context to Decimal
            converted_context = DynamoDBTypeConverter.convert_floats_to_decimal(context)
            details.update(converted_context)
        
        details['event_subtype'] = 'language_detection'
        event_id = self._track_event(
            event_type=EventType.QUERY,
            session_id=session_id,
            details=details
        )
        return event_id is not None
    
    @isolate_analytics_errors
    def track_sentiment_analysis(
        self,
        session_id: str,
        sentiment: str,
        confidence: float,
        sentiment_scores: Dict[str, float],
        requires_attention: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Track sentiment analysis events for MBPP compliance with error isolation.
        
        Args:
            session_id: Session identifier
            sentiment: Detected sentiment (POSITIVE, NEGATIVE, NEUTRAL, MIXED)
            confidence: Sentiment confidence score
            sentiment_scores: Detailed sentiment scores
            requires_attention: Whether this sentiment requires attention
            context: Additional context data
            
        Returns:
            True if tracking was successful, False otherwise
        """
        # Convert confidence score and sentiment scores to Decimal for DynamoDB compatibility
        confidence_decimal = DynamoDBTypeConverter.prepare_confidence_score(confidence)
        sentiment_scores_decimal = DynamoDBTypeConverter.prepare_sentiment_data(sentiment_scores)
        
        details = {
            'sentiment': sentiment,
            'confidence': confidence_decimal,
            'sentiment_scores': sentiment_scores_decimal,
            'requires_attention': requires_attention,
            'priority': 'high' if requires_attention else 'low'
        }
        
        if context:
            # Convert any float values in context to Decimal
            converted_context = DynamoDBTypeConverter.convert_floats_to_decimal(context)
            details.update(converted_context)
        
        details['event_subtype'] = 'sentiment_analysis'
        event_id = self._track_event(
            event_type=EventType.QUERY,
            session_id=session_id,
            details=details
        )
        return event_id is not None
    
    @isolate_analytics_errors
    def track_multilingual_interaction(
        self,
        session_id: str,
        user_language: str,
        response_language: str,
        language_confidence: float,
        sentiment_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Track complete multilingual interaction for MBPP compliance with error isolation.
        
        Args:
            session_id: Session identifier
            user_language: Detected user language
            response_language: Language used for response
            language_confidence: Language detection confidence
            sentiment_data: Optional sentiment analysis data
            context: Additional context data
            
        Returns:
            True if tracking was successful, False otherwise
        """
        # Convert language confidence to Decimal for DynamoDB compatibility
        language_confidence_decimal = DynamoDBTypeConverter.prepare_confidence_score(language_confidence)
        
        details = {
            'user_language': user_language,
            'response_language': response_language,
            'language_confidence': language_confidence_decimal,
            'is_multilingual': user_language != 'en',
            'language_match': user_language == response_language
        }
        
        if sentiment_data:
            # Convert any float values in sentiment data to Decimal
            converted_sentiment_data = DynamoDBTypeConverter.convert_floats_to_decimal(sentiment_data)
            details['sentiment_data'] = converted_sentiment_data
        
        if context:
            # Convert any float values in context to Decimal
            converted_context = DynamoDBTypeConverter.convert_floats_to_decimal(context)
            details.update(converted_context)
        
        details['event_subtype'] = 'multilingual_interaction'
        event_id = self._track_event(
            event_type=EventType.RESPONSE_GENERATED,
            session_id=session_id,
            details=details
        )
        return event_id is not None


def configure_analytics_logging(log_level: str = 'INFO') -> None:
    """
    Configure structured logging for analytics operations.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Configure boto3 logging to reduce noise
    boto3.set_stream_logger('boto3', logging.WARNING)
    boto3.set_stream_logger('botocore', logging.WARNING)