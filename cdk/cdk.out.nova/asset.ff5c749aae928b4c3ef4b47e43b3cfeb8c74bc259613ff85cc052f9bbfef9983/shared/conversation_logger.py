"""
Conversation logging system for the websocket chatbot.

This module provides functionality to log conversations, questions, responses,
and metadata to DynamoDB with proper structured logging and session tracking.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import asdict

import boto3
from botocore.exceptions import ClientError

from shared.models import ConversationRecord, QueryType
from shared.exceptions import DatabaseError


# Configure structured logging
logger = logging.getLogger(__name__)


class ConversationLogger:
    """
    Handles conversation data storage to DynamoDB with structured logging.
    
    This class manages the storage of conversation records including questions,
    responses, metadata, session tracking, and timestamps for all interactions.
    """
    
    def __init__(self, table_name: str, region_name: str = 'us-east-1'):
        """
        Initialize the conversation logger.
        
        Args:
            table_name: Name of the DynamoDB conversations table
            region_name: AWS region name (default: us-east-1)
        """
        self.table_name = table_name
        self.region_name = region_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        
        logger.info(
            "ConversationLogger initialized",
            extra={
                'table_name': table_name,
                'region': region_name
            }
        )
    
    def log_user_message(
        self,
        session_id: str,
        content: str,
        message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a user message to the conversations table.
        
        Args:
            session_id: Session identifier
            content: Message content from user
            message_id: Optional message ID (generated if not provided)
            metadata: Optional additional metadata
            
        Returns:
            str: Message ID of the logged message
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        if not message_id:
            message_id = self._generate_message_id()
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        conversation_record = ConversationRecord(
            sessionId=session_id,
            messageId=message_id,
            timestamp=timestamp,
            messageType='user',
            content=content,
            queryType=None,
            sources=None,
            toolsUsed=None,
            responseTime=None
        )
        
        try:
            item = self._conversation_record_to_item(conversation_record)
            if metadata:
                item['metadata'] = metadata
            
            self.table.put_item(Item=item)
            
            logger.info(
                "User message logged successfully",
                extra={
                    'session_id': session_id,
                    'message_id': message_id,
                    'content_length': len(content),
                    'timestamp': timestamp
                }
            )
            
            return message_id
            
        except ClientError as e:
            error_msg = f"Failed to log user message: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'session_id': session_id,
                    'message_id': message_id,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def log_assistant_response(
        self,
        session_id: str,
        content: str,
        query_type: QueryType,
        response_time_ms: Optional[int] = None,
        sources: Optional[List[str]] = None,
        tools_used: Optional[List[str]] = None,
        message_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an assistant response to the conversations table.
        
        Args:
            session_id: Session identifier
            content: Response content from assistant
            query_type: Type of query processed
            response_time_ms: Response time in milliseconds
            sources: List of sources used for RAG responses
            tools_used: List of MCP tools used
            message_id: Optional message ID (generated if not provided)
            metadata: Optional additional metadata
            
        Returns:
            str: Message ID of the logged response
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        if not message_id:
            message_id = self._generate_message_id()
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        conversation_record = ConversationRecord(
            sessionId=session_id,
            messageId=message_id,
            timestamp=timestamp,
            messageType='assistant',
            content=content,
            queryType=query_type,
            sources=sources,
            toolsUsed=tools_used,
            responseTime=response_time_ms
        )
        
        try:
            item = self._conversation_record_to_item(conversation_record)
            if metadata:
                item['metadata'] = metadata
            
            self.table.put_item(Item=item)
            
            logger.info(
                "Assistant response logged successfully",
                extra={
                    'session_id': session_id,
                    'message_id': message_id,
                    'query_type': query_type.value,
                    'content_length': len(content),
                    'response_time_ms': response_time_ms,
                    'sources_count': len(sources) if sources else 0,
                    'tools_used_count': len(tools_used) if tools_used else 0,
                    'timestamp': timestamp
                }
            )
            
            return message_id
            
        except ClientError as e:
            error_msg = f"Failed to log assistant response: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'session_id': session_id,
                    'message_id': message_id,
                    'query_type': query_type.value,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50,
        last_message_id: Optional[str] = None
    ) -> List[ConversationRecord]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            last_message_id: Last message ID for pagination
            
        Returns:
            List[ConversationRecord]: List of conversation records
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        try:
            query_kwargs = {
                'KeyConditionExpression': 'sessionId = :session_id',
                'ExpressionAttributeValues': {':session_id': session_id},
                'ScanIndexForward': False,  # Most recent first
                'Limit': limit
            }
            
            if last_message_id:
                query_kwargs['ExclusiveStartKey'] = {
                    'sessionId': session_id,
                    'messageId': last_message_id
                }
            
            response = self.table.query(**query_kwargs)
            
            conversations = []
            for item in response['Items']:
                conversation = self._item_to_conversation_record(item)
                conversations.append(conversation)
            
            logger.info(
                "Conversation history retrieved",
                extra={
                    'session_id': session_id,
                    'messages_count': len(conversations),
                    'limit': limit
                }
            )
            
            return conversations
            
        except ClientError as e:
            error_msg = f"Failed to retrieve conversation history: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'session_id': session_id,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def delete_conversation_history(self, session_id: str) -> int:
        """
        Delete all conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            int: Number of messages deleted
            
        Raises:
            DatabaseError: If DynamoDB operation fails
        """
        try:
            # First, get all message IDs for the session
            response = self.table.query(
                KeyConditionExpression='sessionId = :session_id',
                ExpressionAttributeValues={':session_id': session_id},
                ProjectionExpression='messageId'
            )
            
            deleted_count = 0
            
            # Delete each message
            for item in response['Items']:
                self.table.delete_item(
                    Key={
                        'sessionId': session_id,
                        'messageId': item['messageId']
                    }
                )
                deleted_count += 1
            
            logger.info(
                "Conversation history deleted",
                extra={
                    'session_id': session_id,
                    'deleted_count': deleted_count
                }
            )
            
            return deleted_count
            
        except ClientError as e:
            error_msg = f"Failed to delete conversation history: {str(e)}"
            logger.error(
                error_msg,
                extra={
                    'session_id': session_id,
                    'error_code': e.response['Error']['Code']
                }
            )
            raise DatabaseError(error_msg) from e
    
    def _generate_message_id(self) -> str:
        """Generate a unique message ID using UUID4."""
        return str(uuid.uuid4())
    
    def _conversation_record_to_item(self, record: ConversationRecord) -> Dict[str, Any]:
        """Convert ConversationRecord to DynamoDB item format."""
        item = {
            'sessionId': record.sessionId,
            'messageId': record.messageId,
            'timestamp': record.timestamp,
            'messageType': record.messageType,
            'content': record.content
        }
        
        if record.queryType:
            item['queryType'] = record.queryType.value
        
        if record.sources:
            item['sources'] = record.sources
        
        if record.toolsUsed:
            item['toolsUsed'] = record.toolsUsed
        
        if record.responseTime is not None:
            item['responseTime'] = record.responseTime
        
        return item
    
    def _item_to_conversation_record(self, item: Dict[str, Any]) -> ConversationRecord:
        """Convert DynamoDB item to ConversationRecord."""
        query_type = None
        if 'queryType' in item:
            query_type = QueryType(item['queryType'])
        
        return ConversationRecord(
            sessionId=item['sessionId'],
            messageId=item['messageId'],
            timestamp=item['timestamp'],
            messageType=item['messageType'],
            content=item['content'],
            queryType=query_type,
            sources=item.get('sources'),
            toolsUsed=item.get('toolsUsed'),
            responseTime=item.get('responseTime')
        )


def configure_conversation_logging(log_level: str = 'INFO') -> None:
    """
    Configure structured logging for conversation operations.
    
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