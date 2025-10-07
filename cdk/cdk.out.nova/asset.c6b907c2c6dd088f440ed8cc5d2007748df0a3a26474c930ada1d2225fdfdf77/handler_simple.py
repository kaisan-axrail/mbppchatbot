"""
Simplified WebSocket handler that actually works.
"""

import json
import logging
import os
import boto3
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')

def lambda_handler(event, context):
    """
    Main Lambda handler for WebSocket events.
    """
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        route_key = event.get('requestContext', {}).get('routeKey')
        connection_id = event.get('requestContext', {}).get('connectionId')
        
        if route_key == '$connect':
            return handle_connect(connection_id, event)
        elif route_key == '$disconnect':
            return handle_disconnect(connection_id, event)
        elif route_key == '$default':
            return handle_message(connection_id, event)
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
        
        # Send welcome message
        send_message_to_connection(connection_id, {
            'type': 'connection_established',
            'message': 'Connected to chatbot successfully',
            'timestamp': datetime.utcnow().isoformat()
        })
        
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
        return {'statusCode': 200}  # Always return 200 for disconnect

def handle_message(connection_id, event):
    """Handle incoming WebSocket message."""
    try:
        # Parse message
        body = event.get('body', '{}')
        message_data = json.loads(body)
        
        user_message = message_data.get('message', '')
        session_id = message_data.get('sessionId', 'default')
        
        logger.info(f"Processing message: {user_message[:100]}...")
        
        # Generate response using Bedrock
        response_text = generate_bedrock_response(user_message)
        
        # Send response back
        response = {
            'type': 'assistant_message',
            'content': response_text,
            'sessionId': session_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        send_message_to_connection(connection_id, response)
        
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Message handling error: {str(e)}", exc_info=True)
        
        # Send error response to user
        try:
            error_response = {
                'type': 'error',
                'content': 'I apologize, but I encountered an error processing your message. Please try again.',
                'timestamp': datetime.utcnow().isoformat()
            }
            send_message_to_connection(connection_id, error_response)
        except:
            pass
            
        return {'statusCode': 500}

def generate_bedrock_response(user_message):
    """Generate response using AWS Bedrock."""
    try:
        # Prepare the request for Claude
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.7,
            "messages": [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        }
        
        # Try different model configurations
        model_ids = [
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0",  # Cross-region inference profile
            "anthropic.claude-3-5-sonnet-20241022-v2:0"      # Direct model access
        ]
        
        for model_id in model_ids:
            try:
                logger.info(f"Trying model: {model_id}")
                
                response = bedrock.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )
                
                response_body = json.loads(response['body'].read())
                
                if 'content' in response_body and response_body['content']:
                    content = response_body['content'][0].get('text', '')
                    logger.info(f"Successfully generated response using {model_id}")
                    return content
                    
            except Exception as e:
                logger.warning(f"Model {model_id} failed: {str(e)}")
                continue
        
        # If all models fail, return fallback
        return "I apologize, but I'm currently experiencing technical difficulties. Please try again in a few moments."
        
    except Exception as e:
        logger.error(f"Bedrock error: {str(e)}")
        return "I'm sorry, but I'm unable to process your request right now. Please try again later."

def send_message_to_connection(connection_id, message):
    """Send message to WebSocket connection."""
    try:
        # Get API Gateway management client
        domain_name = os.environ.get('WEBSOCKET_DOMAIN_NAME')
        stage = os.environ.get('WEBSOCKET_STAGE', 'prod')
        
        if domain_name:
            endpoint_url = f"https://{domain_name}/{stage}"
        else:
            # Extract from context if available
            endpoint_url = f"https://execute-api.{os.environ.get('AWS_REGION', 'ap-southeast-1')}.amazonaws.com/{stage}"
        
        apigateway_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
        
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message)
        )
        
        logger.debug(f"Message sent to connection {connection_id}")
        
    except Exception as e:
        logger.error(f"Failed to send message to {connection_id}: {str(e)}")
        raise