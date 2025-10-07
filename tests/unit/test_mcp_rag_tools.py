"""
Unit tests for MCP RAG tools.
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


class TestMCPRAGTools(unittest.TestCase):
    """Test cases for MCP RAG tools."""
    
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
                '/search_documents': {
                    'post': {
                        'summary': 'Search documents using vector similarity',
                        'operationId': 'search_documents',
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
                                                'minLength': 1,
                                                'maxLength': 1000
                                            },
                                            'limit': {
                                                'type': 'integer',
                                                'default': 5,
                                                'minimum': 1,
                                                'maximum': 20
                                            },
                                            'threshold': {
                                                'type': 'number',
                                                'default': 0.7,
                                                'minimum': 0.0,
                                                'maximum': 1.0
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        'responses': {
                            '200': {
                                'description': 'Search results',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'array',
                                            'items': {
                                                'type': 'object',
                                                'required': ['id', 'content', 'source', 'score'],
                                                'properties': {
                                                    'id': {'type': 'string'},
                                                    'content': {'type': 'string'},
                                                    'source': {'type': 'string'},
                                                    'score': {
                                                        'type': 'number',
                                                        'minimum': 0.0,
                                                        'maximum': 1.0
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
        }
        
        # Create temporary schema file
        self.temp_schema_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        yaml.dump(self.test_schema, self.temp_schema_file)
        self.temp_schema_file.close()
        
        # Create MCP server instance
        self.server = MCPChatbotServer(schema_path=self.temp_schema_file.name)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_schema_file.name):
            os.unlink(self.temp_schema_file.name)
    
    def test_vector_search_basic_functionality(self):
        """Test basic vector search functionality."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Test vector search with valid parameters
            results = loop.run_until_complete(
                self.server._perform_vector_search_aws("test query", 5, 0.7)
            )
            
            # Verify results structure
            self.assertIsInstance(results, list)
            self.assertLessEqual(len(results), 5)
            
            for result in results:
                self.assertIn('id', result)
                self.assertIn('content', result)
                self.assertIn('source', result)
                self.assertIn('score', result)
                self.assertIsInstance(result['id'], str)
                self.assertIsInstance(result['content'], str)
                self.assertIsInstance(result['source'], str)
                self.assertIsInstance(result['score'], (int, float))
                self.assertGreaterEqual(result['score'], 0.7)
                self.assertLessEqual(result['score'], 1.0)
        
        finally:
            loop.close()
    
    def test_vector_search_threshold_filtering(self):
        """Test that vector search respects threshold parameter."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Test with high threshold
            results = loop.run_until_complete(
                self.server._perform_vector_search_aws("test query", 10, 0.9)
            )
            
            # All results should have score >= 0.9
            for result in results:
                self.assertGreaterEqual(result['score'], 0.9)
        
        finally:
            loop.close()
    
    def test_vector_search_limit_parameter(self):
        """Test that vector search respects limit parameter."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Test with limit of 2
            results = loop.run_until_complete(
                self.server._perform_vector_search_aws("test query", 2, 0.5)
            )
            
            # Should return at most 2 results
            self.assertLessEqual(len(results), 2)
        
        finally:
            loop.close()
    
    def test_vector_search_deterministic_results(self):
        """Test that vector search returns deterministic results for same query."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run same search twice
            results1 = loop.run_until_complete(
                self.server._perform_vector_search_aws("consistent query", 5, 0.7)
            )
            results2 = loop.run_until_complete(
                self.server._perform_vector_search_aws("consistent query", 5, 0.7)
            )
            
            # Results should be identical
            self.assertEqual(len(results1), len(results2))
            for r1, r2 in zip(results1, results2):
                self.assertEqual(r1['id'], r2['id'])
                self.assertEqual(r1['content'], r2['content'])
                self.assertEqual(r1['source'], r2['source'])
                self.assertEqual(r1['score'], r2['score'])
        
        finally:
            loop.close()
    
    def test_search_documents_input_validation(self):
        """Test search_documents input validation."""
        # Test with valid input
        valid_input = {
            'query': 'test query',
            'limit': 5,
            'threshold': 0.7
        }
        
        result = self.server.validate_input('search_documents', valid_input)
        self.assertTrue(result)
        
        # Test with missing required field
        invalid_input = {
            'limit': 5,
            'threshold': 0.7
        }
        
        with self.assertRaises(SchemaValidationError):
            self.server.validate_input('search_documents', invalid_input)
        
        # Test with invalid limit
        invalid_limit = {
            'query': 'test query',
            'limit': 25,  # Exceeds maximum of 20
            'threshold': 0.7
        }
        
        with self.assertRaises(SchemaValidationError):
            self.server.validate_input('search_documents', invalid_limit)
        
        # Test with invalid threshold
        invalid_threshold = {
            'query': 'test query',
            'limit': 5,
            'threshold': 1.5  # Exceeds maximum of 1.0
        }
        
        with self.assertRaises(SchemaValidationError):
            self.server.validate_input('search_documents', invalid_threshold)
    
    def test_search_documents_output_validation(self):
        """Test search_documents output validation."""
        # Test with valid output
        valid_output = [
            {
                'id': 'doc_1',
                'content': 'Test content 1',
                'source': 'document1.pdf',
                'score': 0.85
            },
            {
                'id': 'doc_2',
                'content': 'Test content 2',
                'source': 'document2.pdf',
                'score': 0.75
            }
        ]
        
        result = self.server.validate_output('search_documents', valid_output)
        self.assertTrue(result)
        
        # Test with invalid output (missing required field)
        invalid_output = [
            {
                'id': 'doc_1',
                'content': 'Test content 1',
                'source': 'document1.pdf'
                # Missing 'score' field
            }
        ]
        
        with self.assertRaises(SchemaValidationError):
            self.server.validate_output('search_documents', invalid_output)
        
        # Test with invalid score range
        invalid_score = [
            {
                'id': 'doc_1',
                'content': 'Test content 1',
                'source': 'document1.pdf',
                'score': 1.5  # Exceeds maximum of 1.0
            }
        ]
        
        with self.assertRaises(SchemaValidationError):
            self.server.validate_output('search_documents', invalid_score)
    
    def test_rag_tool_error_handling(self):
        """Test error handling in RAG tools."""
        # Test with empty query
        with self.assertRaises(SchemaValidationError):
            self.server.validate_input('search_documents', {'query': ''})
        
        # Test with query too long
        long_query = 'a' * 1001  # Exceeds maximum length
        with self.assertRaises(SchemaValidationError):
            self.server.validate_input('search_documents', {'query': long_query})
    
    def test_tool_execution(self):
        """Test tool execution functionality."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Test successful tool execution
            result = loop.run_until_complete(
                self.server.execute_tool('search_documents', {
                    'query': 'test query',
                    'limit': 3,
                    'threshold': 0.7
                })
            )
            
            self.assertTrue(result['success'])
            self.assertIn('result', result)
            self.assertEqual(result['tool'], 'search_documents')
            
            # Verify result structure
            search_results = result['result']
            self.assertIsInstance(search_results, list)
            self.assertLessEqual(len(search_results), 3)
            
        finally:
            loop.close()
    
    def test_list_available_tools(self):
        """Test listing available tools."""
        tools = self.server.list_available_tools()
        
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        
        # Check search_documents tool is listed
        tool_names = [tool['name'] for tool in tools]
        self.assertIn('search_documents', tool_names)
        
        # Check tool structure
        search_tool = next(tool for tool in tools if tool['name'] == 'search_documents')
        self.assertIn('description', search_tool)
        self.assertIn('parameters', search_tool)


if __name__ == '__main__':
    unittest.main()