"""
Working MCP server Lambda function for chatbot system.
"""

import json
import logging
import asyncio
from typing import Dict, Any
from mcp_server_working import MCPChatbotServer, MCPServerError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global MCP server instance
mcp_server_instance = None


def get_mcp_server() -> MCPChatbotServer:
    """
    Get or create MCP server instance.
    
    Returns:
        MCPChatbotServer instance
    """
    global mcp_server_instance
    
    if mcp_server_instance is None:
        try:
            mcp_server_instance = MCPChatbotServer()
            logger.info("MCP server instance created successfully")
        except Exception as e:
            logger.error(f"Failed to create MCP server instance: {str(e)}")
            raise
    
    return mcp_server_instance


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for MCP server operations.
    
    Args:
        event: Lambda event containing MCP request
        context: Lambda context object
        
    Returns:
        Response dictionary for direct Lambda invocation
    """
    try:
        logger.info("Processing MCP server request")
        logger.info(f"Event: {json.dumps(event)}")
        
        # Get MCP server instance
        mcp_server = get_mcp_server()
        
        # Extract action from event
        action = event.get('action')
        if not action:
            return {
                'statusCode': 400,
                'error': 'MISSING_ACTION',
                'message': 'Action parameter is required'
            }
        
        # Handle different actions
        if action == 'health_check':
            return {
                'statusCode': 200,
                'success': True,
                'message': 'MCP server is healthy',
                'server_info': {
                    'version': '1.0.0',
                    'tools_available': len(mcp_server.available_tools)
                }
            }
        
        elif action == 'get_available_tools':
            tools = asyncio.run(mcp_server.get_available_tools())
            return {
                'statusCode': 200,
                'success': True,
                'tools': tools
            }
        
        elif action == 'get_openapi_schema':
            schema_info = mcp_server.get_openapi_schema()
            return {
                'statusCode': 200,
                **schema_info
            }
        
        elif action == 'execute_tool':
            tool_name = event.get('tool_name')
            parameters = event.get('parameters', {})
            
            if not tool_name:
                return {
                    'statusCode': 400,
                    'error': 'MISSING_TOOL_NAME',
                    'message': 'Tool name is required for execute_tool action'
                }
            
            # Execute the tool
            result = asyncio.run(mcp_server.execute_tool(tool_name, parameters))
            
            return {
                'statusCode': 200,
                'success': True,
                'result': result
            }
        
        else:
            return {
                'statusCode': 400,
                'error': 'UNKNOWN_ACTION',
                'message': f'Unknown action: {action}'
            }
    
    except MCPServerError as e:
        logger.error(f"MCP server error: {str(e)}")
        return {
            'statusCode': 500,
            'error': e.code,
            'message': str(e)
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'error': 'INTERNAL_ERROR',
            'message': f'Internal server error: {str(e)}'
        }