"""
Real MCP client implementation using official MCP SDK with Strands Agent.
"""

import os
import logging
from typing import Dict, Any, List
from strands import Agent
import boto3
import json

logger = logging.getLogger(__name__)


class RealMCPHandler:
    """Real MCP handler using official MCP protocol."""
    
    def __init__(self, mcp_lambda_arn: str):
        """
        Initialize real MCP handler.
        
        Args:
            mcp_lambda_arn: ARN of MCP server Lambda function
        """
        self.mcp_lambda_arn = mcp_lambda_arn
        self.lambda_client = boto3.client('lambda')
        logger.info(f"Real MCP handler initialized with Lambda ARN: {mcp_lambda_arn}")
    
    async def process_with_agent(self, message: str, conversation_history: List[Dict[str, str]]) -> str:
        """
        Process message using Strands Agent with MCP tools via Lambda invocation.
        
        Args:
            message: User message
            conversation_history: Previous conversation
            
        Returns:
            Agent response
        """
        try:
            # Get available tools from MCP server
            response = self.lambda_client.invoke(
                FunctionName=self.mcp_lambda_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps({'action': 'get_available_tools'})
            )
            result = json.loads(response['Payload'].read())
            
            if not result.get('success'):
                raise Exception(f"Failed to get tools: {result.get('message')}")
            
            tools = result.get('tools', [])
            logger.info(f"Retrieved {len(tools)} tools from MCP server")
            
            # Create Strands Agent with MCP tools
            agent = Agent(tools=[self._create_lambda_tool(tool) for tool in tools])
            
            # Format conversation history
            history_text = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in conversation_history[-5:]
            ])
            
            # Build prompt
            prompt = f"{history_text}\nuser: {message}" if history_text else message
            
            # Execute agent
            response = agent(prompt)
            
            # Extract text from AgentResult
            if hasattr(response, 'output'):
                return response.output
            elif hasattr(response, 'text'):
                return response.text
            elif isinstance(response, str):
                return response
            else:
                return str(response)
                
        except Exception as e:
            logger.error(f"Error processing with MCP agent: {str(e)}")
            raise
    
    def _create_lambda_tool(self, tool_info: Dict[str, Any]):
        """Create a Strands tool that invokes MCP Lambda with OpenAPI schema."""
        from strands.tools import tool
        
        # Extract parameter schema from OpenAPI format
        params_schema = self._extract_parameters_from_schema(tool_info)
        
        # Build function signature dynamically based on schema
        def lambda_tool(**kwargs):
            """Execute MCP tool via Lambda."""
            response = self.lambda_client.invoke(
                FunctionName=self.mcp_lambda_arn,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'action': 'execute_tool',
                    'tool_name': tool_info['name'],
                    'parameters': kwargs
                })
            )
            result = json.loads(response['Payload'].read())
            return json.dumps(result.get('result', {}))
        
        # Set function metadata
        lambda_tool.__name__ = tool_info['name']
        lambda_tool.__doc__ = self._build_tool_docstring(tool_info, params_schema)
        
        # Apply @tool decorator with schema
        return tool(lambda_tool)
    
    def _extract_parameters_from_schema(self, tool_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters from OpenAPI schema format."""
        schema = tool_info.get('schema', {})
        
        # Navigate OpenAPI structure: requestBody -> content -> application/json -> schema -> properties
        if 'content' in schema:
            json_schema = schema.get('content', {}).get('application/json', {}).get('schema', {})
            return json_schema.get('properties', {})
        
        # Fallback to simple parameters format
        return tool_info.get('parameters', {})
    
    def _build_tool_docstring(self, tool_info: Dict[str, Any], params: Dict[str, Any]) -> str:
        """Build comprehensive docstring from OpenAPI schema."""
        doc = tool_info.get('description', f"Execute {tool_info['name']} tool")
        
        if params:
            doc += "\n\nParameters:\n"
            for param_name, param_info in params.items():
                if isinstance(param_info, dict):
                    param_type = param_info.get('type', 'any')
                    param_desc = param_info.get('description', '')
                    doc += f"  {param_name} ({param_type}): {param_desc}\n"
                else:
                    doc += f"  {param_name}: {param_info}\n"
        
        return doc


def create_real_mcp_handler(mcp_lambda_arn: str = None) -> RealMCPHandler:
    """
    Factory function to create real MCP handler.
    
    Args:
        mcp_lambda_arn: MCP server Lambda ARN
        
    Returns:
        RealMCPHandler instance
    """
    arn = mcp_lambda_arn or os.environ.get('MCP_SERVER_ARN')
    if not arn:
        raise ValueError("MCP_SERVER_ARN not configured")
    
    return RealMCPHandler(arn)
