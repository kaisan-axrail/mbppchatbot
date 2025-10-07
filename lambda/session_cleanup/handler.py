"""
AWS Lambda handler for automated session cleanup.

This module provides the Lambda function handler for cleaning up inactive
and expired sessions from DynamoDB on a scheduled basis using CloudWatch Events.
"""

import json
import logging
import os
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SESSIONS_TABLE = os.environ.get('SESSIONS_TABLE', 'chatbot-sessions')
REGION_NAME = os.environ.get('AWS_REGION', 'us-east-1')
SESSION_TIMEOUT_MINUTES = int(os.environ.get('SESSION_TIMEOUT_MINUTES', '30'))
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'


class SessionCleanupError(Exception):
    """Custom exception for session cleanup errors."""
    pass


class SessionCleanupHandler:
    """
    Handler class for session cleanup operations.
    
    This class encapsulates the logic for identifying and cleaning up
    inactive sessions from DynamoDB with proper error handling and logging.
    """
    
    def __init__(
        self,
        table_name: str,
        region_name: str = 'us-east-1',
        session_timeout_minutes: int = 30,
        dry_run: bool = False
    ):
        """
        Initialize SessionCleanupHandler.
        
        Args:
            table_name: Name of the DynamoDB sessions table
            region_name: AWS region name
            session_timeout_minutes: Session timeout in minutes
            dry_run: If True, only log what would be cleaned up without deleting
        """
        self.table_name = table_name
        self.region_name = region_name
        self.session_timeout_minutes = session_timeout_minutes
        self.dry_run = dry_run
        
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            self.table = self.dynamodb.Table(table_name)
            self.cloudwatch = boto3.client('cloudwatch', region_name=region_name)
            logger.info(f"SessionCleanupHandler initialized for table: {table_name}")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise SessionCleanupError(f"AWS client initialization failed: {e}")
    
    def cleanup_inactive_sessions(self) -> Dict[str, Any]:
        """
        Clean up inactive and expired sessions from DynamoDB.
        
        Returns:
            Dict containing cleanup results and statistics
            
        Raises:
            SessionCleanupError: If cleanup operation fails
        """
        try:
            logger.info("Starting session cleanup process")
            
            # Get current timestamp for comparison
            from datetime import datetime, timezone, timedelta
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                minutes=self.session_timeout_minutes
            )
            cutoff_timestamp = cutoff_time.isoformat()
            
            # Scan for sessions to clean up
            expired_sessions = self._find_expired_sessions(cutoff_timestamp)
            inactive_sessions = self._find_inactive_sessions()
            
            # Combine and deduplicate sessions
            sessions_to_cleanup = self._deduplicate_sessions(
                expired_sessions + inactive_sessions
            )
            
            cleanup_count = len(sessions_to_cleanup)
            
            if cleanup_count == 0:
                logger.info("No sessions found for cleanup")
                return {
                    'status': 'success',
                    'sessions_cleaned': 0,
                    'dry_run': self.dry_run,
                    'message': 'No sessions required cleanup',
                    'cutoff_timestamp': cutoff_timestamp
                }
            
            # Perform cleanup
            if self.dry_run:
                logger.info(f"DRY RUN: Would clean up {cleanup_count} sessions")
                self._log_sessions_for_cleanup(sessions_to_cleanup)
            else:
                deleted_count = self._delete_sessions(sessions_to_cleanup)
                logger.info(f"Successfully cleaned up {deleted_count} sessions")
                
                # Send metrics to CloudWatch
                self._send_cleanup_metrics(deleted_count)
            
            return {
                'status': 'success',
                'sessions_cleaned': cleanup_count if not self.dry_run else 0,
                'sessions_identified': cleanup_count,
                'dry_run': self.dry_run,
                'cutoff_timestamp': cutoff_timestamp
            }
            
        except ClientError as e:
            error_msg = f"DynamoDB error during cleanup: {e}"
            logger.error(error_msg)
            raise SessionCleanupError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during cleanup: {e}"
            logger.error(error_msg)
            raise SessionCleanupError(error_msg)
    
    def _find_expired_sessions(self, cutoff_timestamp: str) -> list:
        """
        Find sessions that have expired based on last activity.
        
        Args:
            cutoff_timestamp: ISO timestamp for expiration cutoff
            
        Returns:
            List of expired session items
        """
        try:
            logger.debug(f"Scanning for sessions with last_activity < {cutoff_timestamp}")
            
            response = self.table.scan(
                FilterExpression='last_activity < :cutoff',
                ExpressionAttributeValues={
                    ':cutoff': cutoff_timestamp
                },
                ProjectionExpression='session_id, last_activity, created_at'
            )
            
            expired_sessions = response.get('Items', [])
            logger.info(f"Found {len(expired_sessions)} expired sessions")
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    FilterExpression='last_activity < :cutoff',
                    ExpressionAttributeValues={
                        ':cutoff': cutoff_timestamp
                    },
                    ProjectionExpression='session_id, last_activity, created_at',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                expired_sessions.extend(response.get('Items', []))
            
            return expired_sessions
            
        except ClientError as e:
            logger.error(f"Error scanning for expired sessions: {e}")
            raise
    
    def _find_inactive_sessions(self) -> list:
        """
        Find sessions that are marked as inactive.
        
        Returns:
            List of inactive session items
        """
        try:
            logger.debug("Scanning for inactive sessions")
            
            response = self.table.scan(
                FilterExpression='is_active = :inactive',
                ExpressionAttributeValues={
                    ':inactive': False
                },
                ProjectionExpression='session_id, last_activity, created_at'
            )
            
            inactive_sessions = response.get('Items', [])
            logger.info(f"Found {len(inactive_sessions)} inactive sessions")
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    FilterExpression='is_active = :inactive',
                    ExpressionAttributeValues={
                        ':inactive': False
                    },
                    ProjectionExpression='session_id, last_activity, created_at',
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                inactive_sessions.extend(response.get('Items', []))
            
            return inactive_sessions
            
        except ClientError as e:
            logger.error(f"Error scanning for inactive sessions: {e}")
            raise
    
    def _deduplicate_sessions(self, sessions: list) -> list:
        """
        Remove duplicate sessions from the list.
        
        Args:
            sessions: List of session items that may contain duplicates
            
        Returns:
            List of unique session items
        """
        seen_session_ids = set()
        unique_sessions = []
        
        for session in sessions:
            session_id = session['session_id']
            if session_id not in seen_session_ids:
                seen_session_ids.add(session_id)
                unique_sessions.append(session)
        
        logger.debug(f"Deduplicated {len(sessions)} sessions to {len(unique_sessions)}")
        return unique_sessions
    
    def _delete_sessions(self, sessions: list) -> int:
        """
        Delete sessions from DynamoDB in batches.
        
        Args:
            sessions: List of session items to delete
            
        Returns:
            Number of sessions successfully deleted
        """
        deleted_count = 0
        batch_size = 25  # DynamoDB batch write limit
        
        try:
            # Process sessions in batches
            for i in range(0, len(sessions), batch_size):
                batch = sessions[i:i + batch_size]
                
                with self.table.batch_writer() as batch_writer:
                    for session in batch:
                        batch_writer.delete_item(
                            Key={'session_id': session['session_id']}
                        )
                        deleted_count += 1
                
                logger.debug(f"Deleted batch of {len(batch)} sessions")
            
            return deleted_count
            
        except ClientError as e:
            logger.error(f"Error deleting session batch: {e}")
            raise
    
    def _log_sessions_for_cleanup(self, sessions: list) -> None:
        """
        Log details of sessions that would be cleaned up (for dry run).
        
        Args:
            sessions: List of session items to log
        """
        logger.info("Sessions that would be cleaned up:")
        for session in sessions[:10]:  # Log first 10 for brevity
            logger.info(
                f"  Session ID: {session['session_id']}, "
                f"Last Activity: {session.get('last_activity', 'N/A')}, "
                f"Created: {session.get('created_at', 'N/A')}"
            )
        
        if len(sessions) > 10:
            logger.info(f"  ... and {len(sessions) - 10} more sessions")
    
    def _send_cleanup_metrics(self, deleted_count: int) -> None:
        """
        Send cleanup metrics to CloudWatch.
        
        Args:
            deleted_count: Number of sessions that were deleted
        """
        try:
            self.cloudwatch.put_metric_data(
                Namespace='ChatbotSystem/SessionCleanup',
                MetricData=[
                    {
                        'MetricName': 'SessionsCleanedUp',
                        'Value': deleted_count,
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'CleanupExecutions',
                        'Value': 1,
                        'Unit': 'Count'
                    }
                ]
            )
            logger.debug(f"Sent cleanup metrics to CloudWatch: {deleted_count} sessions")
            
        except ClientError as e:
            logger.warning(f"Failed to send metrics to CloudWatch: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error sending metrics: {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function for session cleanup.
    
    This function is triggered by CloudWatch Events on a scheduled basis
    to clean up inactive and expired sessions from DynamoDB.
    
    Args:
        event: Lambda event data (from CloudWatch Events)
        context: Lambda context object
        
    Returns:
        Dict containing cleanup results and status
    """
    try:
        logger.info(f"Session cleanup Lambda started. Event: {json.dumps(event)}")
        
        # Initialize cleanup handler
        cleanup_handler = SessionCleanupHandler(
            table_name=SESSIONS_TABLE,
            region_name=REGION_NAME,
            session_timeout_minutes=SESSION_TIMEOUT_MINUTES,
            dry_run=DRY_RUN
        )
        
        # Perform cleanup
        result = cleanup_handler.cleanup_inactive_sessions()
        
        logger.info(f"Session cleanup completed successfully: {result}")
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except SessionCleanupError as e:
        logger.error(f"Session cleanup error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e),
                'error_type': 'SessionCleanupError'
            })
        }
    except Exception as e:
        logger.error(f"Unexpected error in session cleanup: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e),
                'error_type': 'UnexpectedError'
            })
        }