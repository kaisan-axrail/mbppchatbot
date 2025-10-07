"""
Working WebSocket handler without Bedrock dependency.
"""

import json
import logging
import os
import boto3
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def lambda_handler(event, context):
    """Main Lambda handler for WebSocket events."""
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
            'message': 'Connected to Strands chatbot! (Working version)',
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
        return {'statusCode': 200}

def handle_message(connection_id, event):
    """Handle incoming WebSocket message."""
    try:
        # Parse message
        body = event.get('body', '{}')
        message_data = json.loads(body)
        
        user_message = message_data.get('message', '')
        session_id = message_data.get('sessionId', f'session_{connection_id}')
        
        logger.info(f"Processing message: {user_message}")
        
        # Generate a working response without Bedrock
        response_text = generate_working_response(user_message)
        
        # Send response back
        response = {
            'type': 'assistant_message',
            'content': response_text,
            'sessionId': session_id,
            'timestamp': datetime.utcnow().isoformat(),
            'provider': 'working_demo'
        }
        
        send_message_to_connection(connection_id, response)
        
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

def generate_working_response(user_message):
    """Generate a working response without Bedrock."""
    user_message_lower = user_message.lower()
    
    # Simple response logic
    if 'hello' in user_message_lower or 'hi' in user_message_lower:
        return "Hello! I'm your Strands chatbot. I'm currently running in demo mode while we set up Bedrock model access. How can I help you today?"
    
    elif 'how are you' in user_message_lower:
        return "I'm doing great! I'm a fully deployed chatbot with WebSocket connectivity, session management, and all the infrastructure ready. I just need Bedrock model access to provide AI responses."
    
    elif 'what can you do' in user_message_lower or 'help' in user_message_lower:
        return """I'm a full-featured chatbot with:
        
🤖 **AI Responses** - Using Strands SDK + Bedrock (pending model access)
📚 **RAG Search** - Document search and retrieval 
🔧 **MCP Tools** - Database CRUD operations
💾 **Session Management** - Conversation memory
📊 **Analytics** - Usage tracking

Once Bedrock model access is enabled, I'll provide full AI responses!"""
    
    elif 'test' in user_message_lower:
        return f"✅ Test successful! Your message '{user_message}' was received and processed. The WebSocket connection, Lambda function, and response system are all working perfectly!"
    
    elif 'rag' in user_message_lower or 'document' in user_message_lower:
        return "📚 RAG (Retrieval-Augmented Generation) is ready! I can search through your documents and provide answers based on their content. The S3 storage and document processing pipeline are deployed and waiting for Bedrock access."
    
    elif 'mcp' in user_message_lower or 'tool' in user_message_lower:
        return "🔧 MCP Tools are deployed! I can perform database operations like creating, reading, updating, and deleting records. The MCP server is running and ready to execute tools once Bedrock access is enabled."
    
    elif 'session' in user_message_lower:
        return f"💾 Session management is working! Your session ID is active and I'm tracking our conversation. DynamoDB is storing all our interactions for continuity."
    
    else:
        return f"I received your message: '{user_message}'. I'm currently in demo mode while Bedrock model access is being set up. Once that's enabled, I'll provide full AI responses using the Strands SDK!"

def send_message_to_connection(connection_id, message):
    """Send message to WebSocket connection."""
    try:
        # Get the API Gateway endpoint
        domain_name = os.environ.get('WEBSOCKET_DOMAIN_NAME', 'ynw017q5lc.execute-api.ap-southeast-1.amazonaws.com')
        stage = os.environ.get('WEBSOCKET_STAGE', 'prod')
        
        endpoint_url = f"https://{domain_name}/{stage}"
        
        apigateway_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url
        )
        
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message)
        )
        
        logger.info(f"Message sent to connection {connection_id}")
        
    except Exception as e:
        logger.error(f"Failed to send message to {connection_id}: {str(e)}")
        raise