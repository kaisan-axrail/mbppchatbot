"""
MCP server Lambda function for chatbot system.
"""

import json
import logging
from typing import Dict, Any
from mcp_server import MCPChatbotServer, MCPServerError

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
        
        # Get MCP server instance
        mcp_server = get_mcp_server()
        
        # Handle different action types (new format for MCP handler integration)
        action = event.get('action', event.get('requestType', 'info'))
        
        if action == 'info':
            # Return server and tool information
            response_data = mcp_server.get_tool_info()
            return response_data
        
        elif action == 'list_tools':
            # List available tools
            tools = mcp_server.list_available_tools()
            return {'tools': tools}
        
        elif action == 'execute_tool':
            # Execute a tool
            tool_name = event.get('tool_name', event.get('toolName'))
            parameters = event.get('parameters', {})
            
            if not tool_name:
                return {
                    'success': False,
                    'error': {
                        'code': 'MISSING_TOOL_NAME',
                        'message': 'tool_name is required'
                    }
                }
            
            # Since we're in a Lambda, we need to handle async execution
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    mcp_server.execute_tool(tool_name, parameters)
                )
                return result
            finally:
                loop.close()
        
        elif action == 'validate':
            # Validate input against schema
            tool_name = event.get('tool_name', event.get('toolName'))
            input_data = event.get('input_data', event.get('inputData', {}))
            
            if not tool_name:
                return {
                    'success': False,
                    'error': {
                        'code': 'MISSING_TOOL_NAME',
                        'message': 'tool_name is required'
                    }
                }
            
            try:
                mcp_server.validate_input(tool_name, input_data)
                return {'success': True, 'valid': True}
            except Exception as e:
                error_response = mcp_server.handle_error(e, tool_name)
                return {
                    'success': False,
                    'error': error_response
                }
        
        else:
            return {
                'success': False,
                'error': {
                    'code': 'INVALID_ACTION',
                    'message': f'Unknown action: {action}'
                }
            }
        
    except MCPServerError as e:
        logger.error(f"MCP server error: {str(e)}")
        return {
            'success': False,
            'error': {
                'code': e.code,
                'message': str(e)
            }
        }
    except Exception as e:
        logger.error(f"Unexpected error processing MCP request: {str(e)}")
        return {
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An unexpected error occurred'
            }
        }