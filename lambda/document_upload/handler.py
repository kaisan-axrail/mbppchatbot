"""
Document upload handler Lambda function.
Generates presigned URLs for secure document uploads to S3.
"""

import json
import logging
import os
import boto3
import uuid
from typing import Dict, Any, List
from datetime import datetime
import mimetypes

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
s3_client = boto3.client('s3')


class DocumentUploadError(Exception):
    """Custom exception for document upload errors."""
    pass


def lambda_handler(event, context):
    """
    Lambda handler for document upload operations.
    
    Args:
        event: API Gateway or WebSocket event
        context: Lambda context
        
    Returns:
        Upload response with presigned URLs or error
    """
    try:
        logger.info(f"Processing upload request: {json.dumps(event)}")
        
        # Parse request based on event source
        if 'httpMethod' in event:
            # API Gateway REST request
            return handle_rest_request(event, context)
        elif 'requestContext' in event and 'routeKey' in event['requestContext']:
            # API Gateway WebSocket request
            return handle_websocket_request(event, context)
        else:
            # Direct Lambda invocation
            return handle_direct_request(event, context)
            
    except Exception as e:
        logger.error(f"Upload handler error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'error': 'Upload request failed',
                'message': str(e)
            })
        }


def handle_rest_request(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle REST API request for document upload."""
    try:
        method = event.get('httpMethod', 'POST')
        
        if method == 'POST':
            # Generate presigned URL for upload
            body = json.loads(event.get('body', '{}'))
            return generate_upload_url(body)
        
        elif method == 'GET':
            # List uploaded documents
            return list_documents()
        
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        logger.error(f"REST request error: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'error': 'Invalid request',
                'message': str(e)
            })
        }


def handle_websocket_request(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle WebSocket request for document upload."""
    try:
        body = json.loads(event.get('body', '{}'))
        action = body.get('action', 'upload')
        
        if action == 'upload':
            return generate_upload_url(body)
        elif action == 'list':
            return list_documents()
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid action',
                    'message': f'Unknown action: {action}'
                })
            }
            
    except Exception as e:
        logger.error(f"WebSocket request error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid WebSocket request',
                'message': str(e)
            })
        }


def handle_direct_request(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle direct Lambda invocation."""
    try:
        action = event.get('action', 'upload')
        
        if action == 'upload':
            return generate_upload_url(event)
        elif action == 'list':
            return list_documents()
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Invalid action',
                    'message': f'Unknown action: {action}'
                })
            }
            
    except Exception as e:
        logger.error(f"Direct request error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Invalid direct request',
                'message': str(e)
            })
        }


def generate_upload_url(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate presigned URL for document upload.
    
    Args:
        request_data: Upload request parameters
        
    Returns:
        Response with presigned URL and upload details
    """
    try:
        # Extract request parameters
        filename = request_data.get('filename')
        file_type = request_data.get('file_type', '').lower()
        file_size = request_data.get('file_size', 0)
        
        # Validate required parameters
        if not filename:
            raise DocumentUploadError("Filename is required")
        
        # Validate file type
        allowed_extensions = os.environ.get('ALLOWED_EXTENSIONS', 'pdf,txt,docx,md').split(',')
        if not file_type:
            file_type = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if file_type not in allowed_extensions:
            raise DocumentUploadError(
                f"File type '{file_type}' not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size
        max_file_size = int(os.environ.get('MAX_FILE_SIZE', '50000000'))  # 50MB default
        if file_size > max_file_size:
            raise DocumentUploadError(
                f"File size {file_size} exceeds maximum allowed size {max_file_size} bytes"
            )
        
        # Generate unique file key
        upload_id = str(uuid.uuid4())
        safe_filename = sanitize_filename(filename)
        upload_prefix = os.environ.get('UPLOAD_PREFIX', 'uploads/')
        object_key = f"{upload_prefix}{upload_id}_{safe_filename}"
        
        # Get S3 bucket
        bucket_name = os.environ.get('DOCUMENTS_BUCKET')
        if not bucket_name:
            raise DocumentUploadError("Documents bucket not configured")
        
        # Determine content type
        content_type = get_content_type(file_type)
        
        # Generate presigned URL for upload
        expiry_seconds = int(os.environ.get('PRESIGNED_URL_EXPIRY', '3600'))  # 1 hour default
        
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key,
                'ContentType': content_type,
                'Metadata': {
                    'original-filename': filename,
                    'upload-id': upload_id,
                    'file-type': file_type,
                    'upload-timestamp': datetime.utcnow().isoformat()
                }
            },
            ExpiresIn=expiry_seconds
        )
        
        # Generate presigned URL for download (for verification)
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiry_seconds
        )
        
        response_data = {
            'success': True,
            'upload_id': upload_id,
            'upload_url': presigned_url,
            'download_url': download_url,
            'object_key': object_key,
            'bucket_name': bucket_name,
            'expires_in': expiry_seconds,
            'content_type': content_type,
            'upload_instructions': {
                'method': 'PUT',
                'headers': {
                    'Content-Type': content_type
                },
                'max_file_size': max_file_size,
                'allowed_types': allowed_extensions
            }
        }
        
        logger.info(f"Generated upload URL for {filename} (ID: {upload_id})")
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps(response_data)
        }
        
    except DocumentUploadError as e:
        logger.warning(f"Upload validation error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Upload validation failed',
                'message': str(e)
            })
        }
    except Exception as e:
        logger.error(f"Upload URL generation error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Upload URL generation failed',
                'message': str(e)
            })
        }


def list_documents() -> Dict[str, Any]:
    """
    List uploaded documents in the S3 bucket.
    
    Returns:
        Response with list of documents
    """
    try:
        bucket_name = os.environ.get('DOCUMENTS_BUCKET')
        if not bucket_name:
            raise DocumentUploadError("Documents bucket not configured")
        
        upload_prefix = os.environ.get('UPLOAD_PREFIX', 'uploads/')
        
        # List objects in the uploads prefix
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=upload_prefix,
            MaxKeys=100  # Limit to 100 documents
        )
        
        documents = []
        for obj in response.get('Contents', []):
            # Get object metadata
            try:
                head_response = s3_client.head_object(
                    Bucket=bucket_name,
                    Key=obj['Key']
                )
                
                metadata = head_response.get('Metadata', {})
                
                doc_info = {
                    'key': obj['Key'],
                    'filename': metadata.get('original-filename', obj['Key'].split('/')[-1]),
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'upload_id': metadata.get('upload-id'),
                    'file_type': metadata.get('file-type'),
                    'upload_timestamp': metadata.get('upload-timestamp')
                }
                
                documents.append(doc_info)
                
            except Exception as e:
                logger.warning(f"Error getting metadata for {obj['Key']}: {str(e)}")
                # Add basic info without metadata
                documents.append({
                    'key': obj['Key'],
                    'filename': obj['Key'].split('/')[-1],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                })
        
        # Sort by last modified (newest first)
        documents.sort(key=lambda x: x['last_modified'], reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'success': True,
                'documents': documents,
                'total_count': len(documents),
                'bucket_name': bucket_name
            })
        }
        
    except Exception as e:
        logger.error(f"Document listing error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Document listing failed',
                'message': str(e)
            })
        }


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe S3 storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    import re
    
    # Keep only alphanumeric, dots, hyphens, and underscores
    safe_filename = re.sub(r'[^a-zA-Z0-9.\-_]', '_', filename)
    
    # Limit length
    if len(safe_filename) > 100:
        name_part = safe_filename[:90]
        extension = safe_filename.split('.')[-1] if '.' in safe_filename else ''
        safe_filename = f"{name_part}.{extension}" if extension else name_part
    
    return safe_filename


def get_content_type(file_type: str) -> str:
    """
    Get MIME content type for file extension.
    
    Args:
        file_type: File extension
        
    Returns:
        MIME content type
    """
    content_types = {
        'pdf': 'application/pdf',
        'txt': 'text/plain',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'md': 'text/markdown'
    }
    
    return content_types.get(file_type.lower(), 'application/octet-stream')


def validate_upload_request(request_data: Dict[str, Any]) -> List[str]:
    """
    Validate upload request parameters.
    
    Args:
        request_data: Request data to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required fields
    if not request_data.get('filename'):
        errors.append("Filename is required")
    
    # Check file size
    file_size = request_data.get('file_size', 0)
    max_size = int(os.environ.get('MAX_FILE_SIZE', '50000000'))
    if file_size > max_size:
        errors.append(f"File size exceeds maximum allowed size of {max_size} bytes")
    
    # Check file type
    filename = request_data.get('filename', '')
    if '.' not in filename:
        errors.append("File must have an extension")
    else:
        file_type = filename.split('.')[-1].lower()
        allowed_types = os.environ.get('ALLOWED_EXTENSIONS', 'pdf,txt,docx,md').split(',')
        if file_type not in allowed_types:
            errors.append(f"File type '{file_type}' not allowed. Allowed: {', '.join(allowed_types)}")
    
    return errors