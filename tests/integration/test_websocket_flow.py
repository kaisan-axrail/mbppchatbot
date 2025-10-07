"""
Integration tests for WebSocket connection and message flow.

These tests verify the end-to-end WebSocket functionality including
connection establishment, message processing, and session management.
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Import the components we're testing
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


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""
    
    @pytest.fixture
    def mock_aws_services(self):
        """Mock AWS services for integration testing."""
        with patch('boto3.resource') as mock_resource, \
             patch('boto3.client') as mock_client:
            
            # Mock DynamoDB table
            mock_table = Mock()
            mock_table.put_item = Mock()
            mock_table.get_item = Mock()
            mock_table.update_item = Mock()
            mock_table.delete_item = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            # Mock API Gateway client
            mock_api_client = Mock()
            mock_api_client.post_to_connection = Mock()
            mock_client.return_value = mock_api_client
            
            yield {
                'dynamodb_table': mock_table,
                'api_client': mock_api_client
            }
    
    @pytest.mark.asyncio
    async def test_complete_websocket_connection_flow(self, mock_aws_services):
        """Test complete WebSocket connection lifecycle."""
        connection_id = "test-connection-123"
        
        # Mock session creation
        mock_aws_services['dynamodb_table'].put_item.return_value = {}
        mock_aws_services['dynamodb_table'].get_item.return_value = {
            'Item': {
                'connection_id': connection_id,
                'session_id': 'test-session-123',
                'connected_at': datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Test connection
        connect_event = {
            'requestContext': {
                'routeKey': '$connect',
                'connectionId': connection_id,
                'identity': {'sourceIp': '127.0.0.1'}
            },
            'headers': {'User-Agent': 'test-agent'}
        }
        
        with patch.object(websocket_handler, 'connection_manager') as mock_manager:
            mock_manager.handle_connect = AsyncMock(return_value={
                'statusCode': 200,
                'body': json.dumps({'message': 'Connected'})
            })
            
            result = lambda_handler(connect_event, {})
            assert result['statusCode'] == 200
            mock_manager.handle_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_websocket_message_processing_flow(self, mock_aws_services):
        """Test WebSocket message processing end-to-end."""
        connection_id = "test-connection-456"
        session_id = "test-session-456"
        
        # Mock session lookup
        mock_aws_services['dynamodb_table'].get_item.return_value = {
            'Item': {
                'connection_id': connection_id,
                'session_id': session_id,
                'connected_at': datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Test message processing
        message_event = {
            'requestContext': {
                'routeKey': '$default',
                'connectionId': connection_id
            },
            'body': json.dumps({
                'type': 'user_message',
                'content': 'Hello, chatbot!',
                'messageId': str(uuid.uuid4())
            })
        }
        
        with patch.object(websocket_handler, 'connection_manager') as mock_manager:
            mock_manager.handle_message = AsyncMock(return_value={
                'statusCode': 200,
                'body': json.dumps({'message': 'Message processed'})
            })
            
            result = lambda_handler(message_event, {})
            assert result['statusCode'] == 200
            mock_manager.handle_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_flow(self, mock_aws_services):
        """Test WebSocket disconnection flow."""
        connection_id = "test-connection-789"
        
        # Mock connection cleanup
        mock_aws_services['dynamodb_table'].delete_item.return_value = {}
        
        # Test disconnection
        disconnect_event = {
            'requestContext': {
                'routeKey': '$disconnect',
                'connectionId': connection_id
            }
        }
        
        with patch.object(websocket_handler, 'connection_manager') as mock_manager:
            mock_manager.handle_disconnect = AsyncMock(return_value={
                'statusCode': 200,
                'body': json.dumps({'message': 'Disconnected'})
            })
            
            result = lambda_handler(disconnect_event, {})
            assert result['statusCode'] == 200
            mock_manager.handle_disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_activity_update_integration(self, mock_aws_services):
        """Test session activity update during message processing."""
        connection_manager = WebSocketConnectionManager()
        
        # Mock session manager
        with patch.object(connection_manager, 'session_manager') as mock_session_mgr:
            mock_session_mgr.update_activity = AsyncMock()
            mock_session_mgr.get_session = AsyncMock(return_value=Mock(
                session_id='test-session',
                is_active=True
            ))
            
            # Mock connection lookup
            with patch.object(connection_manager, '_get_session_from_connection', 
                            return_value='test-session'):
                
                # Mock message parsing
                with patch.object(connection_manager, '_parse_message', 
                                return_value={'type': 'ping', 'content': 'ping'}):
                    
                    # Mock message routing
                    with patch.object(connection_manager, '_route_message') as mock_route:
                        mock_route.return_value = None
                        
                        # Test message handling
                        event = {
                            'body': json.dumps({'type': 'ping', 'content': 'ping'})
                        }
                        
                        result = await connection_manager.handle_message('conn-123', event)
                        
                        # Verify session activity was updated
                        mock_session_mgr.update_activity.assert_called_once_with('test-session')
                        assert result['statusCode'] == 200
    
    @pytest.mark.asyncio
    async def test_ping_pong_integration(self, mock_aws_services):
        """Test ping-pong message flow integration."""
        connection_manager = WebSocketConnectionManager()
        
        # Mock dependencies
        with patch.object(connection_manager, '_send_message') as mock_send:
            mock_send.return_value = True
            
            # Test ping handling
            message_data = {
                'type': 'ping',
                'content': 'ping',
                'messageId': 'ping-123'
            }
            
            await connection_manager._handle_ping('conn-123', 'session-123', message_data)
            
            # Verify pong was sent
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            response = call_args[0][1]  # response data
            
            assert response['type'] == 'pong'
            assert response['messageId'] == 'ping-123'
            assert response['sessionId'] == 'session-123'
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_aws_services):
        """Test error handling in WebSocket flow."""
        connection_id = "test-connection-error"
        
        # Test with invalid message format
        invalid_message_event = {
            'requestContext': {
                'routeKey': '$default',
                'connectionId': connection_id
            },
            'body': 'invalid json'
        }
        
        with patch.object(websocket_handler, 'connection_manager') as mock_manager:
            mock_manager.handle_message = AsyncMock(return_value={
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid message format'})
            })
            
            result = lambda_handler(invalid_message_event, {})
            assert result['statusCode'] == 400
            assert 'error' in result['body']


class TestSessionLifecycleIntegration:
    """Integration tests for session lifecycle management."""
    
    @pytest.fixture
    def mock_session_components(self):
        """Mock session-related components."""
        with patch('shared.session_manager.boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_table.put_item = Mock()
            mock_table.get_item = Mock()
            mock_table.update_item = Mock()
            mock_table.scan = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            yield mock_table
    
    @pytest.mark.asyncio
    async def test_session_creation_and_retrieval_flow(self, mock_session_components):
        """Test complete session creation and retrieval flow."""
        from shared.session_manager import SessionManager
        from shared.session_models import ClientInfo
        
        # Mock successful session creation
        session_id = str(uuid.uuid4())
        mock_session_components.put_item.return_value = {}
        mock_session_components.get_item.return_value = {
            'Item': {
                'session_id': session_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_activity': datetime.now(timezone.utc).isoformat(),
                'is_active': True,
                'client_info': {'user_agent': 'test-agent'},
                'metadata': {},
                'ttl': 1234567890
            }
        }
        
        session_manager = SessionManager('test-table')
        
        # Test session creation
        client_info = ClientInfo(user_agent='test-agent', ip_address='127.0.0.1')
        created_session_id = await session_manager.create_session(client_info)
        
        assert created_session_id is not None
        mock_session_components.put_item.assert_called_once()
        
        # Test session retrieval
        retrieved_session = await session_manager.get_session(session_id)
        
        assert retrieved_session is not None
        assert retrieved_session.session_id == session_id
        mock_session_components.get_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_activity_update_flow(self, mock_session_components):
        """Test session activity update flow."""
        from shared.session_manager import SessionManager
        
        session_id = str(uuid.uuid4())
        mock_session_components.update_item.return_value = {}
        
        session_manager = SessionManager('test-table')
        
        # Test activity update
        await session_manager.update_activity(session_id)
        
        mock_session_components.update_item.assert_called_once()
        call_args = mock_session_components.update_item.call_args[1]
        assert call_args['Key']['session_id'] == session_id
        assert 'last_activity' in call_args['UpdateExpression']
    
    @pytest.mark.asyncio
    async def test_session_cleanup_integration(self, mock_session_components):
        """Test session cleanup integration."""
        from shared.session_manager import SessionManager
        
        # Mock scan results with inactive sessions
        mock_session_components.scan.return_value = {
            'Items': [
                {'session_id': 'inactive-1'},
                {'session_id': 'inactive-2'}
            ]
        }
        
        # Mock batch writer
        mock_batch = Mock()
        mock_session_components.batch_writer.return_value.__enter__.return_value = mock_batch
        
        session_manager = SessionManager('test-table')
        
        # Test cleanup
        cleanup_count = await session_manager.cleanup_inactive_sessions()
        
        assert cleanup_count == 2
        assert mock_batch.delete_item.call_count == 2


class TestMCPToolIntegration:
    """Integration tests for MCP tool functionality."""
    
    @pytest.fixture
    def mock_mcp_components(self):
        """Mock MCP-related components."""
        with patch('boto3.client') as mock_client:
            mock_lambda_client = Mock()
            mock_lambda_client.invoke = Mock()
            mock_client.return_value = mock_lambda_client
            
            yield mock_lambda_client
    
    @pytest.mark.asyncio
    async def test_mcp_tool_execution_flow(self, mock_mcp_components):
        """Test MCP tool execution integration."""
        from shared.mcp_handler import MCPHandler
        
        # Mock successful tool execution
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'success': True,
            'result': {'data': 'test result'}
        }).encode()
        
        mock_mcp_components.invoke.return_value = mock_response
        
        # Mock Strand client
        with patch('shared.mcp_handler.StrandClient') as mock_strand_class:
            mock_strand_client = Mock()
            mock_strand_client.generate_response = AsyncMock(return_value={
                'content': [{'type': 'text', 'text': 'search_documents'}]
            })
            mock_strand_class.return_value = mock_strand_client
            
            mcp_handler = MCPHandler(
                mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
            )
            
            # Mock available tools
            mcp_handler._available_tools = [
                {'name': 'search_documents', 'description': 'Search documents'}
            ]
            
            # Test tool identification
            tools = await mcp_handler.identify_tools("Search for documents")
            assert tools == ['search_documents']
            
            # Test tool execution
            result = await mcp_handler.execute_tool("search_documents", {"query": "test"})
            assert result == {'data': 'test result'}
            
            # Verify Lambda was called
            mock_mcp_components.invoke.assert_called()


class TestCDKDeploymentValidation:
    """Integration tests for CDK deployment validation."""
    
    def test_cdk_app_structure(self):
        """Test CDK app structure and configuration."""
        # Check if CDK app file exists
        cdk_app_path = os.path.join(os.path.dirname(__file__), '../../cdk/app.py')
        assert os.path.exists(cdk_app_path), "CDK app.py file should exist"
        
        # Check if CDK configuration exists
        cdk_json_path = os.path.join(os.path.dirname(__file__), '../../cdk.json')
        assert os.path.exists(cdk_json_path), "cdk.json file should exist"
        
        # Validate cdk.json structure
        with open(cdk_json_path, 'r') as f:
            cdk_config = json.load(f)
            assert 'app' in cdk_config
            assert 'python' in cdk_config['app']
    
    def test_lambda_function_structure(self):
        """Test Lambda function structure."""
        lambda_dir = os.path.join(os.path.dirname(__file__), '../../lambda')
        assert os.path.exists(lambda_dir), "Lambda directory should exist"
        
        # Check required Lambda functions
        required_functions = [
            'websocket_handler',
            'session_cleanup',
            'mcp_server'
        ]
        
        for function_name in required_functions:
            function_dir = os.path.join(lambda_dir, function_name)
            assert os.path.exists(function_dir), f"{function_name} directory should exist"
            
            handler_file = os.path.join(function_dir, 'handler.py')
            assert os.path.exists(handler_file), f"{function_name}/handler.py should exist"
            
            requirements_file = os.path.join(function_dir, 'requirements.txt')
            assert os.path.exists(requirements_file), f"{function_name}/requirements.txt should exist"
    
    def test_shared_modules_structure(self):
        """Test shared modules structure."""
        shared_dir = os.path.join(os.path.dirname(__file__), '../../shared')
        assert os.path.exists(shared_dir), "Shared directory should exist"
        
        # Check required shared modules
        required_modules = [
            'session_manager.py',
            'session_models.py',
            'chatbot_engine.py',
            'rag_handler.py',
            'mcp_handler.py',
            'strand_client.py',
            'exceptions.py',
            'utils.py'
        ]
        
        for module_name in required_modules:
            module_file = os.path.join(shared_dir, module_name)
            assert os.path.exists(module_file), f"shared/{module_name} should exist"
    
    def test_requirements_consistency(self):
        """Test requirements.txt consistency across components."""
        # Check root requirements
        root_requirements = os.path.join(os.path.dirname(__file__), '../../requirements.txt')
        assert os.path.exists(root_requirements), "Root requirements.txt should exist"
        
        # Check Lambda function requirements
        lambda_functions = ['websocket_handler', 'session_cleanup', 'mcp_server']
        
        for function_name in lambda_functions:
            requirements_file = os.path.join(
                os.path.dirname(__file__), 
                f'../../lambda/{function_name}/requirements.txt'
            )
            assert os.path.exists(requirements_file), f"{function_name} requirements.txt should exist"
            
            # Verify basic dependencies are present
            with open(requirements_file, 'r') as f:
                content = f.read()
                assert 'boto3' in content, f"{function_name} should have boto3 dependency"


if __name__ == '__main__':
    pytest.main([__file__])