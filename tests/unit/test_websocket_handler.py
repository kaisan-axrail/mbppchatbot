"""
Unit tests for WebSocket handler Lambda function.

This module tests the WebSocket connection management and message routing
functionality using pytest with proper mocking of AWS services.
"""

import json
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

# Import the module under test
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'websocket_handler'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))

import sys
import os
import importlib.util

# Load the websocket handler module directly
websocket_handler_path = os.path.join(os.path.dirname(__file__), '../../lambda/websocket_handler/handler.py')
spec = importlib.util.spec_from_file_location("websocket_handler", websocket_handler_path)
websocket_handler = importlib.util.module_from_spec(spec)

# Add shared modules to path for the handler to import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

spec.loader.exec_module(websocket_handler)

WebSocketConnectionManager = websocket_handler.WebSocketConnectionManager
lambda_handler = websocket_handler.lambda_handler
from shared.session_models import Session, ClientInfo, SessionStatus
from shared.exceptions import SessionNotFoundError


class TestWebSocketConnectionManager:
    """Test cases for WebSocketConnectionManager class."""
    
    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables."""
        with patch.dict(os.environ, {
            'AWS_REGION': 'us-east-1',
            'SESSIONS_TABLE': 'test-sessions',
            'CONNECTIONS_TABLE': 'test-connections',
            'SESSION_TIMEOUT_MINUTES': '30',
            'WEBSOCKET_DOMAIN_NAME': 'test.execute-api.us-east-1.amazonaws.com',
            'WEBSOCKET_STAGE': 'test'
        }):
            yield
    
    @pytest.fixture
    def connection_manager(self, mock_env_vars):
        """Create WebSocketConnectionManager instance with mocked dependencies."""
        with patch('handler.boto3.resource') as mock_resource, \
             patch('handler.boto3.client') as mock_client, \
             patch('handler.SessionManager') as mock_session_manager:
            
            # Mock DynamoDB resource
            mock_table = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            # Mock API Gateway client
            mock_api_client = Mock()
            mock_client.return_value = mock_api_client
            
            # Mock session manager
            mock_sm = Mock()
            mock_session_manager.return_value = mock_sm
            
            manager = WebSocketConnectionManager()
            manager.connections_table_ref = mock_table
            manager.apigateway_client = mock_api_client
            manager.session_manager = mock_sm
            
            return manager
    
    @pytest.fixture
    def sample_connect_event(self):
        """Sample WebSocket connect event."""
        return {
            'requestContext': {
                'routeKey': '$connect',
                'connectionId': 'test-connection-123',
                'identity': {
                    'sourceIp': '192.168.1.1'
                }
            },
            'headers': {
                'User-Agent': 'Mozilla/5.0 Test Browser'
            }
        }
    
    @pytest.fixture
    def sample_message_event(self):
        """Sample WebSocket message event."""
        return {
            'requestContext': {
                'routeKey': '$default',
                'connectionId': 'test-connection-123'
            },
            'body': json.dumps({
                'type': 'user_message',
                'content': 'Hello, chatbot!',
                'messageId': 'msg-123'
            })
        }
    
    @pytest.mark.asyncio
    async def test_handle_connect_success(self, connection_manager, sample_connect_event):
        """Test successful WebSocket connection handling."""
        # Mock session manager
        connection_manager.session_manager.create_session = AsyncMock(return_value='session-123')
        
        # Mock DynamoDB put_item
        connection_manager.connections_table_ref.put_item = Mock()
        
        # Mock API Gateway post_to_connection
        connection_manager.apigateway_client.post_to_connection = Mock()
        
        result = await connection_manager.handle_connect('test-connection-123', sample_connect_event)
        
        # Verify session creation was called
        connection_manager.session_manager.create_session.assert_called_once()
        
        # Verify connection was stored
        connection_manager.connections_table_ref.put_item.assert_called_once()
        
        # Verify welcome message was sent
        connection_manager.apigateway_client.post_to_connection.assert_called_once()
        
        # Verify response
        assert result['statusCode'] == 200
        assert 'Connected successfully' in result['body']
    
    @pytest.mark.asyncio
    async def test_handle_disconnect_success(self, connection_manager):
        """Test successful WebSocket disconnection handling."""
        # Mock getting session from connection
        connection_manager._get_session_from_connection = AsyncMock(return_value='session-123')
        
        # Mock session manager
        connection_manager.session_manager.close_session = AsyncMock()
        
        # Mock connection removal
        connection_manager._remove_connection = AsyncMock()
        
        result = await connection_manager.handle_disconnect('test-connection-123', {})
        
        # Verify session was closed
        connection_manager.session_manager.close_session.assert_called_once_with('session-123')
        
        # Verify connection was removed
        connection_manager._remove_connection.assert_called_once_with('test-connection-123')
        
        # Verify response
        assert result['statusCode'] == 200
        assert 'Disconnected successfully' in result['body']
    
    @pytest.mark.asyncio
    async def test_handle_message_success(self, connection_manager, sample_message_event):
        """Test successful message handling."""
        # Mock getting session from connection
        connection_manager._get_session_from_connection = AsyncMock(return_value='session-123')
        
        # Mock session manager
        connection_manager.session_manager.update_activity = AsyncMock()
        
        # Mock message routing
        connection_manager._route_message = AsyncMock()
        
        result = await connection_manager.handle_message('test-connection-123', sample_message_event)
        
        # Verify session activity was updated
        connection_manager.session_manager.update_activity.assert_called_once_with('session-123')
        
        # Verify message was routed
        connection_manager._route_message.assert_called_once()
        
        # Verify response
        assert result['statusCode'] == 200
        assert 'Message processed successfully' in result['body']
    
    @pytest.mark.asyncio
    async def test_handle_message_no_session(self, connection_manager, sample_message_event):
        """Test message handling when no session is found."""
        # Mock no session found
        connection_manager._get_session_from_connection = AsyncMock(return_value=None)
        connection_manager._send_error_message = AsyncMock()
        
        result = await connection_manager.handle_message('test-connection-123', sample_message_event)
        
        # Verify error message was sent
        connection_manager._send_error_message.assert_called_once_with('test-connection-123', 'Session not found')
        
        # Verify error response
        assert result['statusCode'] == 400
        assert 'Session not found' in result['body']
    
    @pytest.mark.asyncio
    async def test_handle_message_session_expired(self, connection_manager, sample_message_event):
        """Test message handling when session is expired."""
        # Mock session found but expired during update
        connection_manager._get_session_from_connection = AsyncMock(return_value='session-123')
        connection_manager.session_manager.update_activity = AsyncMock(side_effect=SessionNotFoundError('session-123'))
        connection_manager._send_error_message = AsyncMock()
        
        result = await connection_manager.handle_message('test-connection-123', sample_message_event)
        
        # Verify error message was sent
        connection_manager._send_error_message.assert_called_once_with('test-connection-123', 'Session expired')
        
        # Verify error response
        assert result['statusCode'] == 400
        assert 'Session expired' in result['body']
    
    def test_parse_message_valid(self, connection_manager):
        """Test parsing valid message."""
        event = {
            'body': json.dumps({
                'type': 'user_message',
                'content': 'Hello, world!',
                'messageId': 'msg-123'
            })
        }
        
        result = connection_manager._parse_message(event)
        
        assert result is not None
        assert result['type'] == 'user_message'
        assert result['content'] == 'Hello, world!'
        assert result['messageId'] == 'msg-123'
        assert 'timestamp' in result
    
    def test_parse_message_invalid_json(self, connection_manager):
        """Test parsing message with invalid JSON."""
        event = {
            'body': 'invalid json'
        }
        
        result = connection_manager._parse_message(event)
        
        assert result is None
    
    def test_parse_message_missing_required_fields(self, connection_manager):
        """Test parsing message with missing required fields."""
        event = {
            'body': json.dumps({
                'type': 'user_message'
                # Missing 'content' field
            })
        }
        
        result = connection_manager._parse_message(event)
        
        assert result is None
    
    def test_parse_message_invalid_type(self, connection_manager):
        """Test parsing message with invalid type."""
        event = {
            'body': json.dumps({
                'type': 'invalid_type',
                'content': 'Hello, world!'
            })
        }
        
        result = connection_manager._parse_message(event)
        
        assert result is None
    
    def test_parse_message_empty_content(self, connection_manager):
        """Test parsing message with empty content."""
        event = {
            'body': json.dumps({
                'type': 'user_message',
                'content': ''
            })
        }
        
        result = connection_manager._parse_message(event)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_route_message_ping(self, connection_manager):
        """Test routing ping message."""
        connection_manager._handle_ping = AsyncMock()
        
        message_data = {
            'type': 'ping',
            'content': 'ping',
            'messageId': 'msg-123'
        }
        
        await connection_manager._route_message('conn-123', 'session-123', message_data)
        
        connection_manager._handle_ping.assert_called_once_with('conn-123', 'session-123', message_data)
    
    @pytest.mark.asyncio
    async def test_route_message_user_message(self, connection_manager):
        """Test routing user message."""
        connection_manager._handle_user_message = AsyncMock()
        
        message_data = {
            'type': 'user_message',
            'content': 'Hello!',
            'messageId': 'msg-123'
        }
        
        await connection_manager._route_message('conn-123', 'session-123', message_data)
        
        connection_manager._handle_user_message.assert_called_once_with('conn-123', 'session-123', message_data)
    
    @pytest.mark.asyncio
    async def test_handle_ping(self, connection_manager):
        """Test ping message handling."""
        connection_manager._send_message = AsyncMock()
        
        message_data = {
            'type': 'ping',
            'messageId': 'msg-123'
        }
        
        await connection_manager._handle_ping('conn-123', 'session-123', message_data)
        
        # Verify pong response was sent
        connection_manager._send_message.assert_called_once()
        call_args = connection_manager._send_message.call_args
        assert call_args[0][0] == 'conn-123'  # connection_id
        response = call_args[0][1]  # response data
        assert response['type'] == 'pong'
        assert response['messageId'] == 'msg-123'
        assert response['sessionId'] == 'session-123'
    
    @pytest.mark.asyncio
    async def test_handle_user_message(self, connection_manager):
        """Test user message handling."""
        connection_manager._send_message = AsyncMock()
        
        message_data = {
            'type': 'user_message',
            'content': 'Hello!',
            'messageId': 'msg-123'
        }
        
        await connection_manager._handle_user_message('conn-123', 'session-123', message_data)
        
        # Verify acknowledgment was sent
        connection_manager._send_message.assert_called_once()
        call_args = connection_manager._send_message.call_args
        response = call_args[0][1]  # response data
        assert response['type'] == 'message_received'
        assert response['sessionId'] == 'session-123'


class TestLambdaHandler:
    """Test cases for lambda_handler function."""
    
    @pytest.fixture
    def mock_connection_manager(self):
        """Mock WebSocketConnectionManager."""
        # Since we're importing the module directly, we need to patch the global variable
        with patch.object(websocket_handler, 'connection_manager') as mock_manager:
            yield mock_manager
    
    def test_lambda_handler_connect(self, mock_connection_manager):
        """Test lambda handler for connect event."""
        event = {
            'requestContext': {
                'routeKey': '$connect',
                'connectionId': 'test-connection-123'
            }
        }
        
        mock_connection_manager.handle_connect = AsyncMock(return_value={
            'statusCode': 200,
            'body': json.dumps({'message': 'Connected'})
        })
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        assert 'Connected' in result['body']
    
    def test_lambda_handler_disconnect(self, mock_connection_manager):
        """Test lambda handler for disconnect event."""
        event = {
            'requestContext': {
                'routeKey': '$disconnect',
                'connectionId': 'test-connection-123'
            }
        }
        
        mock_connection_manager.handle_disconnect = AsyncMock(return_value={
            'statusCode': 200,
            'body': json.dumps({'message': 'Disconnected'})
        })
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        assert 'Disconnected' in result['body']
    
    def test_lambda_handler_message(self, mock_connection_manager):
        """Test lambda handler for message event."""
        event = {
            'requestContext': {
                'routeKey': '$default',
                'connectionId': 'test-connection-123'
            },
            'body': json.dumps({
                'type': 'user_message',
                'content': 'Hello!'
            })
        }
        
        mock_connection_manager.handle_message = AsyncMock(return_value={
            'statusCode': 200,
            'body': json.dumps({'message': 'Processed'})
        })
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 200
        assert 'Processed' in result['body']
    
    def test_lambda_handler_no_connection_id(self):
        """Test lambda handler with missing connection ID."""
        event = {
            'requestContext': {
                'routeKey': '$connect'
                # Missing connectionId
            }
        }
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 400
        assert 'Invalid WebSocket event' in result['body']
    
    def test_lambda_handler_unknown_route(self):
        """Test lambda handler with unknown route."""
        event = {
            'requestContext': {
                'routeKey': 'unknown_route',
                'connectionId': 'test-connection-123'
            }
        }
        
        result = lambda_handler(event, {})
        
        assert result['statusCode'] == 400
        assert 'Unknown route' in result['body']
    
    def test_lambda_handler_exception(self):
        """Test lambda handler with exception."""
        event = {
            'requestContext': {
                'routeKey': '$connect',
                'connectionId': 'test-connection-123'
            }
        }
        
        # Mock an exception during processing
        with patch.object(websocket_handler, 'connection_manager') as mock_manager:
            mock_manager.handle_connect = AsyncMock(side_effect=Exception('Test error'))
            
            result = lambda_handler(event, {})
            
            assert result['statusCode'] == 500
            assert 'Internal server error' in result['body']


if __name__ == '__main__':
    pytest.main([__file__])