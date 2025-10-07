"""
URL ingestion Lambda function for knowledge base.
Fetches content from URLs and processes it for RAG.
"""

import json
import logging
import os
import boto3
from typing import Dict, Any
from datetime import datetime
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
bedrock_agent_client = boto3.client('bedrock-agent')

class URLIngestionError(Exception):
    """Custom exception for URL ingestion errors."""
    pass

def lambda_handler(event, context):
    """
    Lambda handler for URL ingestion.
    
    Args:
        event: Contains URL and optional metadata
        context: Lambda context
        
    Returns:
        Processing result
    """
    try:
        logger.info(f"Processing URL ingestion: {json.dumps(event)}")
        
        # Handle OPTIONS request for CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
                },
                'body': ''
            }
        
        # Handle REST API request
        if 'httpMethod' in event:
            body = json.loads(event.get('body', '{}'))
            url = body.get('url')
            metadata = body.get('metadata', {})
        else:
            # Direct Lambda invocation
            url = event.get('url')
            metadata = event.get('metadata', {})
        
        if not url:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
                },
                'body': json.dumps({
                    'error': 'URL is required',
                    'message': 'Please provide a valid URL'
                })
            }
        
        # Process the URL
        result = process_url(url, metadata)
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"URL ingestion error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With'
            },
            'body': json.dumps({
                'error': 'URL ingestion failed',
                'message': str(e)
            })
        }

def process_url(url: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Process URL using AWS Bedrock Knowledge Base web crawler."""
    try:
        start_time = datetime.utcnow()
        
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise URLIngestionError("Invalid URL format")
        
        knowledge_base_id = os.environ.get('KNOWLEDGE_BASE_ID')
        data_source_id = os.environ.get('DATA_SOURCE_ID')
        
        if not knowledge_base_id or not data_source_id:
            logger.warning("Knowledge Base or Data Source ID not configured")
            return store_url_metadata(url, metadata, start_time)
        
        # Update data source with the URL to crawl
        logger.info(f"Adding URL to web crawler: {url}")
        
        try:
            # Create a new data source for this URL
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            ds_name = f"WebCrawler-{url_hash}"
            
            logger.info(f"Creating data source for URL: {url}")
            
            ds_response = bedrock_agent_client.create_data_source(
                knowledgeBaseId=knowledge_base_id,
                name=ds_name,
                description=f"Web crawler for {url}",
                dataSourceConfiguration={
                    'type': 'WEB',
                    'webConfiguration': {
                        'sourceConfiguration': {
                            'urlConfiguration': {
                                'seedUrls': [{'url': url}]
                            }
                        },
                        'crawlerConfiguration': {
                            'crawlerLimits': {
                                'rateLimit': 300
                            },
                            'inclusionFilters': [f"{parsed_url.scheme}://{parsed_url.netloc}/*"],
                            'exclusionFilters': ['*.pdf', '*.doc', '*.docx']
                        }
                    }
                }
            )
            
            created_data_source_id = ds_response['dataSource']['dataSourceId']
            logger.info(f"Created data source: {created_data_source_id}")
            
            # Start ingestion job
            response = bedrock_agent_client.start_ingestion_job(
                knowledgeBaseId=knowledge_base_id,
                dataSourceId=created_data_source_id,
                description=f"Ingestion job for URL: {url}"
            )
            
            ingestion_job_id = response['ingestionJob']['ingestionJobId']
            
        except Exception as e:
            logger.error(f"Error starting ingestion job: {str(e)}")
            # Fallback to storing metadata
            return store_url_metadata(url, metadata, start_time)
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        result = {
            'success': True,
            'ingestion_job_id': ingestion_job_id,
            'source_url': url,
            'knowledge_base_id': knowledge_base_id,
            'data_source_id': created_data_source_id,
            'processing_time_seconds': processing_time,
            'status': 'ingestion_started',
            'message': f'URL {url} added to knowledge base for crawling',
            'metadata': metadata
        }
        
        logger.info(f"Started Knowledge Base ingestion for {url} (Job ID: {ingestion_job_id})")
        return result
        
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'url': url
        }

def store_url_metadata(url: str, metadata: Dict[str, Any], start_time: datetime) -> Dict[str, Any]:
    """Store URL metadata when Knowledge Base is not configured."""
    try:
        import hashlib
        
        # Generate document ID
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        document_id = f"url_{url_hash}"
        
        parsed_url = urlparse(url)
        doc_metadata = {
            'document_id': document_id,
            'source_url': url,
            'source_type': 'url',
            'domain': parsed_url.netloc,
            'ingestion_date': start_time.isoformat(),
            'status': 'pending_kb_setup',
            **metadata
        }
        
        # Store metadata in S3 for later processing
        kb_bucket = os.environ.get('KNOWLEDGE_BASE_BUCKET')
        if kb_bucket:
            s3_client = boto3.client('s3')
            metadata_key = f"pending_urls/{document_id}.json"
            
            s3_client.put_object(
                Bucket=kb_bucket,
                Key=metadata_key,
                Body=json.dumps(doc_metadata, indent=2),
                ContentType='application/json'
            )
        
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        return {
            'success': True,
            'document_id': document_id,
            'source_url': url,
            'status': 'metadata_stored',
            'processing_time_seconds': processing_time,
            'message': 'URL metadata stored. Knowledge Base ingestion will be available once KB is configured.',
            'metadata': doc_metadata
        }
        
    except Exception as e:
        logger.error(f"Error storing URL metadata: {str(e)}")
        raise URLIngestionError(f"Failed to store URL metadata: {str(e)}")

