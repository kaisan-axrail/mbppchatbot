"""Vector-based RAG handler using embedded S3 documents."""
import boto3
import json
import numpy as np
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def embed_query(query: str) -> List[float]:
    """Generate embedding for query."""
    body = json.dumps({
        "texts": [query[:2048]],
        "input_type": "search_query",
        "embedding_types": ["float"]
    })
    
    response = bedrock.invoke_model(
        modelId='cohere.embed-english-v3',
        body=body
    )
    
    result = json.loads(response['body'].read())
    return result['embeddings']['float'][0]

def search_embedded_documents(query: str, limit: int = 5) -> List[Dict]:
    """Search embedded documents in S3."""
    bucket = os.environ.get('PROCESSED_BUCKET', '')
    if not bucket:
        logger.warning("PROCESSED_BUCKET not set")
        return []
    
    try:
        # Embed query
        query_embedding = embed_query(query)
        
        # List chunks
        response = s3.list_objects_v2(Bucket=bucket, Prefix='chunks/')
        
        results = []
        for obj in response.get('Contents', [])[:100]:  # Limit to 100 chunks
            try:
                chunk_obj = s3.get_object(Bucket=bucket, Key=obj['Key'])
                chunk_data = json.loads(chunk_obj['Body'].read())
                
                similarity = cosine_similarity(query_embedding, chunk_data['embedding'])
                
                results.append({
                    'id': chunk_data['chunk_id'],
                    'content': chunk_data['content'],
                    'source': chunk_data.get('document_id', 'unknown'),
                    'score': similarity
                })
            except Exception as e:
                logger.debug(f"Skip chunk {obj['Key']}: {e}")
                continue
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []
