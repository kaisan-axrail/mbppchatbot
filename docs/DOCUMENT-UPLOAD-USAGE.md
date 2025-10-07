# Document Upload and RAG Usage Guide

## Overview
The storage stack provides S3-based document storage for RAG (Retrieval-Augmented Generation) functionality with automatic document processing.

## Architecture

```
Document Upload → S3 Bucket → Lambda Processor → Bedrock Embeddings → Processed Storage
                                                                    ↓
User Query → MCP Server → Vector Search → Relevant Chunks → RAG Response
```

## Components

### 1. S3 Buckets
- **Documents Bucket**: `chatbot-documents-{account}-{region}`
  - Stores original uploaded documents
  - Triggers processing on upload
  - Supports PDF, TXT, DOCX, MD files

- **Processed Documents Bucket**: `chatbot-processed-docs-{account}-{region}`
  - Stores processed document chunks with embeddings
  - Organized by document ID
  - Includes metadata and search indices

### 2. Lambda Functions
- **Document Processor**: Automatically processes uploaded documents
  - Extracts text content
  - Splits into searchable chunks
  - Generates embeddings using AWS Bedrock
  - Stores processed data

- **Document Upload Handler**: Manages upload requests
  - Generates presigned URLs for secure uploads
  - Validates file types and sizes
  - Lists uploaded documents

## Usage Examples

### 1. Upload Document via WebSocket

```javascript
// WebSocket message to request upload URL
const uploadRequest = {
  action: "upload_document",
  filename: "user_manual.pdf",
  file_type: "pdf",
  file_size: 1024000
};

// Send via WebSocket
websocket.send(JSON.stringify(uploadRequest));

// Response will include presigned URL
{
  "success": true,
  "upload_id": "uuid-here",
  "upload_url": "https://s3-presigned-url...",
  "expires_in": 3600
}
```

### 2. Upload Document via REST API

```bash
# Request upload URL
curl -X POST https://api-endpoint/upload \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "document.pdf",
    "file_type": "pdf", 
    "file_size": 1024000
  }'

# Upload file using presigned URL
curl -X PUT "presigned-url-here" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

### 3. Search Documents via MCP

```python
# MCP search request
search_request = {
  "tool": "search_documents",
  "parameters": {
    "query": "user authentication process",
    "limit": 5,
    "threshold": 0.7
  }
}

# Response with relevant chunks
{
  "success": true,
  "result": [
    {
      "id": "doc_abc123_chunk_1",
      "content": "Authentication process involves...",
      "source": "user_manual.pdf",
      "score": 0.85
    }
  ]
}
```

## File Processing Pipeline

### 1. Upload Trigger
```
User uploads file → S3 Event → Document Processor Lambda
```

### 2. Text Extraction
- **PDF**: Uses PyPDF2 for text extraction
- **DOCX**: Uses python-docx library
- **TXT/MD**: Direct text reading

### 3. Chunking Strategy
- **Chunk Size**: 1000 words (configurable)
- **Overlap**: 200 words (configurable)
- **Method**: Word-based splitting with overlap

### 4. Embedding Generation
- **Model**: Amazon Titan Text Embeddings v1
- **Dimensions**: 1536
- **Fallback**: Mock embeddings for development

### 5. Storage Structure
```
processed-bucket/
├── metadata/
│   └── {document_id}.json
└── chunks/
    └── {document_id}/
        ├── {document_id}_chunk_0.json
        ├── {document_id}_chunk_1.json
        └── ...
```

## Configuration

### Environment Variables

#### Document Processor
- `DOCUMENTS_BUCKET`: Source S3 bucket
- `PROCESSED_BUCKET`: Processed documents bucket
- `CHUNK_SIZE`: Text chunk size (default: 1000)
- `CHUNK_OVERLAP`: Chunk overlap (default: 200)
- `EMBEDDING_MODEL`: Bedrock model ID

#### Document Upload Handler
- `DOCUMENTS_BUCKET`: Upload destination bucket
- `MAX_FILE_SIZE`: Maximum file size (default: 50MB)
- `ALLOWED_EXTENSIONS`: Allowed file types
- `PRESIGNED_URL_EXPIRY`: URL expiry time (default: 1 hour)

## Monitoring and Troubleshooting

### CloudWatch Logs
- Document processing logs: `/aws/lambda/ChatbotStorageStack-DocumentProcessor-*`
- Upload handler logs: `/aws/lambda/ChatbotStorageStack-DocumentUploadHandler-*`

### Common Issues

1. **Upload Fails**
   - Check file size limits
   - Verify file type is allowed
   - Ensure presigned URL hasn't expired

2. **Processing Fails**
   - Check CloudWatch logs for errors
   - Verify Bedrock permissions
   - Check document format compatibility

3. **Search Returns No Results**
   - Verify documents are processed
   - Check embedding generation
   - Adjust similarity threshold

## Integration with WebSocket Chatbot

### Add Document Upload to WebSocket Handler

```python
# In websocket_handler/handler.py
async def handle_message(connection_id, message):
    message_type = message.get('type')
    
    if message_type == 'upload_document':
        # Call document upload handler
        upload_response = await invoke_upload_handler(message)
        return upload_response
    
    elif message_type == 'search_documents':
        # Use MCP server for document search
        search_response = await mcp_client.search_documents(
            query=message.get('query'),
            limit=message.get('limit', 5)
        )
        return search_response
```

### Update MCP Server for Real Storage

The MCP server needs to be updated to read from the processed documents bucket instead of using mock data. This involves:

1. Reading chunk data from S3
2. Performing vector similarity search
3. Returning real document results

## Next Steps

1. **Deploy Storage Stack**: `cdk deploy ChatbotStorageStack`
2. **Test Document Upload**: Use the upload handler to upload test documents
3. **Verify Processing**: Check processed documents bucket for chunks
4. **Update MCP Server**: Integrate with real document storage
5. **Test End-to-End**: Upload → Process → Search → RAG Response

## Security Considerations

- Presigned URLs have limited expiry time
- S3 buckets block public access
- Lambda functions have minimal required permissions
- Document content is encrypted at rest in S3
- File type validation prevents malicious uploads