"""
Lambda function to delete files from S3 storage.
"""

import json
import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    Delete file from S3 storage.
    
    Expected input:
    {
        "filename": "test.txt"
    }
    """
    try:
        # Parse input
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event
            
        filename = body.get('filename')
        if not filename:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,Authorization'
                },
                'body': json.dumps({'error': 'filename is required'})
            }
        
        documents_bucket = os.environ['DOCUMENTS_BUCKET']
        processed_bucket = os.environ['PROCESSED_BUCKET']
        
        # Delete from documents bucket (uploads folder)
        upload_key = filename if filename.startswith('uploads/') else f"uploads/{filename}"
        try:
            s3_client.delete_object(Bucket=documents_bucket, Key=upload_key)
            logger.info(f"Deleted {upload_key} from {documents_bucket}")
        except Exception as e:
            logger.warning(f"Could not delete {upload_key}: {str(e)}")
        
        # Delete processed chunks (find by filename pattern)
        try:
            # List all objects in processed bucket that match the filename
            response = s3_client.list_objects_v2(
                Bucket=processed_bucket,
                Prefix=f"chunks/"
            )
            
            deleted_chunks = 0
            if 'Contents' in response:
                for obj in response['Contents']:
                    if filename.replace('.', '_') in obj['Key']:
                        s3_client.delete_object(Bucket=processed_bucket, Key=obj['Key'])
                        deleted_chunks += 1
            
            # Delete metadata
            metadata_response = s3_client.list_objects_v2(
                Bucket=processed_bucket,
                Prefix=f"metadata/"
            )
            
            deleted_metadata = 0
            if 'Contents' in metadata_response:
                for obj in metadata_response['Contents']:
                    if filename.replace('.', '_') in obj['Key']:
                        s3_client.delete_object(Bucket=processed_bucket, Key=obj['Key'])
                        deleted_metadata += 1
            
            logger.info(f"Deleted {deleted_chunks} chunks and {deleted_metadata} metadata files")
            
        except Exception as e:
            logger.error(f"Error deleting processed files: {str(e)}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'DELETE,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization'
            },
            'body': json.dumps({
                'message': f'Successfully deleted {filename}',
                'filename': filename
            })
        }
        
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'DELETE,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization'
            },
            'body': json.dumps({'error': str(e)})
        }