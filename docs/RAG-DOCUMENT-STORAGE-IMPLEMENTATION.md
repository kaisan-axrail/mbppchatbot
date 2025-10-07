# RAG Document Storage Implementation Guide

## Current Status
The system currently uses mock/placeholder data for RAG document storage. This guide explains how to implement real document storage and retrieval.

## Architecture Options

### Option 1: AWS OpenSearch + S3 (Recommended)

```
Documents → S3 → Lambda Processor → Bedrock Embeddings → OpenSearch Vector Index
                                                      ↓
User Query → Bedrock Embeddings → OpenSearch Vector Search → Relevant Chunks
```

**Components:**
- **S3 Bucket**: Store original documents (PDF, DOCX, TXT)
- **Lambda Function**: Document processing and chunking
- **AWS Bedrock**: Generate embeddings (Titan Text Embeddings)
- **OpenSearch**: Vector search with k-NN capabilities
- **DynamoDB**: Document metadata and chunk references

**Implementation Steps:**

1. **Add S3 Bucket to CDK Stack:**
```python
# In database_stack.py
self.documents_bucket = s3.Bucket(
    self, "DocumentsBucket",
    bucket_name="chatbot-documents",
    versioned=True,
    encryption=s3.BucketEncryption.S3_MANAGED,
    removal_policy=RemovalPolicy.DESTROY
)
```

2. **Add OpenSearch Domain:**
```python
# In database_stack.py
self.opensearch_domain = opensearch.Domain(
    self, "DocumentsSearchDomain",
    version=opensearch.EngineVersion.OPENSEARCH_2_3,
    capacity=opensearch.CapacityConfig(
        data_nodes=1,
        data_node_instance_type="t3.small.search"
    ),
    ebs=opensearch.EbsOptions(
        volume_size=20,
        volume_type=ec2.EbsDeviceVolumeType.GP3
    ),
    zone_awareness=opensearch.ZoneAwarenessConfig(enabled=False),
    removal_policy=RemovalPolicy.DESTROY
)
```

3. **Create Document Processing Lambda:**
```python
# New file: lambda/document_processor/handler.py
import boto3
import json
from typing import List, Dict
import PyPDF2
import docx

def lambda_handler(event, context):
    """Process uploaded documents and create embeddings."""
    
    # 1. Extract text from document
    # 2. Split into chunks
    # 3. Generate embeddings with Bedrock
    # 4. Store in OpenSearch
    # 5. Store metadata in DynamoDB
```

4. **Update MCP Server for Real Vector Search:**
```python
# In mcp_server.py - replace mock implementation
async def _search_documents_opensearch(self, query_embedding: List[float], limit: int, threshold: float):
    """Real OpenSearch vector similarity search."""
    
    opensearch_client = boto3.client('opensearchserverless')
    
    search_body = {
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": limit
                }
            }
        },
        "min_score": threshold
    }
    
    response = opensearch_client.search(
        index="documents",
        body=search_body
    )
    
    return self._format_opensearch_results(response)
```

### Option 2: DynamoDB + Vector Extensions (Simpler)

```
Documents → Lambda Processor → Bedrock Embeddings → DynamoDB with Vector Attributes
                                                  ↓
User Query → Bedrock Embeddings → DynamoDB Scan with Cosine Similarity → Relevant Chunks
```

**Pros:** Simpler setup, no additional services
**Cons:** Less efficient for large document collections

### Option 3: External Vector Database (Pinecone/Weaviate)

```
Documents → Lambda Processor → Bedrock Embeddings → External Vector DB
                                                  ↓
User Query → Bedrock Embeddings → External Vector DB API → Relevant Chunks
```

## Document Upload Workflow

### 1. Document Upload API
```python
# Add to WebSocket API or create REST API
@app.route('/upload-document', methods=['POST'])
def upload_document():
    """Upload document for RAG processing."""
    
    # 1. Validate file type (PDF, DOCX, TXT)
    # 2. Upload to S3
    # 3. Trigger processing Lambda
    # 4. Return upload status
```

### 2. Document Processing Pipeline
```python
def process_document(s3_bucket: str, s3_key: str):
    """Process uploaded document into searchable chunks."""
    
    # 1. Download from S3
    # 2. Extract text based on file type
    # 3. Split into chunks (500-1000 tokens each)
    # 4. Generate embeddings for each chunk
    # 5. Store in vector database
    # 6. Update metadata in DynamoDB
```

### 3. Chunk Storage Schema
```python
# DynamoDB Document Metadata Table
{
    "document_id": "doc_123",
    "filename": "user_manual.pdf", 
    "upload_date": "2024-01-15T10:30:00Z",
    "total_chunks": 25,
    "file_size": 1024000,
    "status": "processed"
}

# Vector Database Chunk Storage
{
    "chunk_id": "doc_123_chunk_1",
    "document_id": "doc_123", 
    "content": "This is the text content of the chunk...",
    "embedding": [0.1, 0.2, -0.3, ...],  # 1536-dimensional vector
    "chunk_index": 1,
    "source_page": 1
}
```

## Implementation Priority

### Phase 1: Basic Document Storage (Quick Win)
1. Add S3 bucket for document storage
2. Create simple document upload endpoint
3. Implement basic text extraction (PDF, TXT)
4. Store document chunks in DynamoDB with mock embeddings

### Phase 2: Real Vector Search
1. Integrate AWS Bedrock for real embeddings
2. Add OpenSearch domain for vector search
3. Implement document processing pipeline
4. Update MCP server with real vector search

### Phase 3: Advanced Features
1. Support for more file types (DOCX, HTML, Markdown)
2. Document versioning and updates
3. Batch document processing
4. Search result ranking and filtering

## Quick Implementation (Phase 1)

To get started quickly, you can:

1. **Add Document Upload to WebSocket API:**
```python
# In websocket_handler - add new message type
if message_type == "upload_document":
    # Handle document upload
    result = await handle_document_upload(message_data)
```

2. **Store Documents in DynamoDB:**
```python
# Simple document storage without vector search
def store_document_chunks(document_id: str, chunks: List[str]):
    """Store document chunks in DynamoDB for basic search."""
    
    for i, chunk in enumerate(chunks):
        item = {
            "chunk_id": f"{document_id}_chunk_{i}",
            "document_id": document_id,
            "content": chunk,
            "chunk_index": i,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store in conversations table or create new documents table
        dynamodb_table.put_item(Item=item)
```

3. **Basic Text Search (Temporary):**
```python
# Replace vector search with text search temporarily
def search_documents_text(query: str, limit: int = 5):
    """Basic text search until vector search is implemented."""
    
    # Use DynamoDB scan with contains filter
    response = dynamodb_table.scan(
        FilterExpression=Attr('content').contains(query.lower()),
        Limit=limit
    )
    
    return format_search_results(response['Items'])
```

## Next Steps

1. **Choose Architecture**: Recommend Option 1 (OpenSearch) for production
2. **Implement Phase 1**: Basic document storage and text search
3. **Add Document Upload UI**: Simple web interface for document uploads
4. **Upgrade to Vector Search**: Implement real embeddings and vector similarity

Would you like me to implement any of these phases?