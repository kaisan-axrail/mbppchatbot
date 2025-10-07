"""
Integration tests for MCP (Model Context Protocol) tool functionality.

These tests verify the integration between MCP tools, the MCP server,
and the chatbot engine for end-to-end tool execution flows.
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# Import MCP components
from shared.mcp_handler import MCPHandler
from shared.exceptions import McpHandlerError, StrandClientError


class TestMCPServerIntegration:
    """Integration tests for MCP server functionality."""
    
    @pytest.fixture
    def mock_mcp_server_components(self):
        """Mock MCP server components."""
        # Load the MCP server module
        import importlib.util
        import sys
        
        mcp_server_path = os.path.join(
            os.path.dirname(__file__), 
            '../../lambda/mcp_server/mcp_server.py'
        )
        spec = importlib.util.spec_from_file_location("mcp_server", mcp_server_path)
        mcp_server = importlib.util.module_from_spec(spec)
        
        # Add shared modules to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
        
        spec.loader.exec_module(mcp_server)
        
        with patch('boto3.resource') as mock_resource, \
             patch('boto3.client') as mock_client:
            
            # Mock DynamoDB
            mock_table = Mock()
            mock_table.put_item = Mock()
            mock_table.get_item = Mock()
            mock_table.update_item = Mock()
            mock_table.delete_item = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            
            # Mock Bedrock
            mock_bedrock = Mock()
            mock_bedrock.invoke_model = Mock()
            mock_client.return_value = mock_bedrock
            
            yield {
                'mcp_server_module': mcp_server,
                'dynamodb_table': mock_table,
                'bedrock_client': mock_bedrock
            }
    
    @pytest.mark.asyncio
    async def test_mcp_server_tool_registration(self, mock_mcp_server_components):
        """Test MCP server tool registration and listing."""
        MCPChatbotServer = mock_mcp_server_components['mcp_server_module'].MCPChatbotServer
        
        # Create MCP server instance
        with patch('builtins.open', mock_open_schema()):
            mcp_server = MCPChatbotServer()
            
            # Test tool registration
            available_tools = mcp_server.get_available_tools()
            
            # Verify tools are registered
            assert len(available_tools) > 0
            
            # Check for expected tools
            tool_names = [tool['name'] for tool in available_tools]
            assert 'search_documents' in tool_names
            assert 'create_record' in tool_names
            assert 'read_record' in tool_names
            assert 'update_record' in tool_names
            assert 'delete_record' in tool_names
    
    @pytest.mark.asyncio
    async def test_rag_tool_integration(self, mock_mcp_server_components):
        """Test RAG tool integration with Bedrock and OpenSearch."""
        MCPChatbotServer = mock_mcp_server_components['mcp_server_module'].MCPChatbotServer
        
        # Mock Bedrock embedding response
        mock_mcp_server_components['bedrock_client'].invoke_model.return_value = {
            'body': Mock()
        }
        mock_mcp_server_components['bedrock_client'].invoke_model.return_value['body'].read.return_value = json.dumps({
            'embedding': [0.1, 0.2, 0.3, 0.4, 0.5] * 256  # 1280 dimensions
        }).encode()
        
        with patch('builtins.open', mock_open_schema()):
            mcp_server = MCPChatbotServer()
            
            # Test document search
            search_params = {
                'query': 'test search query',
                'limit': 5,
                'threshold': 0.7
            }
            
            # Mock OpenSearch response (simplified)
            with patch.object(mcp_server, '_search_opensearch', return_value=[
                {
                    'id': 'doc_1',
                    'content': 'Test document content',
                    'source': 'test.pdf',
                    'score': 0.85
                }
            ]):
                result = await mcp_server.search_documents(**search_params)
                
                # Verify search results
                assert len(result) == 1
                assert result[0]['id'] == 'doc_1'
                assert result[0]['score'] == 0.85
                
                # Verify Bedrock was called for embedding
                mock_mcp_server_components['bedrock_client'].invoke_model.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crud_tool_integration(self, mock_mcp_server_components):
        """Test CRUD tool integration with DynamoDB."""
        MCPChatbotServer = mock_mcp_server_components['mcp_server_module'].MCPChatbotServer
        
        with patch('builtins.open', mock_open_schema()):
            mcp_server = MCPChatbotServer()
            
            # Test create record
            create_params = {
                'table': 'sessions',
                'data': {
                    'name': 'Test Record',
                    'value': 'Test Value'
                }
            }
            
            mock_mcp_server_components['dynamodb_table'].put_item.return_value = {}
            
            result = await mcp_server.create_record(**create_params)
            
            # Verify create operation
            assert result['success'] is True
            assert 'record_id' in result
            mock_mcp_server_components['dynamodb_table'].put_item.assert_called_once()
            
            # Test read record
            record_id = result['record_id']
            mock_mcp_server_components['dynamodb_table'].get_item.return_value = {
                'Item': {
                    'id': record_id,
                    'name': 'Test Record',
                    'value': 'Test Value',
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
            }
            
            read_result = await mcp_server.read_record('sessions', record_id)
            
            # Verify read operation
            assert read_result['success'] is True
            assert read_result['data']['id'] == record_id
            mock_mcp_server_components['dynamodb_table'].get_item.assert_called_once()
            
            # Test update record
            update_params = {
                'table': 'sessions',
                'record_id': record_id,
                'data': {'value': 'Updated Value'}
            }
            
            mock_mcp_server_components['dynamodb_table'].update_item.return_value = {
                'Attributes': {
                    'id': record_id,
                    'name': 'Test Record',
                    'value': 'Updated Value',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
            }
            
            update_result = await mcp_server.update_record(**update_params)
            
            # Verify update operation
            assert update_result['success'] is True
            assert update_result['data']['value'] == 'Updated Value'
            mock_mcp_server_components['dynamodb_table'].update_item.assert_called_once()
            
            # Test delete record
            mock_mcp_server_components['dynamodb_table'].delete_item.return_value = {
                'Attributes': {
                    'id': record_id,
                    'name': 'Test Record'
                }
            }
            
            delete_result = await mcp_server.delete_record('sessions', record_id)
            
            # Verify delete operation
            assert delete_result['success'] is True
            mock_mcp_server_components['dynamodb_table'].delete_item.assert_called_once()


class TestMCPHandlerIntegration:
    """Integration tests for MCP handler functionality."""
    
    @pytest.fixture
    def mock_mcp_handler_components(self):
        """Mock MCP handler components."""
        with patch('boto3.client') as mock_client, \
             patch('shared.mcp_handler.StrandClient') as mock_strand_class:
            
            # Mock Lambda client
            mock_lambda_client = Mock()
            mock_lambda_client.invoke = Mock()
            mock_client.return_value = mock_lambda_client
            
            # Mock Strand client
            mock_strand_client = Mock()
            mock_strand_client.generate_response = AsyncMock()
            mock_strand_client.validate_configuration = Mock(return_value={
                'api_key_configured': True
            })
            mock_strand_class.return_value = mock_strand_client
            
            yield {
                'lambda_client': mock_lambda_client,
                'strand_client': mock_strand_client
            }
    
    @pytest.mark.asyncio
    async def test_end_to_end_tool_execution_flow(self, mock_mcp_handler_components):
        """Test complete end-to-end tool execution flow."""
        # Create MCP handler
        mcp_handler = MCPHandler(
            mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
        )
        
        # Mock available tools
        tools_response = {
            'Payload': Mock()
        }
        tools_response['Payload'].read.return_value = json.dumps({
            'tools': [
                {
                    'name': 'search_documents',
                    'description': 'Search documents using vector similarity',
                    'parameters': {
                        'query': {'type': 'string', 'required': True},
                        'limit': {'type': 'integer', 'default': 5}
                    }
                },
                {
                    'name': 'create_record',
                    'description': 'Create a new record',
                    'parameters': {
                        'table': {'type': 'string', 'required': True},
                        'data': {'type': 'object', 'required': True}
                    }
                }
            ]
        }).encode()
        
        mock_mcp_handler_components['lambda_client'].invoke.return_value = tools_response
        
        # Step 1: Tool identification
        mock_mcp_handler_components['strand_client'].generate_response.return_value = {
            'content': [{'type': 'text', 'text': 'search_documents'}]
        }
        
        identified_tools = await mcp_handler.identify_tools("Find documents about machine learning")
        
        assert identified_tools == ['search_documents']
        mock_mcp_handler_components['strand_client'].generate_response.assert_called_once()
        
        # Step 2: Tool execution
        tool_response = {
            'Payload': Mock()
        }
        tool_response['Payload'].read.return_value = json.dumps({
            'success': True,
            'result': [
                {
                    'id': 'doc_1',
                    'content': 'Machine learning is a subset of AI...',
                    'source': 'ml_guide.pdf',
                    'score': 0.92
                },
                {
                    'id': 'doc_2',
                    'content': 'Deep learning uses neural networks...',
                    'source': 'dl_basics.pdf',
                    'score': 0.87
                }
            ]
        }).encode()
        
        mock_mcp_handler_components['lambda_client'].invoke.return_value = tool_response
        
        tool_result = await mcp_handler.execute_tool('search_documents', {
            'query': 'machine learning',
            'limit': 5
        })
        
        assert len(tool_result) == 2
        assert tool_result[0]['score'] == 0.92
        
        # Step 3: Result processing
        mock_mcp_handler_components['strand_client'].generate_response.return_value = {
            'content': [{'type': 'text', 'text': 'Based on the search results, machine learning is a powerful subset of AI that enables computers to learn from data. The documents show that it includes techniques like deep learning with neural networks.'}]
        }
        
        tool_results = [
            {
                'tool': 'search_documents',
                'success': True,
                'result': tool_result
            }
        ]
        
        final_response = await mcp_handler.process_tool_results(
            tool_results, 
            "Find documents about machine learning"
        )
        
        assert 'machine learning' in final_response.lower()
        assert 'neural networks' in final_response.lower()
        
        # Verify all Lambda calls were made
        assert mock_mcp_handler_components['lambda_client'].invoke.call_count == 2  # tools list + execution
    
    @pytest.mark.asyncio
    async def test_multiple_tool_execution_flow(self, mock_mcp_handler_components):
        """Test execution flow with multiple tools."""
        mcp_handler = MCPHandler(
            mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
        )
        
        # Mock available tools
        mcp_handler._available_tools = [
            {'name': 'search_documents', 'description': 'Search documents'},
            {'name': 'create_record', 'description': 'Create record'}
        ]
        
        # Mock tool identification for multiple tools
        mock_mcp_handler_components['strand_client'].generate_response.return_value = {
            'content': [{'type': 'text', 'text': 'search_documents,create_record'}]
        }
        
        identified_tools = await mcp_handler.identify_tools("Search for info and save it")
        
        assert set(identified_tools) == {'search_documents', 'create_record'}
        
        # Mock execution for both tools
        search_response = {
            'Payload': Mock()
        }
        search_response['Payload'].read.return_value = json.dumps({
            'success': True,
            'result': [{'id': 'doc_1', 'content': 'Found content', 'score': 0.9}]
        }).encode()
        
        create_response = {
            'Payload': Mock()
        }
        create_response['Payload'].read.return_value = json.dumps({
            'success': True,
            'result': {'record_id': 'rec_123', 'message': 'Record created'}
        }).encode()
        
        # Set up side effects for multiple calls
        mock_mcp_handler_components['lambda_client'].invoke.side_effect = [
            search_response,
            create_response
        ]
        
        # Execute both tools
        search_result = await mcp_handler.execute_tool('search_documents', {'query': 'test'})
        create_result = await mcp_handler.execute_tool('create_record', {
            'table': 'results',
            'data': {'content': 'Found content'}
        })
        
        assert search_result[0]['score'] == 0.9
        assert create_result['record_id'] == 'rec_123'
        
        # Verify both tools were executed
        assert mock_mcp_handler_components['lambda_client'].invoke.call_count == 2
    
    @pytest.mark.asyncio
    async def test_tool_error_handling_integration(self, mock_mcp_handler_components):
        """Test tool error handling integration."""
        mcp_handler = MCPHandler(
            mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
        )
        
        # Mock tool execution error
        error_response = {
            'Payload': Mock()
        }
        error_response['Payload'].read.return_value = json.dumps({
            'success': False,
            'error': {
                'message': 'Tool execution failed',
                'code': 'EXECUTION_ERROR'
            }
        }).encode()
        
        mock_mcp_handler_components['lambda_client'].invoke.return_value = error_response
        
        # Test error handling
        with pytest.raises(Exception):  # Should raise an exception
            await mcp_handler.execute_tool('search_documents', {'query': 'test'})
        
        # Test error result processing
        error_results = [
            {
                'tool': 'search_documents',
                'success': False,
                'error': {'message': 'Search failed'}
            }
        ]
        
        mock_mcp_handler_components['strand_client'].generate_response.return_value = {
            'content': [{'type': 'text', 'text': 'I encountered an error while searching. Please try again.'}]
        }
        
        error_response_text = await mcp_handler.process_tool_results(
            error_results,
            "Search for documents"
        )
        
        assert 'error' in error_response_text.lower()
        assert 'try again' in error_response_text.lower()


class TestChatbotMCPIntegration:
    """Integration tests for chatbot and MCP integration."""
    
    @pytest.fixture
    def mock_chatbot_mcp_components(self):
        """Mock chatbot and MCP components."""
        with patch('shared.chatbot_engine.boto3.resource'), \
             patch('shared.chatbot_engine.SessionManager'), \
             patch('shared.strand_client.create_strand_client') as mock_create_strand:
            
            # Mock Strand client
            mock_strand_client = Mock()
            mock_strand_client.generate_response = AsyncMock()
            mock_create_strand.return_value = mock_strand_client
            
            # Mock MCP handler
            with patch('shared.mcp_handler.MCPHandler') as mock_mcp_class:
                mock_mcp_handler = Mock()
                mock_mcp_handler.identify_tools = AsyncMock()
                mock_mcp_handler.execute_tool = AsyncMock()
                mock_mcp_handler.process_tool_results = AsyncMock()
                mock_mcp_class.return_value = mock_mcp_handler
                
                yield {
                    'strand_client': mock_strand_client,
                    'mcp_handler': mock_mcp_handler
                }
    
    @pytest.mark.asyncio
    async def test_chatbot_mcp_query_integration(self, mock_chatbot_mcp_components):
        """Test chatbot integration with MCP tools."""
        from shared.chatbot_engine import ChatbotEngine
        from shared.strand_utils import QueryType
        
        # Create chatbot engine
        chatbot_engine = ChatbotEngine()
        
        # Mock query type determination
        chatbot_engine.determine_query_type = AsyncMock(return_value=QueryType.MCP_TOOL)
        
        # Mock MCP tool operations
        mock_chatbot_mcp_components['mcp_handler'].identify_tools.return_value = ['search_documents']
        mock_chatbot_mcp_components['mcp_handler'].execute_tool.return_value = [
            {
                'id': 'doc_1',
                'content': 'Relevant document content',
                'source': 'guide.pdf',
                'score': 0.9
            }
        ]
        mock_chatbot_mcp_components['mcp_handler'].process_tool_results.return_value = (
            "Based on the search results, I found relevant information in guide.pdf. "
            "The document contains detailed information about your query."
        )
        
        # Mock session
        from shared.session_models import Session, SessionStatus
        mock_session = Session(
            session_id="test-session",
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            status=SessionStatus.ACTIVE
        )
        
        chatbot_engine.session_manager.get_session = AsyncMock(return_value=mock_session)
        chatbot_engine.session_manager.update_activity = AsyncMock()
        chatbot_engine._log_conversation = AsyncMock()
        
        # Process MCP tool query
        response = await chatbot_engine.process_message(
            "test-session",
            "Search for information about machine learning"
        )
        
        # Verify response
        assert response.query_type == QueryType.MCP_TOOL
        assert response.tools_used == ['search_documents']
        assert 'guide.pdf' in response.content
        assert response.response_time is not None
        
        # Verify MCP operations were called
        mock_chatbot_mcp_components['mcp_handler'].identify_tools.assert_called_once()
        mock_chatbot_mcp_components['mcp_handler'].execute_tool.assert_called_once()
        mock_chatbot_mcp_components['mcp_handler'].process_tool_results.assert_called_once()


def mock_open_schema():
    """Mock open function for schema file."""
    schema_content = """
openapi: 3.0.0
info:
  title: Chatbot MCP Tools
  version: 1.0.0
paths:
  /search_documents:
    post:
      summary: Search documents
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                query:
                  type: string
                limit:
                  type: integer
                  default: 5
      responses:
        '200':
          description: Search results
  /create_record:
    post:
      summary: Create record
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                table:
                  type: string
                data:
                  type: object
      responses:
        '200':
          description: Record created
"""
    
    from unittest.mock import mock_open
    return mock_open(read_data=schema_content)


if __name__ == '__main__':
    pytest.main([__file__])