"""
Unit tests for MCP handler functionality.
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from shared.mcp_handler import MCPHandler, create_mcp_handler
from shared.exceptions import McpHandlerError
from shared.strand_client import StrandClientError


class TestMCPHandler:
    """Test cases for MCPHandler class."""
    
    @pytest.fixture
    def mock_lambda_client(self):
        """Mock AWS Lambda client."""
        mock_client = Mock()
        return mock_client
    
    @pytest.fixture
    def mock_strand_client(self):
        """Mock Strand SDK client."""
        mock_client = Mock()
        mock_client.generate_response = AsyncMock()
        mock_client.validate_configuration = Mock(return_value={
            "api_key_configured": True,
            "region": "us-east-1",
            "model_name": "anthropic.claude-3-5-sonnet-20241022-v2:0"
        })
        return mock_client
    
    @pytest.fixture
    def sample_tools(self):
        """Sample available tools for testing."""
        return [
            {
                "name": "search_documents",
                "description": "Search documents using vector similarity",
                "parameters": {
                    "query": {"type": "string", "required": True},
                    "limit": {"type": "integer", "default": 5}
                }
            },
            {
                "name": "create_record",
                "description": "Create a new record in DynamoDB",
                "parameters": {
                    "table": {"type": "string", "required": True},
                    "data": {"type": "object", "required": True}
                }
            }
        ]
    
    @pytest.fixture
    def mcp_handler(self, mock_lambda_client, mock_strand_client):
        """Create MCPHandler instance with mocked dependencies."""
        with patch('shared.mcp_handler.boto3.client', return_value=mock_lambda_client), \
             patch('shared.mcp_handler.StrandClient', return_value=mock_strand_client):
            handler = MCPHandler(
                mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server",
                region="us-east-1"
            )
            handler.lambda_client = mock_lambda_client
            handler.strand_client = mock_strand_client
            return handler
    
    def test_initialization_success(self, mock_lambda_client, mock_strand_client):
        """Test successful MCPHandler initialization."""
        with patch('shared.mcp_handler.boto3.client', return_value=mock_lambda_client), \
             patch('shared.mcp_handler.StrandClient', return_value=mock_strand_client):
            handler = MCPHandler(
                mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server",
                region="us-east-1"
            )
            
            assert handler.mcp_server_lambda_arn == "arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
            assert handler.region == "us-east-1"
            assert handler.lambda_client == mock_lambda_client
            assert handler.strand_client == mock_strand_client
    
    def test_initialization_missing_lambda_arn(self):
        """Test MCPHandler initialization with missing Lambda ARN."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(McpHandlerError) as exc_info:
                MCPHandler()
            
            assert exc_info.value.code == "CONFIGURATION_ERROR"
            assert "MCP server Lambda ARN not configured" in str(exc_info.value)
    
    def test_initialization_strand_client_error(self, mock_lambda_client):
        """Test MCPHandler initialization with Strand client error."""
        with patch('shared.mcp_handler.boto3.client', return_value=mock_lambda_client), \
             patch('shared.mcp_handler.StrandClient', side_effect=StrandClientError("Strand error")):
            with pytest.raises(McpHandlerError) as exc_info:
                MCPHandler(
                    mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
                )
            
            assert exc_info.value.code == "STRAND_INITIALIZATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_identify_tools_success(self, mcp_handler, sample_tools):
        """Test successful tool identification."""
        # Mock get available tools
        mcp_handler._available_tools = sample_tools
        
        # Mock Strand client response
        mcp_handler.strand_client.generate_response.return_value = {
            "content": [{"type": "text", "text": "search_documents"}]
        }
        
        result = await mcp_handler.identify_tools("Find documents about AWS Lambda")
        
        assert result == ["search_documents"]
        mcp_handler.strand_client.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_identify_tools_multiple_tools(self, mcp_handler, sample_tools):
        """Test identification of multiple tools."""
        mcp_handler._available_tools = sample_tools
        
        mcp_handler.strand_client.generate_response.return_value = {
            "content": [{"type": "text", "text": "search_documents,create_record"}]
        }
        
        result = await mcp_handler.identify_tools("Search for info and save it")
        
        assert set(result) == {"search_documents", "create_record"}
    
    @pytest.mark.asyncio
    async def test_identify_tools_none_needed(self, mcp_handler, sample_tools):
        """Test tool identification when no tools are needed."""
        mcp_handler._available_tools = sample_tools
        
        mcp_handler.strand_client.generate_response.return_value = {
            "content": [{"type": "text", "text": "NONE"}]
        }
        
        result = await mcp_handler.identify_tools("What's the weather like?")
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_identify_tools_invalid_tools_filtered(self, mcp_handler, sample_tools):
        """Test that invalid tool names are filtered out."""
        mcp_handler._available_tools = sample_tools
        
        mcp_handler.strand_client.generate_response.return_value = {
            "content": [{"type": "text", "text": "search_documents,invalid_tool,create_record"}]
        }
        
        result = await mcp_handler.identify_tools("Test query")
        
        assert set(result) == {"search_documents", "create_record"}
    
    @pytest.mark.asyncio
    async def test_identify_tools_strand_error(self, mcp_handler, sample_tools):
        """Test tool identification with Strand client error."""
        mcp_handler._available_tools = sample_tools
        
        mcp_handler.strand_client.generate_response.side_effect = StrandClientError("API error")
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler.identify_tools("Test query")
        
        assert exc_info.value.code == "TOOL_IDENTIFICATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(self, mcp_handler):
        """Test successful tool execution."""
        # Mock Lambda response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'success': True,
            'result': {'data': 'test result'}
        }).encode()
        
        mcp_handler.lambda_client.invoke.return_value = mock_response
        
        result = await mcp_handler.execute_tool("search_documents", {"query": "test"})
        
        assert result == {'data': 'test result'}
        mcp_handler.lambda_client.invoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_tool_lambda_error(self, mcp_handler):
        """Test tool execution with Lambda error."""
        # Mock Lambda error response
        mock_response = {
            'FunctionError': 'Unhandled',
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'errorMessage': 'Lambda execution failed'
        }).encode()
        
        mcp_handler.lambda_client.invoke.return_value = mock_response
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler.execute_tool("search_documents", {"query": "test"})
        
        assert exc_info.value.code == "LAMBDA_EXECUTION_ERROR"
    
    @pytest.mark.asyncio
    async def test_execute_tool_mcp_error(self, mcp_handler):
        """Test tool execution with MCP tool error."""
        # Mock MCP tool error response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'success': False,
            'error': {
                'message': 'Tool execution failed',
                'code': 'TOOL_ERROR'
            }
        }).encode()
        
        mcp_handler.lambda_client.invoke.return_value = mock_response
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler.execute_tool("search_documents", {"query": "test"})
        
        assert exc_info.value.code == "MCP_TOOL_EXECUTION_ERROR"
    
    @pytest.mark.asyncio
    async def test_execute_tool_invalid_json_response(self, mcp_handler):
        """Test tool execution with invalid JSON response."""
        # Mock invalid JSON response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = b'invalid json'
        
        mcp_handler.lambda_client.invoke.return_value = mock_response
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler.execute_tool("search_documents", {"query": "test"})
        
        assert exc_info.value.code == "RESPONSE_PARSING_ERROR"
    
    @pytest.mark.asyncio
    async def test_process_tool_results_success(self, mcp_handler):
        """Test successful tool result processing."""
        results = [
            {
                'tool': 'search_documents',
                'success': True,
                'result': {'data': [{'content': 'Document content', 'score': 0.9}]}
            }
        ]
        
        mcp_handler.strand_client.generate_response.return_value = {
            "content": [{"type": "text", "text": "Based on the search results, here is the answer..."}]
        }
        
        response = await mcp_handler.process_tool_results(results, "Find information about AWS")
        
        assert "Based on the search results" in response
        mcp_handler.strand_client.generate_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_tool_results_with_errors(self, mcp_handler):
        """Test tool result processing with tool errors."""
        results = [
            {
                'tool': 'search_documents',
                'success': False,
                'error': {'message': 'Search failed'}
            }
        ]
        
        mcp_handler.strand_client.generate_response.return_value = {
            "content": [{"type": "text", "text": "I encountered an error while searching..."}]
        }
        
        response = await mcp_handler.process_tool_results(results, "Find information")
        
        assert "error" in response.lower()
    
    @pytest.mark.asyncio
    async def test_process_tool_results_empty_response(self, mcp_handler):
        """Test tool result processing with empty response."""
        results = [{'tool': 'test', 'success': True, 'result': {}}]
        
        mcp_handler.strand_client.generate_response.return_value = {
            "content": []
        }
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler.process_tool_results(results, "Test query")
        
        assert exc_info.value.code == "EMPTY_RESPONSE_ERROR"
    
    @pytest.mark.asyncio
    async def test_process_tool_results_strand_error(self, mcp_handler):
        """Test tool result processing with Strand client error."""
        results = [{'tool': 'test', 'success': True, 'result': {}}]
        
        mcp_handler.strand_client.generate_response.side_effect = StrandClientError("API error")
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler.process_tool_results(results, "Test query")
        
        assert exc_info.value.code == "RESULT_PROCESSING_ERROR"
    
    @pytest.mark.asyncio
    async def test_get_available_tools_success(self, mcp_handler, sample_tools):
        """Test successful retrieval of available tools."""
        # Mock Lambda response
        mock_response = {
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'tools': sample_tools
        }).encode()
        
        mcp_handler.lambda_client.invoke.return_value = mock_response
        
        tools = await mcp_handler._get_available_tools()
        
        assert tools == sample_tools
        mcp_handler.lambda_client.invoke.assert_called_once_with(
            FunctionName=mcp_handler.mcp_server_lambda_arn,
            InvocationType='RequestResponse',
            Payload=json.dumps({"action": "list_tools"})
        )
    
    @pytest.mark.asyncio
    async def test_get_available_tools_lambda_error(self, mcp_handler):
        """Test get available tools with Lambda error."""
        # Mock Lambda error response
        mock_response = {
            'FunctionError': 'Unhandled',
            'Payload': Mock()
        }
        mock_response['Payload'].read.return_value = json.dumps({
            'errorMessage': 'Lambda execution failed'
        }).encode()
        
        mcp_handler.lambda_client.invoke.return_value = mock_response
        
        with pytest.raises(McpHandlerError) as exc_info:
            await mcp_handler._get_available_tools()
        
        assert exc_info.value.code == "TOOL_LIST_ERROR"
    
    def test_create_tool_identification_prompt(self, mcp_handler, sample_tools):
        """Test creation of tool identification prompt."""
        prompt = mcp_handler._create_tool_identification_prompt(sample_tools)
        
        assert "search_documents" in prompt
        assert "create_record" in prompt
        assert "Search documents using vector similarity" in prompt
        assert "Create a new record in DynamoDB" in prompt
        assert "NONE" in prompt
    
    def test_create_result_processing_prompt(self, mcp_handler):
        """Test creation of result processing prompt."""
        prompt = mcp_handler._create_result_processing_prompt()
        
        assert "tool execution results" in prompt.lower()
        assert "synthesize" in prompt.lower()
        assert "cite sources" in prompt.lower()
    
    def test_parse_tool_names_from_response_single_tool(self, mcp_handler, sample_tools):
        """Test parsing single tool name from response."""
        mcp_handler._available_tools = sample_tools
        
        result = mcp_handler._parse_tool_names_from_response("search_documents")
        assert result == ["search_documents"]
    
    def test_parse_tool_names_from_response_multiple_tools(self, mcp_handler, sample_tools):
        """Test parsing multiple tool names from response."""
        mcp_handler._available_tools = sample_tools
        
        result = mcp_handler._parse_tool_names_from_response("search_documents, create_record")
        assert set(result) == {"search_documents", "create_record"}
    
    def test_parse_tool_names_from_response_none(self, mcp_handler, sample_tools):
        """Test parsing NONE response."""
        mcp_handler._available_tools = sample_tools
        
        result = mcp_handler._parse_tool_names_from_response("NONE")
        assert result == []
    
    def test_parse_tool_names_from_response_invalid_tools(self, mcp_handler, sample_tools):
        """Test parsing response with invalid tool names."""
        mcp_handler._available_tools = sample_tools
        
        result = mcp_handler._parse_tool_names_from_response("search_documents, invalid_tool")
        assert result == ["search_documents"]
    
    def test_format_tool_results_for_claude_success(self, mcp_handler):
        """Test formatting successful tool results."""
        results = [
            {
                'tool': 'search_documents',
                'success': True,
                'result': {'data': 'test result'}
            }
        ]
        
        formatted = mcp_handler._format_tool_results_for_claude(results)
        
        assert "Tool 1: search_documents" in formatted
        assert "Status: Success" in formatted
        assert "test result" in formatted
    
    def test_format_tool_results_for_claude_error(self, mcp_handler):
        """Test formatting tool results with errors."""
        results = [
            {
                'tool': 'search_documents',
                'success': False,
                'error': {'message': 'Search failed'}
            }
        ]
        
        formatted = mcp_handler._format_tool_results_for_claude(results)
        
        assert "Tool 1: search_documents" in formatted
        assert "Status: Failed" in formatted
        assert "Search failed" in formatted
    
    def test_validate_configuration(self, mcp_handler):
        """Test configuration validation."""
        config = mcp_handler.validate_configuration()
        
        assert "mcp_server_lambda_arn" in config
        assert "region" in config
        assert "strand_client_configured" in config
        assert "lambda_client_configured" in config
        assert "strand_configuration" in config
        
        assert config["strand_client_configured"] is True
        assert config["lambda_client_configured"] is True


class TestMCPHandlerFactory:
    """Test cases for MCP handler factory function."""
    
    @patch('shared.mcp_handler.MCPHandler')
    def test_create_mcp_handler(self, mock_mcp_handler_class):
        """Test MCP handler factory function."""
        mock_instance = Mock()
        mock_mcp_handler_class.return_value = mock_instance
        
        result = create_mcp_handler(
            mcp_server_lambda_arn="test-arn",
            region="us-west-2"
        )
        
        mock_mcp_handler_class.assert_called_once_with(
            mcp_server_lambda_arn="test-arn",
            region="us-west-2"
        )
        assert result == mock_instance


class TestMCPHandlerIntegration:
    """Integration test cases for MCP handler."""
    
    @pytest.mark.asyncio
    async def test_full_tool_execution_flow(self):
        """Test complete tool execution flow from identification to result processing."""
        # This would be an integration test that tests the full flow
        # For now, we'll create a simplified version
        
        with patch('shared.mcp_handler.boto3.client') as mock_boto_client, \
             patch('shared.mcp_handler.StrandClient') as mock_strand_class:
            
            # Setup mocks
            mock_lambda_client = Mock()
            mock_strand_client = Mock()
            mock_strand_client.generate_response = AsyncMock()
            mock_strand_client.validate_configuration = Mock(return_value={})
            
            mock_boto_client.return_value = mock_lambda_client
            mock_strand_class.return_value = mock_strand_client
            
            # Create handler
            handler = MCPHandler(
                mcp_server_lambda_arn="arn:aws:lambda:us-east-1:123456789012:function:mcp-server"
            )
            
            # Mock tool identification
            mock_strand_client.generate_response.return_value = {
                "content": [{"type": "text", "text": "search_documents"}]
            }
            
            # Mock get available tools
            mock_response = {
                'Payload': Mock()
            }
            mock_response['Payload'].read.return_value = json.dumps({
                'tools': [
                    {
                        "name": "search_documents",
                        "description": "Search documents",
                        "parameters": {}
                    }
                ]
            }).encode()
            mock_lambda_client.invoke.return_value = mock_response
            
            # Test tool identification
            tools = await handler.identify_tools("Find documents about AWS")
            assert tools == ["search_documents"]
            
            # Mock tool execution
            mock_response['Payload'].read.return_value = json.dumps({
                'success': True,
                'result': {'data': 'search results'}
            }).encode()
            
            # Test tool execution
            result = await handler.execute_tool("search_documents", {"query": "AWS"})
            assert result == {'data': 'search results'}
            
            # Mock result processing
            mock_strand_client.generate_response.return_value = {
                "content": [{"type": "text", "text": "Here are the search results..."}]
            }
            
            # Test result processing
            response = await handler.process_tool_results(
                [{'tool': 'search_documents', 'success': True, 'result': result}],
                "Find documents about AWS"
            )
            assert "search results" in response.lower()


if __name__ == "__main__":
    pytest.main([__file__])