"""
Working MCP server implementation with OpenAPI schema validation and CRUD tools.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
import yaml
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import uuid


class MCPServerError(Exception):
    """Base exception for MCP server errors."""
    
    def __init__(self, message: str, code: str = "MCP_ERROR"):
        super().__init__(message)
        self.code = code


class SchemaValidationError(MCPServerError):
    """Exception for OpenAPI schema validation errors."""
    
    def __init__(self, message: str):
        super().__init__(message, "SCHEMA_VALIDATION_ERROR")


class MCPChatbotServer:
    """
    Working MCP server for chatbot with RAG and CRUD tools using OpenAPI schema validation.
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize MCP server with OpenAPI schema.
        
        Args:
            schema_path: Path to OpenAPI schema file
        """
        self.logger = self._setup_logging()
        self.schema_path = schema_path or os.environ.get(
            'SCHEMA_PATH', 
            '/var/task/mcp_tools_schema.yaml'
        )
        
        # Initialize AWS clients
        self.dynamodb = boto3.resource('dynamodb')
        self.bedrock = boto3.client('bedrock-runtime')
        self.s3 = boto3.client('s3')
        
        # Get table names from environment
        self.sessions_table_name = os.environ.get('SESSIONS_TABLE', 'chatbot-sessions')
        self.conversations_table_name = os.environ.get('CONVERSATIONS_TABLE', 'chatbot-conversations')
        self.analytics_table_name = os.environ.get('ANALYTICS_TABLE', 'chatbot-analytics')
        self.events_table_name = os.environ.get('EVENTS_TABLE', 'chatbot-events')
        
        try:
            self.schema = self._load_openapi_schema()
            self.logger.info(f"✅ OpenAPI schema loaded successfully from {self.schema_path}")
            if 'servers' in self.schema:
                self.logger.info(f"API Server: {self.schema['servers'][0]['url']}")
        except Exception as e:
            self.logger.error(f"❌ Failed to load OpenAPI schema: {str(e)}")
            # Continue without schema validation for now
            self.schema = None
        
        # Initialize available tools
        self.available_tools = self._initialize_tools()
        self.logger.info("MCP server initialized successfully")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up structured logging for MCP operations."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _load_openapi_schema(self) -> Dict[str, Any]:
        """
        Load OpenAPI schema for tool validation.
        
        Returns:
            Parsed OpenAPI schema dictionary
            
        Raises:
            MCPServerError: If schema file cannot be loaded or parsed
        """
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
            
            # Validate that it's a valid OpenAPI schema
            if not isinstance(schema, dict) or 'openapi' not in schema:
                raise MCPServerError("Invalid OpenAPI schema format")
            
            return schema
            
        except FileNotFoundError:
            raise MCPServerError(f"Schema file not found: {self.schema_path}")
        except yaml.YAMLError as e:
            raise MCPServerError(f"Invalid YAML in schema file: {str(e)}")
        except Exception as e:
            raise MCPServerError(f"Failed to load schema: {str(e)}")
    
    def _initialize_tools(self) -> List[Dict[str, Any]]:
        """
        Initialize available tools from OpenAPI schema.
        
        Returns:
            List of available tool definitions
        """
        tools = []
        
        # Define tools based on OpenAPI schema
        if self.schema and 'paths' in self.schema:
            self.logger.info("Loading tools from OpenAPI schema")
            for path, methods in self.schema['paths'].items():
                for method, spec in methods.items():
                    if method.lower() == 'post':
                        tool_name = spec.get('operationId', path.strip('/'))
                        tools.append({
                            'name': tool_name,
                            'description': spec.get('summary', ''),
                            'path': path,
                            'method': method.upper(),
                            'schema': spec.get('requestBody', {})
                        })
            self.logger.info(f"Loaded {len(tools)} tools from OpenAPI schema: {[t['name'] for t in tools]}")
        else:
            self.logger.warning("OpenAPI schema not available, using fallback tool definitions")
            # Fallback tool definitions with proper schemas
            tools = [
                {
                    'name': 'list_events',
                    'description': 'List all events from the database. Use this to find events by name or see all available events.',
                    'parameters': {}
                },
                {
                    'name': 'search_documents',
                    'description': 'Search documents using vector similarity for RAG queries',
                    'parameters': {'query': 'string', 'limit': 'integer', 'threshold': 'float'}
                },
                {
                    'name': 'create_event',
                    'description': 'Create a new event in the database',
                    'parameters': {'data': 'object'}
                },
                {
                    'name': 'read_event',
                    'description': 'Read a specific event by ID',
                    'parameters': {'record_id': 'string'}
                },
                {
                    'name': 'update_event',
                    'description': 'Update an existing event',
                    'parameters': {'record_id': 'string', 'data': 'object'}
                },
                {
                    'name': 'delete_event',
                    'description': 'Delete an event from the database',
                    'parameters': {'record_id': 'string'}
                }
            ]
            self.logger.info(f"Loaded {len(tools)} fallback tools: {[t['name'] for t in tools]}")
        
        return tools
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools.
        
        Returns:
            List of available tool definitions
        """
        self.logger.info(f"Returning {len(self.available_tools)} available tools")
        return self.available_tools
    
    def get_openapi_schema(self) -> Dict[str, Any]:
        """
        Get the full OpenAPI schema.
        
        Returns:
            OpenAPI schema dictionary or error message
        """
        if self.schema:
            return {
                "success": True,
                "schema": self.schema,
                "source": "openapi_file"
            }
        else:
            return {
                "success": False,
                "message": "OpenAPI schema not loaded, using fallback tools",
                "source": "fallback",
                "tools": self.available_tools
            }
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with given parameters."""
        self.logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")
        
        try:
            if tool_name == 'search_documents':
                return await self.search_documents(**parameters)
            else:
                raise MCPServerError(f"Unknown tool: {tool_name}")
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}")
            raise MCPServerError(f"Tool execution failed: {str(e)}")
    
    async def search_documents(self, query: str, limit: int = 5, threshold: float = 0.7) -> Dict[str, Any]:
        """
        Search documents using both Bedrock Knowledge Bases.
        
        Args:
            query: Search query text
            limit: Maximum number of results per knowledge base
            threshold: Minimum similarity score
            
        Returns:
            Combined search results from both knowledge bases
        """
        self.logger.info(f"Searching knowledge bases for query: {query}")
        
        try:
            # Get knowledge base IDs from environment
            kb_ids = [
                'U6EAI0DHJC',  # mbpp-faq-knowledgebase
                'CTFE3RJR01'   # mbpp-knowledgebase-url
            ]
            
            # Initialize Bedrock Agent Runtime client
            bedrock_agent = boto3.client('bedrock-agent-runtime')
            
            all_results = []
            
            # Query each knowledge base
            for kb_id in kb_ids:
                try:
                    response = bedrock_agent.retrieve(
                        knowledgeBaseId=kb_id,
                        retrievalQuery={'text': query},
                        retrievalConfiguration={
                            'vectorSearchConfiguration': {
                                'numberOfResults': limit
                            }
                        }
                    )
                    
                    # Format results
                    for item in response.get('retrievalResults', []):
                        score = item.get('score', 0.0)
                        if score >= threshold:
                            all_results.append({
                                'content': item.get('content', {}).get('text', ''),
                                'score': float(score),
                                'source': item.get('location', {}).get('s3Location', {}).get('uri', 'unknown'),
                                'knowledge_base': kb_id,
                                'metadata': item.get('metadata', {})
                            })
                    
                    self.logger.info(f"Found {len(response.get('retrievalResults', []))} results from KB {kb_id}")
                    
                except Exception as kb_error:
                    self.logger.error(f"Error querying KB {kb_id}: {str(kb_error)}")
                    continue
            
            # Sort by score and limit total results
            all_results.sort(key=lambda x: x['score'], reverse=True)
            all_results = all_results[:limit * 2]  # Return up to 2x limit from both KBs
            
            self.logger.info(f"Found {len(all_results)} total documents from both knowledge bases")
            
            return {
                "success": True,
                "results": all_results,
                "query": query,
                "total_results": len(all_results)
            }
            
        except Exception as e:
            self.logger.error(f"Error searching knowledge bases: {str(e)}")
            return {
                "success": False,
                "results": [],
                "query": query,
                "total_results": 0,
                "error": str(e)
            }
    
    async def create_record(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new record in DynamoDB table.
        
        Args:
            table: Table name (sessions, conversations, analytics)
            data: Record data to create
            
        Returns:
            Creation result with record ID
        """
        self.logger.info(f"Creating record in table: {table}")
        
        # Map table names
        table_mapping = {
            'events': self.events_table_name
        }
        
        if table not in table_mapping:
            raise MCPServerError(f"Invalid table name: {table}")
        
        actual_table_name = table_mapping[table]
        
        try:
            # Get DynamoDB table
            dynamodb_table = self.dynamodb.Table(actual_table_name)
            
            # Generate record ID if not provided
            if table == 'sessions' and 'sessionId' not in data:
                data['sessionId'] = str(uuid.uuid4())
            elif table == 'conversations' and 'conversationId' not in data:
                data['conversationId'] = str(uuid.uuid4())
            elif table == 'analytics' and 'analyticsId' not in data:
                data['analyticsId'] = str(uuid.uuid4())
            elif table == 'events' and 'eventId' not in data:
                data['eventId'] = str(uuid.uuid4())
            
            # Add timestamp
            data['created_at'] = datetime.now().isoformat()
            
            # Put item in DynamoDB
            response = dynamodb_table.put_item(Item=data)
            
            # Get the record ID
            record_id = data.get('sessionId') or data.get('conversationId') or data.get('analyticsId') or data.get('eventId')
            
            self.logger.info(f"Successfully created record {record_id} in {actual_table_name}")
            
            return {
                "success": True,
                "record_id": record_id,
                "data": data
            }
            
        except ClientError as e:
            error_msg = f"DynamoDB error creating record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error creating record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
    
    async def read_record(self, table: str, record_id: str) -> Dict[str, Any]:
        """
        Read a record from DynamoDB table.
        
        Args:
            table: Table name (sessions, conversations, analytics)
            record_id: Record identifier to retrieve
            
        Returns:
            Retrieved record data
        """
        self.logger.info(f"Reading record {record_id} from table: {table}")
        
        # Map table names
        table_mapping = {
            'events': self.events_table_name
        }
        
        if table not in table_mapping:
            raise MCPServerError(f"Invalid table name: {table}")
        
        actual_table_name = table_mapping[table]
        
        try:
            # Get DynamoDB table
            dynamodb_table = self.dynamodb.Table(actual_table_name)
            
            # Determine key name based on table
            if table == 'sessions':
                key_name = 'sessionId'
            elif table == 'conversations':
                key_name = 'conversationId'
            elif table == 'analytics':
                key_name = 'analyticsId'
            else:
                key_name = 'eventId'
            
            # Get item from DynamoDB
            response = dynamodb_table.get_item(
                Key={key_name: record_id}
            )
            
            if 'Item' not in response:
                raise MCPServerError(f"Record {record_id} not found in {table}")
            
            item = response['Item']
            self.logger.info(f"Successfully retrieved record {record_id} from {actual_table_name}")
            
            return {
                "success": True,
                "data": item
            }
            
        except ClientError as e:
            error_msg = f"DynamoDB error reading record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error reading record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
    
    async def update_record(self, table: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a record in DynamoDB table.
        
        Args:
            table: Table name (sessions, conversations, analytics)
            record_id: Record identifier to update
            data: Updated record data
            
        Returns:
            Update result
        """
        self.logger.info(f"Updating record {record_id} in table: {table}")
        
        # Map table names
        table_mapping = {
            'events': self.events_table_name
        }
        
        if table not in table_mapping:
            raise MCPServerError(f"Invalid table name: {table}")
        
        actual_table_name = table_mapping[table]
        
        try:
            # Get DynamoDB table
            dynamodb_table = self.dynamodb.Table(actual_table_name)
            
            # Determine key name based on table
            if table == 'sessions':
                key_name = 'sessionId'
            elif table == 'conversations':
                key_name = 'conversationId'
            elif table == 'analytics':
                key_name = 'analyticsId'
            else:
                key_name = 'eventId'
            
            # Add updated timestamp
            data['updated_at'] = datetime.now().isoformat()
            
            # Build update expression
            update_expression = "SET "
            expression_attribute_values = {}
            expression_attribute_names = {}
            
            for key, value in data.items():
                if key != key_name:  # Don't update the primary key
                    attr_name = f"#{key}"
                    attr_value = f":{key}"
                    update_expression += f"{attr_name} = {attr_value}, "
                    expression_attribute_names[attr_name] = key
                    expression_attribute_values[attr_value] = value
            
            # Remove trailing comma and space
            update_expression = update_expression.rstrip(', ')
            
            # Update item in DynamoDB
            response = dynamodb_table.update_item(
                Key={key_name: record_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            
            updated_item = response.get('Attributes', {})
            self.logger.info(f"Successfully updated record {record_id} in {actual_table_name}")
            
            return {
                "success": True,
                "data": updated_item
            }
            
        except ClientError as e:
            error_msg = f"DynamoDB error updating record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error updating record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
    
    async def delete_record(self, table: str, record_id: str) -> Dict[str, Any]:
        """
        Delete a record from DynamoDB table.
        
        Args:
            table: Table name (sessions, conversations, analytics)
            record_id: Record identifier to delete
            
        Returns:
            Deletion result
        """
        self.logger.info(f"Deleting record {record_id} from table: {table}")
        
        # Map table names
        table_mapping = {
            'events': self.events_table_name
        }
        
        if table not in table_mapping:
            raise MCPServerError(f"Invalid table name: {table}")
        
        actual_table_name = table_mapping[table]
        
        try:
            # Get DynamoDB table
            dynamodb_table = self.dynamodb.Table(actual_table_name)
            
            # Determine key name based on table
            if table == 'sessions':
                key_name = 'sessionId'
            elif table == 'conversations':
                key_name = 'conversationId'
            elif table == 'analytics':
                key_name = 'analyticsId'
            else:
                key_name = 'eventId'
            
            # Delete item from DynamoDB
            response = dynamodb_table.delete_item(
                Key={key_name: record_id},
                ReturnValues="ALL_OLD"
            )
            
            deleted_item = response.get('Attributes')
            if not deleted_item:
                raise MCPServerError(f"Record {record_id} not found in {table}")
            
            self.logger.info(f"Successfully deleted record {record_id} from {actual_table_name}")
            
            return {
                "success": True,
                "message": f"Record {record_id} deleted successfully"
            }
            
        except ClientError as e:
            error_msg = f"DynamoDB error deleting record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error deleting record: {str(e)}"
            self.logger.error(error_msg)
            raise MCPServerError(error_msg)