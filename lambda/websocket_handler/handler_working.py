"""
Working WebSocket handler without Bedrock dependency.
Updated to fix authentication issues and Nova Pro API format.
Added debug logging for response parsing.
"""

import json
import logging
import os
import boto3
import asyncio
from datetime import datetime

# Import Nova Pro chatbot components
from shared.chatbot_engine import ChatbotEngine
from shared.session_manager import SessionManager
from shared.exceptions import ChatbotEngineError

# Import MBPP Workflow Agent
import sys
sys.path.insert(0, '/opt/python')
from mbpp_agent import MBPPAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to cache WebSocket endpoint
_websocket_endpoint = None

def lambda_handler(event, context):
    """Main Lambda handler for WebSocket events."""
    global _websocket_endpoint
    
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract WebSocket endpoint from event context
        request_context = event.get('requestContext', {})
        if not _websocket_endpoint:
            domain_name = request_context.get('domainName')
            stage = request_context.get('stage')
            if domain_name and stage:
                _websocket_endpoint = f"https://{domain_name}/{stage}"
                logger.info(f"Cached WebSocket endpoint: {_websocket_endpoint}")
        
        route_key = request_context.get('routeKey')
        connection_id = request_context.get('connectionId')
        
        if route_key == '$connect':
            return handle_connect(connection_id, event)
        elif route_key == '$disconnect':
            return handle_disconnect(connection_id, event)
        elif route_key == '$default':
            return handle_message(connection_id, event)
        elif route_key == 'conversation-update':
            return handle_conversation_update(connection_id, event)
        else:
            logger.warning(f"Unknown route: {route_key}")
            return {'statusCode': 400}
            
    except Exception as e:
        logger.error(f"Handler error: {str(e)}", exc_info=True)
        return {'statusCode': 500}

def handle_connect(connection_id, event):
    """Handle WebSocket connection."""
    try:
        logger.info(f"Connection established: {connection_id}")
        return {'statusCode': 200}
    except Exception as e:
        logger.error(f"Connect error: {str(e)}")
        return {'statusCode': 500}

def handle_disconnect(connection_id, event):
    """Handle WebSocket disconnection."""
    try:
        logger.info(f"Connection closed: {connection_id}")
        return {'statusCode': 200}
    except Exception as e:
        logger.error(f"Disconnect error: {str(e)}")
        return {'statusCode': 200}

def handle_message(connection_id, event):
    """Handle incoming WebSocket message using Nova Pro chatbot engine."""
    try:
        # Parse message
        body = event.get('body', '{}')
        message_data = json.loads(body)
        
        user_message = message_data.get('message', '')
        session_id = message_data.get('sessionId', f'session_{connection_id}')
        has_image = message_data.get('hasImage', False)
        image_data = message_data.get('imageData')
        
        logger.info(f"Processing message with Nova Pro: {user_message}, has_image: {has_image}")
        
        # Use the actual Nova Pro chatbot engine
        response_data = process_with_nova_pro(user_message, session_id, has_image, image_data)
        
        # Send response back
        send_message_to_connection(connection_id, response_data)
        
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Message handling error: {str(e)}", exc_info=True)
        
        # Send error response to user
        try:
            error_response = {
                'type': 'error',
                'content': 'I apologize, but I encountered an error. Please try again.',
                'timestamp': datetime.utcnow().isoformat()
            }
            send_message_to_connection(connection_id, error_response)
        except:
            pass
            
        return {'statusCode': 500}

def handle_conversation_update(connection_id, event):
    """Handle conversation update requests."""
    try:
        logger.info(f"Conversation update request from {connection_id}")
        
        # Parse the request body
        body = event.get('body', '{}')
        update_data = json.loads(body)
        
        # For now, just acknowledge the update
        response = {
            'type': 'conversation_update_ack',
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        send_message_to_connection(connection_id, response)
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Conversation update error: {str(e)}")
        return {'statusCode': 500}

def process_with_nova_pro(user_message: str, session_id: str, has_image: bool = False, image_data: str = None) -> dict:
    """Process message using MBPP Workflow Agent or Nova Pro chatbot engine."""
    try:
        # Check if this is a workflow trigger
        mbpp_agent = MBPPAgent()
        result = mbpp_agent.process_message(
            message=user_message,
            session_id=session_id,
            has_image=has_image,
            image_data=image_data
        )
        
        # If it's a workflow, return workflow response
        if result.get('type') in ['workflow', 'workflow_complete']:
            response_content = result.get('response', '')
            # Convert AgentResult to string if needed
            if hasattr(response_content, 'content'):
                response_content = str(response_content.content)
            elif not isinstance(response_content, str):
                response_content = str(response_content)
            
            # Add quick replies for incident confirmation and remove option text
            quick_replies = None
            if 'confirm you would like to report an incident' in response_content.lower():
                quick_replies = ['Yes, report an incident', 'Not an incident (Service Complaint / Feedback)']
                # Keep only the question, remove everything after it
                if 'Image detected.' in response_content:
                    response_content = 'Image detected. Can you confirm you would like to report an incident?'
                else:
                    # Find the question and keep only that
                    lines = response_content.split('\n')
                    for i, line in enumerate(lines):
                        if 'confirm you would like to report an incident' in line.lower():
                            response_content = '\n'.join(lines[:i+1]).strip()
                            break
            elif 'blocking the road' in response_content.lower() or 'causing hazard' in response_content.lower():
                quick_replies = ['Yes', 'No']
            
            return {
                'type': 'assistant_message',
                'content': response_content,
                'sessionId': session_id,
                'timestamp': datetime.utcnow().isoformat(),
                'provider': 'mbpp-workflow',
                'workflowType': result.get('workflow_type'),
                'workflowId': result.get('workflow_id'),
                'quickReplies': quick_replies
            }
        
        # Otherwise use Nova Pro engine
        engine = ChatbotEngine(region=os.environ.get('AWS_REGION', 'ap-southeast-1'))
        
        # Process message asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check if session exists, create if not
            session = loop.run_until_complete(
                engine.session_manager.get_session(session_id)
            )
            
            if not session:
                logger.info(f"Session {session_id} not found, creating new session")
                # Create a new session - this will generate a new ID
                new_session_id = loop.run_until_complete(
                    engine.session_manager.create_session()
                )
                # Use the generated session ID instead
                session_id = new_session_id
                logger.info(f"Created new session: {session_id}")
            
            response = loop.run_until_complete(
                engine.process_message(
                    session_id=session_id,
                    message=user_message,
                    user_context={"websocket_connection": True}
                )
            )
            
            # Format response for WebSocket
            return {
                'type': 'assistant_message',
                'content': response.content,
                'sessionId': session_id,
                'timestamp': datetime.utcnow().isoformat(),
                'provider': 'nova-pro',
                'queryType': response.query_type.value,
                'sources': response.sources,
                'toolsUsed': response.tools_used,
                'responseTime': response.response_time
            }
            
        finally:
            loop.close()
            
    except ChatbotEngineError as e:
        logger.error(f"Nova Pro engine error: {str(e)}")
        return {
            'type': 'error',
            'content': f"I encountered an error processing your request: {str(e)}",
            'sessionId': session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'provider': 'nova-pro-error'
        }
    except Exception as e:
        logger.error(f"Unexpected error in Nova Pro processing: {str(e)}")
        return {
            'type': 'error',
            'content': "I'm experiencing technical difficulties. Please try again in a moment.",
            'sessionId': session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'provider': 'nova-pro-error'
        }

def send_message_to_connection(connection_id, message):
    """Send message to WebSocket connection."""
    global _websocket_endpoint
    
    try:
        # Use cached endpoint from event context
        endpoint_url = _websocket_endpoint
        
        if not endpoint_url:
            # Fallback to environment variables
            domain_name = os.environ.get('WEBSOCKET_DOMAIN_NAME')
            stage = os.environ.get('WEBSOCKET_STAGE', 'prod')
            if domain_name:
                endpoint_url = f"https://{domain_name}/{stage}"
            else:
                raise ValueError("WebSocket endpoint not available")
        
        apigateway_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
        
        logger.info(f"Sending to {endpoint_url} for connection {connection_id}")
        
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message)
        )
        
        logger.info(f"Message sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send message to {connection_id}: {str(e)}")
        raise