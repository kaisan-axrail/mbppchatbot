"""API Gateway handler for MCP tools."""
import json
import logging
import os
import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

lambda_client = boto3.client('lambda')
mcp_server_arn = os.environ.get('MCP_SERVER_ARN')
crud_handler_arn = os.environ.get('CRUD_HANDLER_ARN')


def lambda_handler(event, context):
    """Route API Gateway requests to appropriate Lambda functions."""
    try:
        path = event.get('path', '')
        method = event.get('httpMethod', '')
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
        path_params = event.get('pathParameters') or {}
        
        logger.info(f"Request: {method} {path}")
        
        if path == '/mcp' and method == 'POST':
            return handle_mcp_request(body)
        elif path == '/mcp/sse':
            return handle_mcp_sse(event)
        elif path == '/search_documents' and method == 'POST':
            return handle_search_documents(body)
        elif path == '/events' and method == 'POST':
            return handle_create_event(body)
        elif path == '/events' and method == 'GET':
            return handle_list_events()
        elif path.startswith('/events/') and method == 'GET':
            return handle_read_event(path_params.get('eventId'))
        elif path.startswith('/events/') and method == 'PUT':
            return handle_update_event(path_params.get('eventId'), body)
        elif path.startswith('/events/') and method == 'DELETE':
            return handle_delete_event(path_params.get('eventId'))
        else:
            return {'statusCode': 404, 'body': json.dumps({'error': 'Endpoint not found'})}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


def handle_search_documents(body):
    payload = {'action': 'execute_tool', 'tool_name': 'search_documents', 'parameters': body}
    response = lambda_client.invoke(FunctionName=mcp_server_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    result = json.loads(response['Payload'].read())
    return {'statusCode': 200, 'body': json.dumps(result)}


def handle_create_event(body):
    payload = {'operation': 'create', 'data': body}
    response = lambda_client.invoke(FunctionName=crud_handler_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    return json.loads(response['Payload'].read())


def handle_list_events():
    payload = {'operation': 'list'}
    response = lambda_client.invoke(FunctionName=crud_handler_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    return json.loads(response['Payload'].read())


def handle_read_event(event_id):
    payload = {'operation': 'read', 'record_id': event_id}
    response = lambda_client.invoke(FunctionName=crud_handler_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    return json.loads(response['Payload'].read())


def handle_update_event(event_id, body):
    payload = {'operation': 'update', 'record_id': event_id, 'data': body}
    response = lambda_client.invoke(FunctionName=crud_handler_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    return json.loads(response['Payload'].read())


def handle_delete_event(event_id):
    payload = {'operation': 'delete', 'record_id': event_id}
    response = lambda_client.invoke(FunctionName=crud_handler_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    return json.loads(response['Payload'].read())


def handle_mcp_request(body):
    """Unified MCP endpoint - handles all tool requests."""
    tool_name = body.get('tool_name')
    parameters = body.get('parameters', {})
    
    if not tool_name:
        return {'statusCode': 400, 'body': json.dumps({'error': 'tool_name required'})}
    
    payload = {'action': 'execute_tool', 'tool_name': tool_name, 'parameters': parameters}
    response = lambda_client.invoke(FunctionName=mcp_server_arn, InvocationType='RequestResponse', Payload=json.dumps(payload))
    result = json.loads(response['Payload'].read())
    
    if result.get('statusCode') == 200:
        return {'statusCode': 200, 'body': json.dumps(result.get('result', {}))}
    else:
        return {'statusCode': 500, 'body': json.dumps({'error': result.get('message', 'Tool execution failed')})}


def handle_mcp_sse(event):
    """Forward MCP SSE requests to MCP server Lambda."""
    response = lambda_client.invoke(FunctionName=mcp_server_arn, InvocationType='RequestResponse', Payload=json.dumps(event))
    return json.loads(response['Payload'].read())
