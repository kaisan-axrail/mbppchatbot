"""
MCP handler for tool execution in Python.
Handles identification, execution, and processing of MCP tools.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
import asyncio
import boto3
from botocore.exceptions import ClientError

from shared.strand_client import StrandClient, format_messages_for_strand, extract_text_from_strand_response
from shared.exceptions import (
    McpHandlerError,
    StrandClientError,
    LambdaExecutionError,
    ConfigurationError,
    get_user_friendly_message
)
from shared.retry_utils import (
    retry_with_backoff,
    with_graceful_degradation,
    MCP_RETRY_CONFIG,
    handle_service_failure
)


# Configure logging
logger = logging.getLogger(__name__)


class MCPHandler:
    """
    MCP handler class for tool identification, execution, and result processing.
    """
    
    def __init__(self, mcp_server_lambda_arn: str = None, region: str = None):
        """
        Initialize MCP handler with client connections.
        
        Args:
            mcp_server_lambda_arn: ARN of the MCP server Lambda function
            region: AWS region for Lambda client
        """
        self.region = region or os.environ.get('AWS_REGION', 'us-east-1')
        self.mcp_server_lambda_arn = mcp_server_lambda_arn or os.environ.get(
            'MCP_SERVER_LAMBDA_ARN'
        )
        
        if not self.mcp_server_lambda_arn:
            raise ConfigurationError(
                "MCP server Lambda ARN not configured",
                "MCP_SERVER_LAMBDA_ARN"
            )
        
        # Initialize AWS Lambda client for MCP server communication
        self.lambda_client = boto3.client('lambda', region_name=self.region)
        
        # Initialize Strand SDK client for Claude Sonnet 4.5 interactions
        try:
            self.strand_client = StrandClient(region=self.region)
        except StrandClientError as e:
            logger.error(f"Failed to initialize Strand client: {str(e)}")
            raise McpHandlerError(
                f"Failed to initialize Strand client: {str(e)}",
                "STRAND_INITIALIZATION_ERROR"
            )
        
        # Cache for available tools
        self._available_tools: Optional[List[Dict[str, Any]]] = None
        
        logger.info("MCP handler initialized successfully")
    
    async def identify_tools(self, query: str) -> List[str]:
        """
        Identify required MCP tools from user query using Claude Sonnet 4.5.
        
        Args:
            query: User query text
            
        Returns:
            List of tool names that should be used
            
        Raises:
            MCPHandlerError: If tool identification fails
        """
        try:
            logger.info(f"Identifying tools for query: {query[:100]}...")
            
            # Get available tools if not cached
            if self._available_tools is None:
                self._available_tools = await self._get_available_tools()
            
            # Create system prompt for tool identification with multilingual support
            base_prompt = self._create_tool_identification_prompt(self._available_tools)
            
            # Import multilingual service to enhance the prompt
            from shared.multilingual_prompts import MultilingualPromptService
            multilingual_service = MultilingualPromptService()
            system_prompt = multilingual_service.ensure_multilingual_capabilities(base_prompt)
            
            # Format messages for Strand SDK
            messages = format_messages_for_strand(query)
            
            # Generate response using Claude Sonnet 4.5
            response = await self.strand_client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent tool identification
            )
            
            # Extract and parse tool names from response
            response_text = extract_text_from_strand_response(response)
            identified_tools = self._parse_tool_names_from_response(response_text)
            
            logger.info(f"Identified {len(identified_tools)} tools: {identified_tools}")
            return identified_tools
            
        except StrandClientError as e:
            logger.error(f"Strand client error during tool identification: {str(e)}")
            raise McpHandlerError(
                f"Tool identification failed: {str(e)}",
                "TOOL_IDENTIFICATION_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error during tool identification: {str(e)}")
            raise McpHandlerError(
                f"Tool identification failed: {str(e)}",
                "TOOL_IDENTIFICATION_ERROR"
            )
    
    @retry_with_backoff(
        config=MCP_RETRY_CONFIG,
        service_name="mcp_lambda"
    )
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
            
        Raises:
            MCPHandlerError: If tool execution fails
        """
        try:
            logger.info(f"Executing MCP tool: {tool_name}")
            logger.debug(f"Tool parameters: {parameters}")
            
            # Prepare Lambda payload for MCP server
            payload = {
                "action": "execute_tool",
                "tool_name": tool_name,
                "parameters": parameters
            }
            
            # Invoke MCP server Lambda function
            response = self.lambda_client.invoke(
                FunctionName=self.mcp_server_lambda_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            # Parse Lambda response
            response_payload = json.loads(response['Payload'].read())
            
            # Check for Lambda execution errors
            if response.get('FunctionError'):
                error_message = response_payload.get('errorMessage', 'Unknown Lambda error')
                raise LambdaExecutionError(
                    self.mcp_server_lambda_arn.split(':')[-1],  # Extract function name
                    error_message
                )
            
            # Check for MCP tool execution errors
            if not response_payload.get('success', False):
                error_info = response_payload.get('error', {})
                error_message = error_info.get('message', 'Unknown MCP tool error')
                raise MCPHandlerError(
                    f"MCP tool execution failed: {error_message}",
                    "MCP_TOOL_EXECUTION_ERROR"
                )
            
            result = response_payload.get('result', {})
            logger.info(f"Successfully executed tool {tool_name}")
            
            return result
            
        except ClientError as e:
            logger.error(f"AWS Lambda client error: {str(e)}")
            raise MCPHandlerError(
                f"Failed to invoke MCP server: {str(e)}",
                "LAMBDA_CLIENT_ERROR"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Lambda response: {str(e)}")
            raise MCPHandlerError(
                f"Invalid response from MCP server: {str(e)}",
                "RESPONSE_PARSING_ERROR"
            )
        except MCPHandlerError:
            # Re-raise MCPHandlerError with original error code
            raise
        except Exception as e:
            logger.error(f"Unexpected error during tool execution: {str(e)}")
            raise MCPHandlerError(
                f"Tool execution failed: {str(e)}",
                "TOOL_EXECUTION_ERROR"
            )
    
    async def process_tool_results(self, results: List[Dict[str, Any]], original_query: str) -> str:
        """
        Process tool execution results and generate response using Claude Sonnet 4.5.
        
        Args:
            results: List of tool execution results
            original_query: Original user query
            
        Returns:
            Generated response text incorporating tool results
            
        Raises:
            MCPHandlerError: If result processing fails
        """
        try:
            logger.info(f"Processing {len(results)} tool results")
            
            # Create system prompt for result processing with multilingual support
            base_prompt = self._create_result_processing_prompt()
            
            # Import multilingual service to enhance the prompt
            from shared.multilingual_prompts import MultilingualPromptService
            multilingual_service = MultilingualPromptService()
            system_prompt = multilingual_service.ensure_multilingual_capabilities(base_prompt)
            
            # Format tool results for Claude
            results_text = self._format_tool_results_for_claude(results)
            
            # Create user message with original query and tool results
            user_message = f"""
Original Query: {original_query}

Tool Execution Results:
{results_text}

Please provide a comprehensive response to the original query based on the tool execution results above.
"""
            
            # Format messages for Strand SDK
            messages = format_messages_for_strand(user_message)
            
            # Generate response using Claude Sonnet 4.5
            response = await self.strand_client.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=2000,
                temperature=0.7
            )
            
            # Extract response text
            response_text = extract_text_from_strand_response(response)
            
            if not response_text:
                raise MCPHandlerError(
                    "Empty response from Claude Sonnet 4.5",
                    "EMPTY_RESPONSE_ERROR"
                )
            
            logger.info("Successfully processed tool results")
            return response_text
            
        except MCPHandlerError:
            # Re-raise MCPHandlerError with original error code
            raise
        except StrandClientError as e:
            logger.error(f"Strand client error during result processing: {str(e)}")
            raise MCPHandlerError(
                f"Result processing failed: {str(e)}",
                "RESULT_PROCESSING_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error during result processing: {str(e)}")
            raise MCPHandlerError(
                f"Result processing failed: {str(e)}",
                "RESULT_PROCESSING_ERROR"
            )
    
    async def _get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools from MCP server.
        
        Returns:
            List of available tool information
            
        Raises:
            MCPHandlerError: If unable to get tool list
        """
        try:
            logger.info("Fetching available tools from MCP server")
            
            # Prepare Lambda payload for listing tools
            payload = {
                "action": "list_tools"
            }
            
            # Invoke MCP server Lambda function
            response = self.lambda_client.invoke(
                FunctionName=self.mcp_server_lambda_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            # Parse Lambda response
            response_payload = json.loads(response['Payload'].read())
            
            # Check for Lambda execution errors
            if response.get('FunctionError'):
                error_message = response_payload.get('errorMessage', 'Unknown Lambda error')
                raise MCPHandlerError(
                    f"Failed to get tool list: {error_message}",
                    "TOOL_LIST_ERROR"
                )
            
            tools = response_payload.get('tools', [])
            logger.info(f"Retrieved {len(tools)} available tools")
            
            return tools
            
        except ClientError as e:
            logger.error(f"AWS Lambda client error: {str(e)}")
            raise MCPHandlerError(
                f"Failed to get tool list: {str(e)}",
                "LAMBDA_CLIENT_ERROR"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Lambda response: {str(e)}")
            raise MCPHandlerError(
                f"Invalid response from MCP server: {str(e)}",
                "RESPONSE_PARSING_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error getting tool list: {str(e)}")
            raise MCPHandlerError(
                f"Failed to get tool list: {str(e)}",
                "TOOL_LIST_ERROR"
            )
    
    def _create_tool_identification_prompt(self, available_tools: List[Dict[str, Any]]) -> str:
        """
        Create system prompt for tool identification.
        
        Args:
            available_tools: List of available tool information
            
        Returns:
            System prompt text
        """
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in available_tools
        ])
        
        return f"""You are an AI assistant that identifies which MCP tools should be used to answer user queries.

Available MCP Tools:
{tools_description}

Your task is to analyze the user's query and determine which tools (if any) should be used to provide a complete answer.

Rules:
1. Only suggest tools that are directly relevant to answering the query
2. Consider the user's intent and what information they need
3. For document search queries, use search_documents
4. For data management queries (create, read, update, delete), use the appropriate CRUD tools
5. If no tools are needed (general conversation), respond with "NONE"
6. If multiple tools are needed, list them separated by commas

Respond with only the tool names (comma-separated) or "NONE". Do not include explanations.

Examples:
- "Find documents about AWS Lambda" → search_documents
- "Create a new user record" → create_record
- "What's the weather like?" → NONE
- "Search for pricing info and save it to database" → search_documents,create_record
"""
    
    def _create_result_processing_prompt(self) -> str:
        """
        Create system prompt for processing tool results.
        
        Returns:
            System prompt text
        """
        return """You are an AI assistant that processes MCP tool execution results and generates comprehensive responses.

Your task is to:
1. Analyze the tool execution results provided
2. Synthesize the information to answer the original user query
3. Provide a clear, helpful response that incorporates the tool results
4. If tool results contain errors, explain what went wrong and suggest alternatives
5. Cite sources when relevant (especially for document search results)
6. Be concise but comprehensive

Guidelines:
- Focus on answering the user's original question
- Use the tool results as evidence and supporting information
- If multiple tools were used, integrate their results coherently
- If tools failed, explain the failure and provide what information you can
- Maintain a helpful and professional tone
"""
    
    def _parse_tool_names_from_response(self, response_text: str) -> List[str]:
        """
        Parse tool names from Claude's response.
        
        Args:
            response_text: Response text from Claude
            
        Returns:
            List of tool names
        """
        # Clean up the response text
        response_text = response_text.strip()
        
        # Handle "NONE" case
        if response_text.upper() == "NONE":
            return []
        
        # Split by comma and clean up tool names
        tool_names = [
            name.strip() 
            for name in response_text.split(',')
            if name.strip()
        ]
        
        # Validate tool names against available tools
        if self._available_tools:
            available_tool_names = {tool['name'] for tool in self._available_tools}
            valid_tools = [
                name for name in tool_names 
                if name in available_tool_names
            ]
            
            if len(valid_tools) != len(tool_names):
                invalid_tools = set(tool_names) - set(valid_tools)
                logger.warning(f"Invalid tool names identified: {invalid_tools}")
            
            return valid_tools
        
        return tool_names
    
    def _format_tool_results_for_claude(self, results: List[Dict[str, Any]]) -> str:
        """
        Format tool execution results for Claude processing.
        
        Args:
            results: List of tool execution results
            
        Returns:
            Formatted results text
        """
        formatted_results = []
        
        for i, result in enumerate(results, 1):
            tool_name = result.get('tool', 'unknown')
            success = result.get('success', False)
            
            if success:
                tool_result = result.get('result', {})
                formatted_results.append(f"""
Tool {i}: {tool_name}
Status: Success
Result: {json.dumps(tool_result, indent=2)}
""")
            else:
                error_info = result.get('error', {})
                error_message = error_info.get('message', 'Unknown error')
                formatted_results.append(f"""
Tool {i}: {tool_name}
Status: Failed
Error: {error_message}
""")
        
        return "\n".join(formatted_results)
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate MCP handler configuration.
        
        Returns:
            Configuration validation results
        """
        validation_results = {
            "mcp_server_lambda_arn": self.mcp_server_lambda_arn,
            "region": self.region,
            "strand_client_configured": bool(self.strand_client),
            "lambda_client_configured": bool(self.lambda_client)
        }
        
        # Test Strand client configuration
        try:
            strand_config = self.strand_client.validate_configuration()
            validation_results["strand_configuration"] = strand_config
        except Exception as e:
            validation_results["strand_configuration_error"] = str(e)
        
        logger.info("MCP handler configuration validation completed")
        return validation_results


def create_mcp_handler(mcp_server_lambda_arn: str = None, region: str = None) -> MCPHandler:
    """
    Factory function to create a configured MCP handler.
    
    Args:
        mcp_server_lambda_arn: ARN of the MCP server Lambda function
        region: AWS region for Lambda client
        
    Returns:
        Configured MCPHandler instance
    """
    return MCPHandler(mcp_server_lambda_arn=mcp_server_lambda_arn, region=region)