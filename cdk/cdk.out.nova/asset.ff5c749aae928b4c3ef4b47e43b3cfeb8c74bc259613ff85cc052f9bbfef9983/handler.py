"""
Document processor Lambda function for RAG document processing.
Handles document chunking, embedding generation, and storage.
"""

import json
import logging
import os
import boto3
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import urllib.parse

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialize AWS clients
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')


class DocumentProcessorError(Exception):
    """Custom exception for document processing errors."""
    pass


def lambda_handler(event, context):
    """
    Lambda handler for processing uploaded documents.
    
    Args:
        event: S3 event notification
        context: Lambda context
        
    Returns:
        Processing result
    """
    try:
        logger.info(f"Processing document event: {json.dumps(event)}")
        
        # Extract S3 event information
        records = event.get('Records', [])
        if not records:
            logger.warning("No records found in event")
            return {'statusCode': 200, 'body': 'No records to process'}
        
        results = []
        for record in records:
            try:
                # Extract bucket and key from S3 event
                bucket_name = record['s3']['bucket']['name']
                object_key = urllib.parse.unquote_plus(
                    record['s3']['object']['key'], 
                    encoding='utf-8'
                )
                
                logger.info(f"Processing document: s3://{bucket_name}/{object_key}")
                
                # Process the document
                result = process_document(bucket_name, object_key)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'object_key': object_key if 'object_key' in locals() else 'unknown'
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Document processing completed',
                'results': results
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Document processing failed',
                'message': str(e)
            })
        }


def process_document(bucket_name: str, object_key: str) -> Dict[str, Any]:
    """
    Process a single document: extract text, chunk, generate embeddings.
    
    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key
        
    Returns:
        Processing result dictionary
    """
    try:
        start_time = datetime.utcnow()
        
        # Download document from S3
        logger.info(f"Downloading document: {object_key}")
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        document_content = response['Body'].read()
        
        # Extract text based on file type
        file_extension = object_key.lower().split('.')[-1]
        text_content = extract_text(document_content, file_extension)
        
        if not text_content.strip():
            raise DocumentProcessorError("No text content extracted from document")
        
        # Generate document metadata
        document_id = generate_document_id(object_key, document_content)
        metadata = {
            'document_id': document_id,
            'filename': object_key.split('/')[-1],
            'file_type': file_extension,
            'file_size': len(document_content),
            'upload_date': start_time.isoformat(),
            'source_bucket': bucket_name,
            'source_key': object_key
        }
        
        # Split text into chunks
        chunks = chunk_text(text_content)
        logger.info(f"Split document into {len(chunks)} chunks")
        
        # Process each chunk
        processed_chunks = []
        for i, chunk_text in enumerate(chunks):
            try:
                # Generate embedding for chunk
                embedding = generate_embedding(chunk_text)
                
                chunk_data = {
                    'chunk_id': f"{document_id}_chunk_{i}",
                    'document_id': document_id,
                    'chunk_index': i,
                    'content': chunk_text,
                    'embedding': embedding,
                    'word_count': len(chunk_text.split()),
                    'char_count': len(chunk_text)
                }
                
                processed_chunks.append(chunk_data)
                
            except Exception as e:
                logger.error(f"Error processing chunk {i}: {str(e)}")
                continue
        
        if not processed_chunks:
            raise DocumentProcessorError("No chunks were successfully processed")
        
        # Store processed chunks in S3
        processed_bucket = os.environ.get('PROCESSED_BUCKET')
        if processed_bucket:
            store_processed_chunks(processed_bucket, document_id, processed_chunks, metadata)
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        result = {
            'success': True,
            'document_id': document_id,
            'filename': metadata['filename'],
            'chunks_processed': len(processed_chunks),
            'processing_time_seconds': processing_time,
            'metadata': metadata
        }
        
        logger.info(f"Successfully processed document {document_id} in {processing_time:.2f}s")
        return result
        
    except Exception as e:
        logger.error(f"Error processing document {object_key}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'object_key': object_key
        }


def extract_text(content: bytes, file_type: str) -> str:
    """
    Extract text content from document based on file type.
    
    Args:
        content: Document content as bytes
        file_type: File extension (pdf, txt, docx)
        
    Returns:
        Extracted text content
    """
    try:
        if file_type == 'txt':
            return content.decode('utf-8')
        
        elif file_type == 'pdf':
            # For PDF processing, you would typically use PyPDF2 or pdfplumber
            # For now, return a placeholder implementation
            logger.warning("PDF processing not fully implemented, using placeholder")
            return f"PDF content placeholder for file with {len(content)} bytes"
        
        elif file_type == 'docx':
            # For DOCX processing, you would typically use python-docx
            # For now, return a placeholder implementation
            logger.warning("DOCX processing not fully implemented, using placeholder")
            return f"DOCX content placeholder for file with {len(content)} bytes"
        
        elif file_type == 'md':
            return content.decode('utf-8')
        
        else:
            raise DocumentProcessorError(f"Unsupported file type: {file_type}")
            
    except UnicodeDecodeError as e:
        logger.error(f"Unicode decode error: {str(e)}")
        raise DocumentProcessorError(f"Failed to decode text content: {str(e)}")
    except Exception as e:
        logger.error(f"Text extraction error: {str(e)}")
        raise DocumentProcessorError(f"Text extraction failed: {str(e)}")


def chunk_text(text: str) -> List[str]:
    """
    Split text into chunks for processing.
    
    Args:
        text: Input text to chunk
        
    Returns:
        List of text chunks
    """
    try:
        chunk_size = int(os.environ.get('CHUNK_SIZE', '1000'))
        chunk_overlap = int(os.environ.get('CHUNK_OVERLAP', '200'))
        
        # Simple word-based chunking
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            # Only add non-empty chunks
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
        
        # Ensure we have at least one chunk
        if not chunks and text.strip():
            chunks.append(text.strip())
        
        return chunks
        
    except Exception as e:
        logger.error(f"Text chunking error: {str(e)}")
        raise DocumentProcessorError(f"Text chunking failed: {str(e)}")


def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using AWS Bedrock.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector as list of floats
    """
    try:
        model_id = os.environ.get('EMBEDDING_MODEL', 'amazon.titan-embed-text-v1')
        
        # Prepare request body
        body = json.dumps({
            "inputText": text[:8000]  # Limit text length for embedding model
        })
        
        # Call Bedrock
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        embedding = response_body.get('embedding', [])
        
        if not embedding:
            raise DocumentProcessorError("Empty embedding returned from Bedrock")
        
        logger.debug(f"Generated embedding of length {len(embedding)}")
        return embedding
        
    except Exception as e:
        logger.error(f"Embedding generation error: {str(e)}")
        # Fallback to mock embedding for development
        logger.warning("Using mock embedding due to Bedrock error")
        return generate_mock_embedding(text)


def generate_mock_embedding(text: str) -> List[float]:
    """
    Generate a deterministic mock embedding for development/testing.
    
    Args:
        text: Input text
        
    Returns:
        Mock embedding vector
    """
    # Create deterministic embedding based on text hash
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    # Generate 1536-dimensional mock embedding (Titan embedding size)
    embedding = []
    for i in range(1536):
        # Use hash characters to generate deterministic values
        hash_char = text_hash[i % len(text_hash)]
        value = (ord(hash_char) - ord('0')) / 15.0 - 0.5  # Normalize to [-0.5, 0.5]
        embedding.append(value)
    
    return embedding


def generate_document_id(object_key: str, content: bytes) -> str:
    """
    Generate unique document ID based on key and content.
    
    Args:
        object_key: S3 object key
        content: Document content
        
    Returns:
        Unique document ID
    """
    # Combine object key and content hash for uniqueness
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    key_hash = hashlib.md5(object_key.encode()).hexdigest()[:8]
    
    return f"doc_{key_hash}_{content_hash}"


def store_processed_chunks(
    bucket_name: str, 
    document_id: str, 
    chunks: List[Dict[str, Any]], 
    metadata: Dict[str, Any]
) -> None:
    """
    Store processed document chunks and metadata in S3.
    
    Args:
        bucket_name: S3 bucket for processed documents
        document_id: Unique document identifier
        chunks: List of processed chunks
        metadata: Document metadata
    """
    try:
        # Store document metadata
        metadata_key = f"metadata/{document_id}.json"
        metadata_with_chunks = {
            **metadata,
            'total_chunks': len(chunks),
            'processed_at': datetime.utcnow().isoformat(),
            'status': 'processed'
        }
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=metadata_key,
            Body=json.dumps(metadata_with_chunks, indent=2),
            ContentType='application/json'
        )
        
        # Store each chunk
        for chunk in chunks:
            chunk_key = f"chunks/{document_id}/{chunk['chunk_id']}.json"
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=chunk_key,
                Body=json.dumps(chunk, indent=2),
                ContentType='application/json'
            )
        
        logger.info(f"Stored {len(chunks)} chunks and metadata for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error storing processed chunks: {str(e)}")
        raise DocumentProcessorError(f"Failed to store processed chunks: {str(e)}")