"""Vector similarity search for embedded documents in S3."""
import boto3
import json
import math
from typing import List, Dict

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors without numpy."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

def embed_query(query: str) -> List[float]:
    """Generate embedding for search query."""
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

def search_embedded_documents(query: str, bucket: str, limit: int = 5) -> List[Dict]:
    """Search embedded documents using vector similarity."""
    
    # Embed the query
    query_embedding = embed_query(query)
    
    # List all chunk files
    response = s3.list_objects_v2(Bucket=bucket, Prefix='chunks/')
    
    results = []
    for obj in response.get('Contents', []):
        try:
            # Load chunk with embedding
            chunk_obj = s3.get_object(Bucket=bucket, Key=obj['Key'])
            chunk_data = json.loads(chunk_obj['Body'].read())
            
            # Calculate similarity
            similarity = cosine_similarity(query_embedding, chunk_data['embedding'])
            
            results.append({
                'id': chunk_data['chunk_id'],
                'content': chunk_data['content'],
                'source': chunk_data['document_id'],
                'score': float(similarity)
            })
        except:
            continue
    
    # Sort by similarity and return top results
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]
