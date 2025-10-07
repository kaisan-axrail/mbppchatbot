"""
WebSocket handler Lambda function for chatbot system.

This module handles WebSocket connection lifecycle events (connect, disconnect, message)
and integrates with the session management system using DynamoDB.
"""

import json
import logging
import os
import asyncio
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Import shared modules
import sys
sys.path.append('/opt/python')
sys.path.append('/var/task')

from shared.session_manager import SessionManager
from shared.session_models import ClientInfo
from shared.exceptions import SessionNotFoundError, SessionManagerError
from shared.multilingual_prompts import create_language_service
from shared.sentiment_service import create_sentiment_service
from shared.analytics_tracker import AnalyticsTracker
from shared.error_handler import error_handler, isolate_analytics_errors

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """
    Manages WebSocket connections and integrates with session management.
    
    This class handles connection storage, retrieval, and cleanup operations
    using DynamoDB for persistent storage.
    """
    
    def __init__(self):
        """Initialize WebSocket connection manager with AWS services."""
        self.region_name = os.environ.get('AWS_REGION', 'us-east-1')
        self.sessions_table = os.environ.get('SESSIONS_TABLE', 'chatbot-sessions')
        self.connections_table = os.environ.get('CONNECTIONS_TABLE', 'websocket-connections')
        self.session_timeout_minutes = int(os.environ.get('SESSION_TIMEOUT_MINUTES', '30'))
        
        # Initialize AWS clients
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
        self.apigateway_client = boto3.client('apigatewaymanagementapi',
                                            endpoint_url=self._get_api_endpoint())
        
        # Initialize session manager
        self.session_manager = SessionManager(
            table_name=self.sessions_table,
            region_name=self.region_name,
            session_timeout_minutes=self.session_timeout_minutes
        )
        
        # Get connections table reference
        self.connections_table_ref = self.dynamodb.Table(self.connections_table)
        
        logger.info("WebSocketConnectionManager initialized")
    
    def _get_api_endpoint(self) -> str:
        """Get API Gateway WebSocket endpoint URL."""
        domain_name = os.environ.get('WEBSOCKET_DOMAIN_NAME')
        stage = os.environ.get('WEBSOCKET_STAGE', 'prod')
        
        if domain_name:
            return f"https://{domain_name}/{stage}"
        else:
            # Fallback to default format if domain not provided
            return f"https://execute-api.{self.region_name}.amazonaws.com/{stage}"
    
    async def handle_connect(self, connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle WebSocket connection event.
        
        Args:
            connection_id: WebSocket connection ID
            event: Lambda event data
            
        Returns:
            Response dictionary with statusCode and body
        """
        try:
            # Extract client information
            request_context = event.get('requestContext', {})
            headers = event.get('headers', {})
            
            client_info = ClientInfo(
                user_agent=headers.get('User-Agent'),
                ip_address=request_context.get('identity', {}).get('sourceIp'),
                connection_id=connection_id
            )
            
            # Create new session
            session_id = await self.session_manager.create_session(client_info)
            
            # Store connection mapping
            await self._store_connection(connection_id, session_id, client_info)
            
            logger.info(f"WebSocket connected - Connection: {connection_id}, Session: {session_id}")
            
            # Send welcome message
            await self._send_message(connection_id, {
                'type': 'connection_established',
                'sessionId': session_id,
                'message': 'Connected to chatbot successfully'
            })
            
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Connected successfully'})
            }
            
        except Exception as e:
            logger.error(f"Error handling WebSocket connect for {connection_id}: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Connection failed'})
            }
    
    async def handle_disconnect(self, connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle WebSocket disconnection event.
        
        Args:
            connection_id: WebSocket connection ID
            event: Lambda event data
            
        Returns:
            Response dictionary with statusCode and body
        """
        try:
            # Get session ID from connection
            session_id = await self._get_session_from_connection(connection_id)
            
            if session_id:
                # Close session
                await self.session_manager.close_session(session_id)
                logger.info(f"Session closed for disconnection: {session_id}")
            
            # Remove connection mapping
            await self._remove_connection(connection_id)
            
            logger.info(f"WebSocket disconnected - Connection: {connection_id}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Disconnected successfully'})
            }
            
        except Exception as e:
            logger.error(f"Error handling WebSocket disconnect for {connection_id}: {str(e)}")
            # Return success even on error to avoid API Gateway retries
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Disconnected'})
            }
    
    async def handle_message(self, connection_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming WebSocket message.
        
        Args:
            connection_id: WebSocket connection ID
            event: Lambda event data containing the message
            
        Returns:
            Response dictionary with statusCode and body
        """
        try:
            # Validate and parse message first
            message_data = self._parse_message(event)
            if not message_data:
                logger.warning(f"Invalid message format from connection {connection_id}")
                await self._send_error_message(connection_id, "Invalid message format")
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid message format'})
                }
            
            # Get session ID from message or create new session
            session_id = None
            
            # Try to get session ID from message
            raw_body = json.loads(event.get('body', '{}'))
            if 'sessionId' in raw_body:
                session_id = raw_body['sessionId']
                
                # Verify session exists
                try:
                    session = await self.session_manager.get_session(session_id)
                    if not session:
                        logger.warning(f"Session {session_id} not found, creating new session")
                        session_id = None
                except Exception as e:
                    logger.warning(f"Error checking session {session_id}: {e}, creating new session")
                    session_id = None
            
            # Create new session if needed
            if not session_id:
                try:
                    from shared.session_models import ClientInfo
                    client_info = ClientInfo(connection_id=connection_id)
                    session_id = await self.session_manager.create_session(client_info)
                    logger.info(f"Created new session {session_id} for connection {connection_id}")
                    # For new sessions, no need to update activity since it was just created
                except Exception as e:
                    logger.error(f"Failed to create session: {e}")
                    await self._send_error_message(connection_id, "Failed to create session")
                    return {
                        'statusCode': 500,
                        'body': json.dumps({'error': 'Failed to create session'})
                    }
            else:
                # Update session activity only for existing sessions
                try:
                    await self.session_manager.update_activity(session_id)
                except SessionNotFoundError:
                    logger.warning(f"Session {session_id} not found during activity update")
                    await self._send_error_message(connection_id, "Session expired")
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Session expired'})
                    }
            
            # Log message processing
            self._log_message_event(session_id, connection_id, message_data, 'received')
            
            # Route message for processing
            await self._route_message(connection_id, session_id, message_data)
            
            logger.info(f"Message processed successfully - Connection: {connection_id}, Session: {session_id}")
            
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Message processed successfully'})
            }
            
        except Exception as e:
            logger.error(f"Error handling message from connection {connection_id}: {str(e)}", exc_info=True)
            await self._send_error_message(connection_id, "Internal server error")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Internal server error'})
            }
    
    def _parse_message(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse and validate incoming WebSocket message.
        
        Args:
            event: Lambda event data
            
        Returns:
            Parsed message data if valid, None otherwise
        """
        try:
            # Get message body
            body = event.get('body')
            if not body:
                logger.warning("Empty message body received")
                return None
            
            # Parse JSON
            try:
                message_data = json.loads(body)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in message: {e}")
                return None
            
            # Validate required fields
            if not isinstance(message_data, dict):
                logger.warning("Message data is not a dictionary")
                return None
            
            # Handle both old format (action/message) and new format (type/content)
            if 'action' in message_data and 'message' in message_data:
                # Convert old format to new format
                message_data['type'] = 'user_message' if message_data['action'] == 'sendMessage' else 'system'
                message_data['content'] = message_data['message']
            
            # Check for required fields
            required_fields = ['type', 'content']
            for field in required_fields:
                if field not in message_data:
                    logger.warning(f"Missing required field: {field}")
                    return None
            
            # Validate message type
            valid_types = ['user_message', 'ping', 'system']
            if message_data['type'] not in valid_types:
                logger.warning(f"Invalid message type: {message_data['type']}")
                return None
            
            # Validate content
            if not isinstance(message_data['content'], str) or not message_data['content'].strip():
                logger.warning("Invalid or empty message content")
                return None
            
            # Add timestamp and message ID if not present
            if 'timestamp' not in message_data:
                message_data['timestamp'] = self._get_current_timestamp()
            
            if 'messageId' not in message_data:
                import uuid
                message_data['messageId'] = str(uuid.uuid4())
            
            return message_data
            
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None
    
    async def _route_message(self, connection_id: str, session_id: str, message_data: Dict[str, Any]) -> None:
        """
        Route message to appropriate handler based on message type.
        
        Args:
            connection_id: WebSocket connection ID
            session_id: Session ID
            message_data: Parsed message data
        """
        try:
            message_type = message_data['type']
            
            if message_type == 'ping':
                # Handle ping message
                await self._handle_ping(connection_id, session_id, message_data)
            elif message_type == 'user_message':
                # Handle user message - will be integrated with chatbot engine in later tasks
                await self._handle_user_message(connection_id, session_id, message_data)
            elif message_type == 'system':
                # Handle system message
                await self._handle_system_message(connection_id, session_id, message_data)
            else:
                logger.warning(f"Unhandled message type: {message_type}")
                await self._send_error_message(connection_id, f"Unsupported message type: {message_type}")
            
        except Exception as e:
            logger.error(f"Error routing message: {e}")
            await self._send_error_message(connection_id, "Message routing failed")
    
    async def _handle_ping(self, connection_id: str, session_id: str, message_data: Dict[str, Any]) -> None:
        """
        Handle ping message for connection keep-alive.
        
        Args:
            connection_id: WebSocket connection ID
            session_id: Session ID
            message_data: Ping message data
        """
        try:
            response = {
                'type': 'pong',
                'messageId': message_data.get('messageId'),
                'timestamp': self._get_current_timestamp(),
                'sessionId': session_id
            }
            
            await self._send_message(connection_id, response)
            logger.debug(f"Pong sent to connection {connection_id}")
            
        except Exception as e:
            logger.error(f"Error handling ping: {e}")
    
    async def _handle_user_message(self, connection_id: str, session_id: str, message_data: Dict[str, Any]) -> None:
        """
        Handle user message with MBPP compliance (language detection + sentiment analysis).
        
        Args:
            connection_id: WebSocket connection ID
            session_id: Session ID
            message_data: User message data
        """
        try:
            user_text = message_data.get('content', '')
            message_id = message_data.get('messageId')
            
            if not user_text:
                await self._send_error_message(connection_id, "Empty message content")
                return
            
            # Initialize MBPP services
            language_service = create_language_service()
            sentiment_service = create_sentiment_service()
            analytics_tracker = AnalyticsTracker(
                table_name=os.environ.get('ANALYTICS_TABLE', 'chatbot-analytics'),
                region_name=os.environ.get('AWS_REGION', 'ap-southeast-1')
            )
            
            # Step 1: Detect language (MBPP requirement)
            language_result = await language_service.detect_language(user_text)
            detected_language = language_result['language_code']
            language_confidence = language_result['confidence']
            
            logger.info(f"Language detected: {detected_language} (confidence: {language_confidence:.2f})")
            
            # Step 2: Analyze sentiment (MBPP requirement)
            sentiment_result = await sentiment_service.analyze_sentiment(
                text=user_text,
                language_code=detected_language,
                session_id=session_id
            )
            
            logger.info(f"Sentiment analyzed: {sentiment_result['sentiment']} (confidence: {sentiment_result['confidence']:.2f})")
            
            # Step 3: Track analytics for MBPP compliance (with error isolation)
            try:
                analytics_tracker.track_language_detection(
                    session_id=session_id,
                    detected_language=detected_language,
                    confidence=language_confidence,
                    user_text=user_text,
                    context={'message_id': message_id}
                )
                
                analytics_tracker.track_sentiment_analysis(
                    session_id=session_id,
                    sentiment=sentiment_result['sentiment'],
                    confidence=sentiment_result['confidence'],
                    sentiment_scores=sentiment_result['sentiment_scores'],
                    requires_attention=sentiment_result['requires_attention'],
                    context={'message_id': message_id, 'language': detected_language}
                )
            except Exception as analytics_error:
                # Analytics errors should not interrupt main processing
                error_handler.handle_analytics_error(
                    analytics_error,
                    {
                        'session_id': session_id,
                        'message_id': message_id,
                        'operation': 'mbpp_analytics_tracking'
                    },
                    continue_processing=True
                )
            
            # Step 4: Get language-appropriate system messages
            system_messages = language_service.get_system_messages(detected_language)
            
            # Step 5: Process message with ChatbotEngine
            try:
                from shared.chatbot_engine import create_chatbot_engine
                from shared.session_manager import SessionManager
                
                # Initialize chatbot engine
                session_manager = SessionManager(
                    table_name=os.environ.get('SESSIONS_TABLE', 'chatbot-sessions'),
                    region_name=os.environ.get('AWS_REGION', 'ap-southeast-1')
                )
                
                chatbot_engine = create_chatbot_engine(
                    session_manager=session_manager,
                    region=os.environ.get('AWS_REGION', 'ap-southeast-1')
                )
                
                # Process message with AI
                chatbot_response = await chatbot_engine.process_message(
                    session_id=session_id,
                    message=user_text,
                    user_context={
                        'language': detected_language,
                        'sentiment': sentiment_result,
                        'message_id': message_id
                    }
                )
                
                # Send AI response
                response = {
                    'type': 'assistant_message',
                    'messageId': message_id,
                    'timestamp': self._get_current_timestamp(),
                    'sessionId': session_id,
                    'content': chatbot_response.content,
                    'query_type': chatbot_response.query_type.value if hasattr(chatbot_response.query_type, 'value') else str(chatbot_response.query_type),
                    'sources': chatbot_response.sources,
                    'tools_used': chatbot_response.tools_used,
                    'language_data': {
                        'detected_language': detected_language,
                        'language_name': language_result['language_name'],
                        'confidence': language_confidence
                    },
                    'sentiment_data': {
                        'sentiment': sentiment_result['sentiment'],
                        'confidence': sentiment_result['confidence'],
                        'requires_attention': sentiment_result['requires_attention']
                    }
                }
                
                await self._send_message(connection_id, response)
                
            except Exception as e:
                # Use error handler for comprehensive error management
                context = {
                    'session_id': session_id,
                    'message_id': message_id,
                    'detected_language': detected_language,
                    'operation': 'chatbot_processing'
                }
                
                # Handle Bedrock-related errors with graceful degradation
                if 'bedrock' in str(e).lower() or 'strand' in str(e).lower():
                    error_result = error_handler.handle_bedrock_error(e, context, fallback_enabled=True)
                    
                    if 'fallback_response' in error_result:
                        # Use fallback response from error handler
                        fallback_content = error_result['fallback_response'].get('content', [])
                        if fallback_content and fallback_content[0].get('type') == 'text':
                            fallback_text = fallback_content[0].get('text', '')
                        else:
                            fallback_text = error_result.get('user_message', 'I apologize, but I\'m temporarily unavailable.')
                    else:
                        fallback_text = error_result.get('user_message', 'I apologize, but I\'m experiencing technical difficulties.')
                else:
                    # Log other errors and provide generic fallback
                    error_handler.log_error_with_context(e, context)
                    fallback_text = "I apologize, but I'm having trouble processing your request right now. Please try again."
                
                # Send error response with fallback content
                response = {
                    'type': 'assistant_message',
                    'messageId': message_id,
                    'timestamp': self._get_current_timestamp(),
                    'sessionId': session_id,
                    'content': fallback_text,
                    'query_type': 'error_fallback',
                    'sources': [],
                    'tools_used': [],
                    'language_data': {
                        'detected_language': detected_language,
                        'language_name': language_result['language_name'],
                        'confidence': language_confidence
                    },
                    'is_fallback': True
                }
                await self._send_message(connection_id, response)
            
            # Step 6: Handle negative sentiment escalation if needed
            if sentiment_service.should_escalate(sentiment_result):
                logger.warning(f"Negative sentiment detected requiring escalation - Session: {session_id}")
                escalation_response = {
                    'type': 'escalation_notice',
                    'messageId': f"escalation_{message_id}",
                    'timestamp': self._get_current_timestamp(),
                    'sessionId': session_id,
                    'content': system_messages.get('escalation', 'Your concern has been noted and will receive priority attention.'),
                    'priority': 'high'
                }
                await self._send_message(connection_id, escalation_response)
            
            # Log comprehensive interaction for analytics
            self._log_message_event(session_id, connection_id, {
                **message_data,
                'language_data': language_result,
                'sentiment_data': sentiment_result
            }, 'multilingual_user_message')
            
            logger.info(f"MBPP-compliant message processed - Session: {session_id}, Language: {detected_language}, Sentiment: {sentiment_result['sentiment']}")
            
        except Exception as e:
            logger.error(f"Error handling user message with MBPP compliance: {e}", exc_info=True)
            await self._send_error_message(connection_id, "Failed to process user message")
    
    async def _handle_system_message(self, connection_id: str, session_id: str, message_data: Dict[str, Any]) -> None:
        """
        Handle system message.
        
        Args:
            connection_id: WebSocket connection ID
            session_id: Session ID
            message_data: System message data
        """
        try:
            content = message_data.get('content', '').lower()
            
            if content == 'status':
                # Send session status
                session = await self.session_manager.get_session(session_id)
                if session:
                    response = {
                        'type': 'status_response',
                        'messageId': message_data.get('messageId'),
                        'timestamp': self._get_current_timestamp(),
                        'sessionId': session_id,
                        'status': {
                            'sessionActive': True,
                            'createdAt': session.created_at.isoformat(),
                            'lastActivity': session.last_activity.isoformat()
                        }
                    }
                else:
                    response = {
                        'type': 'status_response',
                        'messageId': message_data.get('messageId'),
                        'timestamp': self._get_current_timestamp(),
                        'sessionId': session_id,
                        'status': {
                            'sessionActive': False
                        }
                    }
                
                await self._send_message(connection_id, response)
            else:
                logger.warning(f"Unknown system command: {content}")
                await self._send_error_message(connection_id, f"Unknown system command: {content}")
            
        except Exception as e:
            logger.error(f"Error handling system message: {e}")
            await self._send_error_message(connection_id, "Failed to process system message")
    
    async def _send_error_message(self, connection_id: str, error_message: str) -> None:
        """
        Send error message to WebSocket connection.
        
        Args:
            connection_id: WebSocket connection ID
            error_message: Error message to send
        """
        try:
            error_response = {
                'type': 'error',
                'timestamp': self._get_current_timestamp(),
                'error': error_message
            }
            
            await self._send_message(connection_id, error_response)
            
        except Exception as e:
            logger.error(f"Failed to send error message to {connection_id}: {e}")
    
    def _log_message_event(self, session_id: str, connection_id: str, message_data: Dict[str, Any], event_type: str) -> None:
        """
        Log message processing event with structured logging.
        
        Args:
            session_id: Session ID
            connection_id: WebSocket connection ID
            message_data: Message data
            event_type: Type of event (received, sent, error)
        """
        try:
            log_data = {
                'event_type': event_type,
                'session_id': session_id,
                'connection_id': connection_id,
                'message_id': message_data.get('messageId'),
                'message_type': message_data.get('type'),
                'timestamp': self._get_current_timestamp(),
                'content_length': len(message_data.get('content', ''))
            }
            
            logger.info(f"Message event logged", extra=log_data)
            
        except Exception as e:
            logger.error(f"Failed to log message event: {e}")
    
    async def _store_connection(self, connection_id: str, session_id: str, client_info: ClientInfo) -> None:
        """
        Store connection mapping in DynamoDB.
        
        Args:
            connection_id: WebSocket connection ID
            session_id: Associated session ID
            client_info: Client information
        """
        # Connection mapping is handled through session management
        # No separate connection storage needed
        logger.debug(f"Connection mapping handled via session: {connection_id} -> {session_id}")
        pass
    
    async def _remove_connection(self, connection_id: str) -> None:
        """
        Remove connection mapping from DynamoDB.
        
        Args:
            connection_id: WebSocket connection ID to remove
        """
        # Connection cleanup is handled through session management
        logger.debug(f"Connection cleanup handled via session: {connection_id}")
        pass
    
    async def _get_session_from_connection(self, connection_id: str) -> Optional[str]:
        """
        Get session ID associated with connection ID.
        
        Args:
            connection_id: WebSocket connection ID
            
        Returns:
            Session ID if found, None otherwise
        """
        # Session mapping is handled differently - session ID is passed in messages
        logger.debug(f"Session lookup for connection {connection_id} - using message-based session ID")
        return None
    
    async def _send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send message to WebSocket connection.
        
        Args:
            connection_id: WebSocket connection ID
            message: Message data to send
            
        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            self.apigateway_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message)
            )
            logger.debug(f"Message sent to connection {connection_id}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'GoneException':
                logger.warning(f"Connection {connection_id} is no longer available")
                # Clean up stale connection
                await self._remove_connection(connection_id)
            else:
                logger.error(f"API Gateway error sending message to {connection_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message to {connection_id}: {e}")
            return False
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    
    def _get_ttl(self) -> int:
        """Get TTL timestamp (24 hours from now)."""
        import time
        return int(time.time()) + (24 * 60 * 60)


# Global connection manager instance
connection_manager = WebSocketConnectionManager()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for WebSocket events.
    
    Args:
        event: Lambda event containing WebSocket connection info
        context: Lambda context object
        
    Returns:
        Response dictionary with statusCode and body
    """
    try:
        request_context = event.get('requestContext', {})
        route_key = request_context.get('routeKey')
        connection_id = request_context.get('connectionId')
        
        if not connection_id:
            logger.error("No connection ID found in event")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid WebSocket event'})
            }
        
        logger.info(f"Processing WebSocket event - Route: {route_key}, Connection: {connection_id}")
        
        # Route to appropriate handler
        if route_key == '$connect':
            return asyncio.run(connection_manager.handle_connect(connection_id, event))
        elif route_key == '$disconnect':
            return asyncio.run(connection_manager.handle_disconnect(connection_id, event))
        elif route_key == '$default':
            return asyncio.run(connection_manager.handle_message(connection_id, event))
        else:
            logger.warning(f"Unknown route key: {route_key}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Unknown route'})
            }
        
    except Exception as e:
        logger.error(f"Error processing WebSocket event: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }