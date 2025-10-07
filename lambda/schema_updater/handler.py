"""Update OpenAPI schema with API Gateway endpoint."""
import json
import os

def lambda_handler(event, context):
    request_type = event.get('RequestType')
    
    if request_type == 'Delete':
        return {'Status': 'SUCCESS', 'PhysicalResourceId': 'schema-updater'}
    
    api_endpoint = event['ResourceProperties']['ApiEndpoint']
    
    # Just return success - schema will be updated via environment variable in MCP server
    return {'Status': 'SUCCESS', 'PhysicalResourceId': 'schema-updater', 'Data': {'Endpoint': api_endpoint}}
