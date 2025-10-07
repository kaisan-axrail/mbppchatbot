"""CRUD operations Lambda handler for DynamoDB events table."""
import json
import logging
import os
import boto3
from datetime import datetime
import uuid

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    """Handle CRUD operations for events table."""
    try:
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event
        operation = body.get('operation')
        table_name = os.environ.get('EVENTS_TABLE', 'chatbot-events')
        
        if operation == 'create':
            return create_record(table_name, body.get('data', {}))
        elif operation == 'read':
            return read_record(table_name, body.get('record_id'))
        elif operation == 'update':
            return update_record(table_name, body.get('record_id'), body.get('data', {}))
        elif operation == 'delete':
            return delete_record(table_name, body.get('record_id'))
        elif operation == 'list':
            return list_records(table_name)
        else:
            return {'statusCode': 400, 'body': json.dumps({'error': f'Unknown operation: {operation}'})}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}

def create_record(table_name, data):
    table = dynamodb.Table(table_name)
    if 'eventId' not in data:
        data['eventId'] = str(uuid.uuid4())
    data['created_at'] = datetime.now().isoformat()
    table.put_item(Item=data)
    return {'statusCode': 200, 'body': json.dumps({'success': True, 'record_id': data['eventId'], 'data': data})}

def read_record(table_name, record_id):
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={'eventId': record_id})
    if 'Item' not in response:
        return {'statusCode': 404, 'body': json.dumps({'error': f'Record {record_id} not found'})}
    return {'statusCode': 200, 'body': json.dumps({'success': True, 'data': response['Item']})}

def update_record(table_name, record_id, data):
    table = dynamodb.Table(table_name)
    data['updated_at'] = datetime.now().isoformat()
    update_expression = "SET "
    expression_values = {}
    expression_names = {}
    for key, value in data.items():
        if key != 'eventId':
            attr_name = f"#{key}"
            attr_value = f":{key}"
            update_expression += f"{attr_name} = {attr_value}, "
            expression_names[attr_name] = key
            expression_values[attr_value] = value
    update_expression = update_expression.rstrip(', ')
    response = table.update_item(Key={'eventId': record_id}, UpdateExpression=update_expression, ExpressionAttributeNames=expression_names, ExpressionAttributeValues=expression_values, ReturnValues="ALL_NEW")
    return {'statusCode': 200, 'body': json.dumps({'success': True, 'data': response['Attributes']})}

def delete_record(table_name, record_id):
    table = dynamodb.Table(table_name)
    response = table.delete_item(Key={'eventId': record_id}, ReturnValues="ALL_OLD")
    if 'Attributes' not in response:
        return {'statusCode': 404, 'body': json.dumps({'error': f'Record {record_id} not found'})}
    return {'statusCode': 200, 'body': json.dumps({'success': True, 'message': f'Record {record_id} deleted successfully'})}

def list_records(table_name):
    table = dynamodb.Table(table_name)
    response = table.scan()
    items = response.get('Items', [])
    return {'statusCode': 200, 'body': json.dumps({'success': True, 'data': items, 'count': len(items)})}
