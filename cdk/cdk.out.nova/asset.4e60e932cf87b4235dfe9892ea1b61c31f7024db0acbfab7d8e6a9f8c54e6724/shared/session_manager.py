"""
Session management system with DynamoDB integration.

This module provides the SessionManager class for handling session lifecycle,
storage, and cleanup operations using AWS DynamoDB.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import asdict

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from shared.session_models import (
    Session,
    SessionRecord,
    SessionStatus,
    ClientInfo,
    create_new_session,
    validate_session_id
)
from shared.exceptions import (
    SessionNotFoundError,
    SessionManagerError,
    DynamoDbError
)
from shared.retry_utils import (
    retry_with_backoff,
    DATABASE_RETRY_CONFIG,
    handle_service_failure
)


logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session lifecycle and storage using DynamoDB.
    
    This class handles session creation, retrieval, updates, and cleanup
    operations with proper error handling and logging.
    """
    
    def __init__(
        self,
        table_name: str,
        region_name: str = 'us-east-1',
        session_timeout_minutes: int = 30
    ):
        """
        Initialize SessionManager with DynamoDB configuration.
        
        Args:
            table_name: Name of the DynamoDB table for sessions
            region_name: AWS region name (default: us-east-1)
            session_timeout_minutes: Session timeout in minutes (default: 30)
        """
        self.table_name = table_name
        self.region_name = region_name
        self.session_timeout_minutes = session_timeout_minutes
        
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            self.table = self.dynamodb.Table(table_name)
            logger.info(f"SessionManager initialized with table: {table_name}")
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB connection: {e}")
            raise SessionManagerError(f"DynamoDB initialization failed: {e}")
    
    @retry_with_backoff(
        config=DATABASE_RETRY_CONFIG,
        service_name="dynamodb"
    )
    async def create_session(self, client_info: Optional[ClientInfo] = None) -> str:
        """
        Create a new session and store it in DynamoDB.
        
        Args:
            client_info: Optional client information
            
        Returns:
            str: Generated session ID
            
        Raises:
            SessionManagerError: If session creation fails
        """
        try:
            session = create_new_session(client_info)
            session_record = SessionRecord.from_session(session)
            
            # Convert to DynamoDB item format
            item = self._session_record_to_item(session_record)
            
            # Store in DynamoDB
            self.table.put_item(Item=item)
            
            logger.info(f"Created new session: {session.session_id}")
            return session.session_id
            
        except ClientError as e:
            error_msg = f"DynamoDB error creating session: {e}"
            logger.error(error_msg)
            raise DynamoDbError(error_msg, "create_session")
        except Exception as e:
            error_msg = f"Unexpected error creating session: {e}"
            logger.error(error_msg)
            raise SessionManagerError(error_msg)
    
    @retry_with_backoff(
        config=DATABASE_RETRY_CONFIG,
        service_name="dynamodb"
    )
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session from DynamoDB.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session object if found, None otherwise
            
        Raises:
            SessionManagerError: If retrieval fails
        """
        if not validate_session_id(session_id):
            logger.warning(f"Invalid session ID format: {session_id}")
            return None
        
        try:
            response = self.table.get_item(
                Key={'sessionId': session_id}
            )
            
            if 'Item' not in response:
                logger.debug(f"Session not found: {session_id}")
                return None
            
            # Convert DynamoDB item to SessionRecord
            session_record = self._item_to_session_record(response['Item'])
            session = session_record.to_session()
            
            # Check if session is expired
            if session.is_expired(self.session_timeout_minutes):
                logger.info(f"Session expired: {session_id}")
                await self._mark_session_expired(session_id)
                return None
            
            logger.debug(f"Retrieved session: {session_id}")
            return session
            
        except ClientError as e:
            error_msg = f"DynamoDB error retrieving session {session_id}: {e}"
            logger.error(error_msg)
            raise DynamoDbError(error_msg, "get_session")
        except Exception as e:
            error_msg = f"Unexpected error retrieving session {session_id}: {e}"
            logger.error(error_msg)
            raise SessionManagerError(error_msg)
    
    async def update_activity(self, session_id: str) -> None:
        """
        Update session activity timestamp.
        
        Args:
            session_id: Session ID to update
            
        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionManagerError: If update fails
        """
        if not validate_session_id(session_id):
            raise SessionNotFoundError(session_id)
        
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            
            response = self.table.update_item(
                Key={'sessionId': session_id},
                UpdateExpression='SET last_activity = :timestamp, is_active = :active',
                ExpressionAttributeValues={
                    ':timestamp': current_time,
                    ':active': True
                },
                ConditionExpression='attribute_exists(sessionId)',
                ReturnValues='UPDATED_NEW'
            )
            
            logger.debug(f"Updated activity for session: {session_id}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Session not found for activity update: {session_id}")
                raise SessionNotFoundError(session_id)
            else:
                error_msg = f"DynamoDB error updating session {session_id}: {e}"
                logger.error(error_msg)
                raise DynamoDbError(error_msg, "update_activity")
        except Exception as e:
            error_msg = f"Unexpected error updating session {session_id}: {e}"
            logger.error(error_msg)
            raise SessionManagerError(error_msg)
    
    async def close_session(self, session_id: str) -> None:
        """
        Close a session by marking it as inactive.
        
        Args:
            session_id: Session ID to close
            
        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionManagerError: If closing fails
        """
        if not validate_session_id(session_id):
            raise SessionNotFoundError(session_id)
        
        try:
            self.table.update_item(
                Key={'sessionId': session_id},
                UpdateExpression='SET is_active = :inactive',
                ExpressionAttributeValues={
                    ':inactive': False
                },
                ConditionExpression='attribute_exists(sessionId)'
            )
            
            logger.info(f"Closed session: {session_id}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Session not found for closing: {session_id}")
                raise SessionNotFoundError(session_id)
            else:
                error_msg = f"DynamoDB error closing session {session_id}: {e}"
                logger.error(error_msg)
                raise DynamoDbError(error_msg, "close_session")
        except Exception as e:
            error_msg = f"Unexpected error closing session {session_id}: {e}"
            logger.error(error_msg)
            raise SessionManagerError(error_msg)
    
    async def cleanup_inactive_sessions(self) -> int:
        """
        Clean up inactive and expired sessions.
        
        Returns:
            int: Number of sessions cleaned up
            
        Raises:
            SessionManagerError: If cleanup fails
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                minutes=self.session_timeout_minutes
            )
            cutoff_timestamp = cutoff_time.isoformat()
            
            # Scan for expired sessions
            response = self.table.scan(
                FilterExpression='last_activity < :cutoff OR is_active = :inactive',
                ExpressionAttributeValues={
                    ':cutoff': cutoff_timestamp,
                    ':inactive': False
                }
            )
            
            expired_sessions = response.get('Items', [])
            cleanup_count = 0
            
            # Delete expired sessions in batches
            with self.table.batch_writer() as batch:
                for item in expired_sessions:
                    batch.delete_item(
                        Key={'sessionId': item['sessionId']}
                    )
                    cleanup_count += 1
            
            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} inactive sessions")
            else:
                logger.debug("No inactive sessions to clean up")
            
            return cleanup_count
            
        except ClientError as e:
            error_msg = f"DynamoDB error during cleanup: {e}"
            logger.error(error_msg)
            raise DynamoDbError(error_msg, "cleanup_expired_sessions")
        except Exception as e:
            error_msg = f"Unexpected error during cleanup: {e}"
            logger.error(error_msg)
            raise SessionManagerError(error_msg)
    
    async def get_active_session_count(self) -> int:
        """
        Get count of active sessions.
        
        Returns:
            int: Number of active sessions
            
        Raises:
            SessionManagerError: If count operation fails
        """
        try:
            response = self.table.scan(
                FilterExpression='is_active = :active',
                ExpressionAttributeValues={
                    ':active': True
                },
                Select='COUNT'
            )
            
            count = response.get('Count', 0)
            logger.debug(f"Active session count: {count}")
            return count
            
        except ClientError as e:
            error_msg = f"DynamoDB error getting session count: {e}"
            logger.error(error_msg)
            raise DynamoDbError(error_msg, "get_active_session_count")
        except Exception as e:
            error_msg = f"Unexpected error getting session count: {e}"
            logger.error(error_msg)
            raise SessionManagerError(error_msg)
    
    def _session_record_to_item(self, session_record: SessionRecord) -> Dict[str, Any]:
        """
        Convert SessionRecord to DynamoDB item format.
        
        Args:
            session_record: SessionRecord to convert
            
        Returns:
            Dict containing DynamoDB item data
        """
        item = asdict(session_record)
        
        # Ensure client_info is properly formatted
        if item['client_info'] is None:
            item['client_info'] = {}
        
        return item
    
    def _item_to_session_record(self, item: Dict[str, Any]) -> SessionRecord:
        """
        Convert DynamoDB item to SessionRecord.
        
        Args:
            item: DynamoDB item data
            
        Returns:
            SessionRecord object
        """
        # Handle optional fields
        client_info = item.get('client_info')
        if client_info == {}:
            client_info = None
        
        return SessionRecord(
            sessionId=item['sessionId'],
            created_at=item['created_at'],
            last_activity=item['last_activity'],
            is_active=item['is_active'],
            client_info=client_info,
            metadata=item.get('metadata', {}),
            ttl=item.get('ttl', int(time.time()) + (24 * 60 * 60))
        )
    
    async def _mark_session_expired(self, session_id: str) -> None:
        """
        Mark a session as expired (internal method).
        
        Args:
            session_id: Session ID to mark as expired
        """
        try:
            self.table.update_item(
                Key={'sessionId': session_id},
                UpdateExpression='SET is_active = :inactive',
                ExpressionAttributeValues={
                    ':inactive': False
                }
            )
            logger.debug(f"Marked session as expired: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to mark session as expired {session_id}: {e}")