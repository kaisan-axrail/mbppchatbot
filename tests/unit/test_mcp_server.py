"""
Unit tests for MCP server foundation.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import yaml

# Add lambda directory to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda/mcp_server'))

from mcp_server import MCPChatbotServer, MCPServerError, SchemaValidationError


class TestMCPChatbotServer(unittest.TestCase):
    """Test cases for MCPChatbotServer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_schema = {
            'openapi': '3.0.0',
            'info': {
                'title': 'Test MCP Tools',
                'version': '1.0.0',
                'description': 'Test schema'
            },
            'paths': {
                '/test_tool': {
                    'post': {
                        'summary': 'Test tool',
                        'operationId': 'test_tool',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'required': ['query'],
                                        'properties': {
                                            'query': {
                                                'type': 'string',
                                                'minLength': 1
                                            },
                                            'limit': {
                                                'type': 'integer',
                                                'default': 5,
                                                'minimum': 1
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '200': {
                                'description': 'Success',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'array',
                                            'items': {
                                                'type': 'object',
                                                'required': ['id', 'content'],
                                                'properties': {
                                                    'id': {'type': 'string'},
                                                    'content': {'type': 'string'}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        # Create temporary schema file
        self.temp_schema_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        yaml.dump(self.test_schema, self.temp_schema_file)
        self.temp_schema_file.close()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_schema_file.name):
            os.unlink(self.temp_schema_file.name)
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_init_success(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test successful MCP server initialization."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        self.assertIsNotNone(server.available_tools)
        self.assertIsNotNone(server.schema)
        self.assertEqual(server.schema['openapi'], '3.0.0')
        self.assertIsNotNone(server.logger)
        self.assertIsNotNone(server.dynamodb)
        self.assertIsNotNone(server.bedrock)
    
    def test_init_missing_schema_file(self):
        """Test initialization with missing schema file."""
        with self.assertRaises(MCPServerError) as context:
            MCPChatbotServer(schema_path='/nonexistent/schema.yaml')
        
        self.assertIn('Schema file not found', str(context.exception))
    
    def test_init_invalid_schema_format(self):
        """Test initialization with invalid schema format."""
        # Create invalid schema file
        invalid_schema_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        yaml.dump({'invalid': 'schema'}, invalid_schema_file)
        invalid_schema_file.close()
        
        try:
            with self.assertRaises(MCPServerError) as context:
                MCPChatbotServer(schema_path=invalid_schema_file.name)
            
            self.assertIn('Invalid OpenAPI schema format', str(context.exception))
        finally:
            os.unlink(invalid_schema_file.name)
    
    def test_load_openapi_schema_success(self):
        """Test successful OpenAPI schema loading."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        schema = server._load_openapi_schema()
        
        self.assertEqual(schema['openapi'], '3.0.0')
        self.assertEqual(schema['info']['title'], 'Test MCP Tools')
        self.assertIn('/test_tool', schema['paths'])
    
    def test_get_schema_by_path_success(self):
        """Test successful schema path retrieval."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        path = "/paths/test_tool/post/requestBody/content/application/json/schema"
        schema = server._get_schema_by_path(path)
        
        self.assertEqual(schema['type'], 'object')
        self.assertIn('query', schema['required'])
        self.assertIn('query', schema['properties'])
    
    def test_get_schema_by_path_not_found(self):
        """Test schema path retrieval with invalid path."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        with self.assertRaises(SchemaValidationError) as context:
            server._get_schema_by_path("/invalid/path")
        
        self.assertIn('Schema path not found', str(context.exception))
    
    def test_validate_input_success(self):
        """Test successful input validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        valid_data = {'query': 'test query', 'limit': 10}
        result = server.validate_input('test_tool', valid_data)
        
        self.assertTrue(result)
    
    def test_validate_input_missing_required_field(self):
        """Test input validation with missing required field."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        invalid_data = {'limit': 10}  # Missing required 'query' field
        
        with self.assertRaises(SchemaValidationError) as context:
            server.validate_input('test_tool', invalid_data)
        
        self.assertIn('Input validation failed', str(context.exception))
    
    def test_validate_input_invalid_type(self):
        """Test input validation with invalid field type."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        invalid_data = {'query': 123, 'limit': 10}  # query should be string
        
        with self.assertRaises(SchemaValidationError) as context:
            server.validate_input('test_tool', invalid_data)
        
        self.assertIn('Input validation failed', str(context.exception))
    
    def test_validate_output_success(self):
        """Test successful output validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        valid_output = [
            {'id': 'test1', 'content': 'Test content 1'},
            {'id': 'test2', 'content': 'Test content 2'}
        ]
        
        result = server.validate_output('test_tool', valid_output)
        self.assertTrue(result)
    
    def test_validate_output_invalid_structure(self):
        """Test output validation with invalid structure."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        invalid_output = [
            {'id': 'test1'},  # Missing required 'content' field
            {'content': 'Test content 2'}  # Missing required 'id' field
        ]
        
        with self.assertRaises(SchemaValidationError) as context:
            server.validate_output('test_tool', invalid_output)
        
        self.assertIn('Output validation failed', str(context.exception))
    
    def test_handle_error_schema_validation_error(self):
        """Test error handling for schema validation errors."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        error = SchemaValidationError("Test validation error")
        result = server.handle_error(error, "test_tool")
        
        self.assertEqual(result['error'], 'SCHEMA_VALIDATION_ERROR')
        self.assertEqual(result['message'], 'Test validation error')
        self.assertEqual(result['details']['tool'], 'test_tool')
    
    def test_handle_error_mcp_server_error(self):
        """Test error handling for MCP server errors."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        error = MCPServerError("Test MCP error", "TEST_ERROR")
        result = server.handle_error(error, "test_tool")
        
        self.assertEqual(result['error'], 'TEST_ERROR')
        self.assertEqual(result['message'], 'Test MCP error')
        self.assertEqual(result['details']['tool'], 'test_tool')
    
    def test_handle_error_generic_exception(self):
        """Test error handling for generic exceptions."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        error = ValueError("Test generic error")
        result = server.handle_error(error, "test_tool")
        
        self.assertEqual(result['error'], 'INTERNAL_ERROR')
        self.assertEqual(result['message'], 'An unexpected error occurred')
        self.assertEqual(result['details']['tool'], 'test_tool')
    
    def test_get_tool_info(self):
        """Test getting tool information from schema."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        info = server.get_tool_info()
        
        self.assertIn('server_info', info)
        self.assertIn('tools', info)
        self.assertEqual(info['server_info']['title'], 'Test MCP Tools')
        self.assertIn('test_tool', info['tools'])
        self.assertEqual(info['tools']['test_tool']['summary'], 'Test tool')


if __name__ == '__main__':
    unittest.main()