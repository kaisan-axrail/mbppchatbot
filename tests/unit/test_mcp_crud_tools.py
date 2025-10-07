"""
Unit tests for MCP CRUD tools.
"""

import asyncio
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


class TestMCPCRUDTools(unittest.TestCase):
    """Test cases for MCP CRUD tools."""
    
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
                '/create_record': {
                    'post': {
                        'summary': 'Create a new record in DynamoDB',
                        'operationId': 'create_record',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'required': ['table', 'data'],
                                        'properties': {
                                            'table': {
                                                'type': 'string',
                                                'enum': ['sessions', 'conversations', 'analytics']
                                            },
                                            'data': {
                                                'type': 'object',
                                                'additionalProperties': True
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '200': {
                                'description': 'Record created successfully',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'required': ['success', 'record_id'],
                                            'properties': {
                                                'success': {'type': 'boolean'},
                                                'record_id': {'type': 'string'},
                                                'data': {
                                                    'type': 'object',
                                                    'additionalProperties': True
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                '/read_record': {
                    'post': {
                        'summary': 'Read a record from DynamoDB',
                        'operationId': 'read_record',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'required': ['table', 'record_id'],
                                        'properties': {
                                            'table': {
                                                'type': 'string',
                                                'enum': ['sessions', 'conversations', 'analytics']
                                            },
                                            'record_id': {
                                                'type': 'string',
                                                'minLength': 1
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '200': {
                                'description': 'Record retrieved successfully',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'required': ['success', 'data'],
                                            'properties': {
                                                'success': {'type': 'boolean'},
                                                'data': {
                                                    'type': 'object',
                                                    'additionalProperties': True
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                '/update_record': {
                    'post': {
                        'summary': 'Update a record in DynamoDB',
                        'operationId': 'update_record',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'required': ['table', 'record_id', 'data'],
                                        'properties': {
                                            'table': {
                                                'type': 'string',
                                                'enum': ['sessions', 'conversations', 'analytics']
                                            },
                                            'record_id': {
                                                'type': 'string',
                                                'minLength': 1
                                            },
                                            'data': {
                                                'type': 'object',
                                                'additionalProperties': True
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '200': {
                                'description': 'Record updated successfully',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'required': ['success', 'data'],
                                            'properties': {
                                                'success': {'type': 'boolean'},
                                                'data': {
                                                    'type': 'object',
                                                    'additionalProperties': True
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                '/delete_record': {
                    'post': {
                        'summary': 'Delete a record from DynamoDB',
                        'operationId': 'delete_record',
                        'requestBody': {
                            'required': True,
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'type': 'object',
                                        'required': ['table', 'record_id'],
                                        'properties': {
                                            'table': {
                                                'type': 'string',
                                                'enum': ['sessions', 'conversations', 'analytics']
                                            },
                                            'record_id': {
                                                'type': 'string',
                                                'minLength': 1
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '200': {
                                'description': 'Record deleted successfully',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'required': ['success'],
                                            'properties': {
                                                'success': {'type': 'boolean'},
                                                'message': {'type': 'string'}
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
    def test_create_record_validation(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test create_record input validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test with valid input
        valid_input = {
            'table': 'sessions',
            'data': {'name': 'test session', 'status': 'active'}
        }
        
        result = server.validate_input('create_record', valid_input)
        self.assertTrue(result)
        
        # Test with missing required field
        invalid_input = {
            'table': 'sessions'
            # Missing 'data' field
        }
        
        with self.assertRaises(SchemaValidationError):
            server.validate_input('create_record', invalid_input)
        
        # Test with invalid table name
        invalid_table = {
            'table': 'invalid_table',
            'data': {'name': 'test'}
        }
        
        with self.assertRaises(SchemaValidationError):
            server.validate_input('create_record', invalid_table)
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_read_record_validation(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test read_record input validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test with valid input
        valid_input = {
            'table': 'conversations',
            'record_id': 'test-record-123'
        }
        
        result = server.validate_input('read_record', valid_input)
        self.assertTrue(result)
        
        # Test with missing required field
        invalid_input = {
            'table': 'conversations'
            # Missing 'record_id' field
        }
        
        with self.assertRaises(SchemaValidationError):
            server.validate_input('read_record', invalid_input)
        
        # Test with empty record_id
        empty_id = {
            'table': 'conversations',
            'record_id': ''
        }
        
        with self.assertRaises(SchemaValidationError):
            server.validate_input('read_record', empty_id)
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_update_record_validation(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test update_record input validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test with valid input
        valid_input = {
            'table': 'analytics',
            'record_id': 'test-record-123',
            'data': {'status': 'updated', 'count': 5}
        }
        
        result = server.validate_input('update_record', valid_input)
        self.assertTrue(result)
        
        # Test with missing required field
        invalid_input = {
            'table': 'analytics',
            'record_id': 'test-record-123'
            # Missing 'data' field
        }
        
        with self.assertRaises(SchemaValidationError):
            server.validate_input('update_record', invalid_input)
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_delete_record_validation(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test delete_record input validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test with valid input
        valid_input = {
            'table': 'sessions',
            'record_id': 'test-record-123'
        }
        
        result = server.validate_input('delete_record', valid_input)
        self.assertTrue(result)
        
        # Test with missing required field
        invalid_input = {
            'record_id': 'test-record-123'
            # Missing 'table' field
        }
        
        with self.assertRaises(SchemaValidationError):
            server.validate_input('delete_record', invalid_input)
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_crud_output_validation(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test CRUD operations output validation."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test create_record output validation
        valid_create_output = {
            'success': True,
            'record_id': 'test-123',
            'data': {'id': 'test-123', 'name': 'test'}
        }
        
        result = server.validate_output('create_record', valid_create_output)
        self.assertTrue(result)
        
        # Test read_record output validation
        valid_read_output = {
            'success': True,
            'data': {'id': 'test-123', 'name': 'test'}
        }
        
        result = server.validate_output('read_record', valid_read_output)
        self.assertTrue(result)
        
        # Test update_record output validation
        valid_update_output = {
            'success': True,
            'data': {'id': 'test-123', 'name': 'updated'}
        }
        
        result = server.validate_output('update_record', valid_update_output)
        self.assertTrue(result)
        
        # Test delete_record output validation
        valid_delete_output = {
            'success': True,
            'message': 'Record deleted successfully'
        }
        
        result = server.validate_output('delete_record', valid_delete_output)
        self.assertTrue(result)
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_table_name_mapping(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test table name mapping functionality."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test valid table aliases
        self.assertEqual(server._get_table_name('sessions'), 'chatbot-sessions')
        self.assertEqual(server._get_table_name('conversations'), 'chatbot-conversations')
        self.assertEqual(server._get_table_name('analytics'), 'chatbot-analytics')
        
        # Test invalid table alias
        with self.assertRaises(MCPServerError) as context:
            server._get_table_name('invalid_table')
        
        self.assertEqual(context.exception.code, 'INVALID_TABLE')
    
    @patch.dict(os.environ, {
        'SESSIONS_TABLE': 'custom-sessions',
        'CONVERSATIONS_TABLE': 'custom-conversations',
        'ANALYTICS_TABLE': 'custom-analytics'
    })
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_custom_table_names(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test custom table names from environment variables."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        # Test custom table names from environment
        self.assertEqual(server._get_table_name('sessions'), 'custom-sessions')
        self.assertEqual(server._get_table_name('conversations'), 'custom-conversations')
        self.assertEqual(server._get_table_name('analytics'), 'custom-analytics')
    
    @patch('boto3.resource')
    @patch('boto3.client')
    def test_crud_tools_listed(self, mock_bedrock_client, mock_dynamodb_resource):
        """Test that CRUD tools are properly listed."""
        server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
        
        tools = server.list_available_tools()
        tool_names = [tool['name'] for tool in tools]
        
        # Check that all CRUD tools are listed
        self.assertIn('create_record', tool_names)
        self.assertIn('read_record', tool_names)
        self.assertIn('update_record', tool_names)
        self.assertIn('delete_record', tool_names)
        
        # Check tool descriptions
        create_tool = next(tool for tool in tools if tool['name'] == 'create_record')
        self.assertIn('DynamoDB', create_tool['description'])


if __name__ == '__main__':
    unittest.main()