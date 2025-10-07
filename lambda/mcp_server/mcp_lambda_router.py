"""Route MCP tool calls to appropriate Lambda functions."""
import boto3
import json
import os

lambda_client = boto3.client('lambda')

async def invoke_crud_lambda(operation, parameters):
    """Invoke CRUD Lambda with operation type."""
    crud_lambda_arn = os.environ.get('CRUD_LAMBDA_ARN')
    
    payload = {
        'operation': operation,
        **parameters
    }
    
    response = lambda_client.invoke(
        FunctionName=crud_lambda_arn,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    result = json.loads(response['Payload'].read())
    return json.loads(result.get('body', '{}'))
