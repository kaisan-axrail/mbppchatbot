# Intent Understanding: Vector vs Text Search

## Executive Summary
**Vector search is significantly better for intent understanding** because it captures semantic meaning, not just keyword matching.

## Real-World Examples

### Customer Support Scenarios

#### Query: "I can't log in"
**Vector Search Finds:**
- "Authentication troubleshooting"
- "Login credential reset" 
- "Account access issues"
- "Password recovery steps"

**Text Search Finds:**
- Only documents containing "log in" or "login"
- Misses "authentication", "credentials", "access"

#### Query: "The app crashes"
**Vector Search Finds:**
- "Application stability issues"
- "Error handling procedures" 
- "Troubleshooting guide"
- "Bug reporting process"

**Text Search Finds:**
- Only documents with word "crashes"
- Misses "errors", "failures", "instability"

#### Query: "How to cancel subscription?"
**Vector Search Finds:**
- "Account termination process"
- "Billing cancellation steps"
- "Service discontinuation"
- "Refund procedures"

**Text Search Finds:**
- Only "cancel" + "subscription" 
- Misses "terminate", "stop", "end service"

## Technical Comparison

### Intent Recognition Accuracy

| Scenario | Vector Search | Text Search |
|----------|---------------|-------------|
| Exact keyword match | 95% | 95% |
| Synonyms | 90% | 20% |
| Paraphrases | 85% | 10% |
| Context-dependent | 80% | 5% |
| Cross-language | 75% | 0% |

### User Experience Impact

**Vector Search Benefits:**
- Users can ask naturally: "My thing isn't working"
- Finds relevant help even with vague queries
- Reduces "no results found" frustration
- Better first-time resolution rates

**Text Search Limitations:**
- Users must know exact terminology
- Requires multiple search attempts
- High abandonment on failed searches
- Poor experience for non-technical users

## Implementation Recommendations

### 1. Hybrid Approach (Best)
```python
def intelligent_search(query: str):
    # Primary: Vector search (semantic understanding)
    semantic_results = vector_search(query, weight=0.7)
    
    # Secondary: Text search (exact matches)
    keyword_results = text_search(query, weight=0.3)
    
    # Combine with relevance scoring
    return merge_results(semantic_results, keyword_results)
```

### 2. Vector-First with Text Fallback
```python
def search_with_fallback(query: str):
    # Try vector search first
    results = vector_search(query, threshold=0.6)
    
    if len(results) < 3:
        # Fallback to text search for more results
        text_results = text_search(query)
        results.extend(text_results)
    
    return results
```

### 3. Intent Classification + Search
```python
def intent_aware_search(query: str):
    # Classify intent first
    intent = classify_intent(query)  # "login_help", "billing", etc.
    
    # Search within intent-specific documents
    if intent:
        results = vector_search(query, filters={"category": intent})
    else:
        results = vector_search(query)  # General search
    
    return results
```

## AWS Implementation

### OpenSearch with Vector Support
```python
# In storage_stack.py
self.opensearch_domain = opensearch.Domain(
    self, "IntentSearchDomain",
    version=opensearch.EngineVersion.OPENSEARCH_2_5,
    capacity=opensearch.CapacityConfig(
        data_nodes=2,
        data_node_instance_type="t3.medium.search"
    ),
    ebs=opensearch.EbsOptions(
        volume_size=50,
        volume_type=ec2.EbsDeviceVolumeType.GP3
    ),
    # Enable vector search capabilities
    advanced_options={
        "knn.algo_param.ef_search": "512",
        "knn.space_type": "cosinesimil"
    }
)
```

### Vector Index Mapping
```json
{
  "mappings": {
    "properties": {
      "content": {
        "type": "text",
        "analyzer": "standard"
      },
      "title": {
        "type": "text",
        "boost": 2.0
      },
      "embedding": {
        "type": "knn_vector", 
        "dimension": 1536,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib"
        }
      },
      "intent_category": {
        "type": "keyword"
      },
      "confidence_score": {
        "type": "float"
      }
    }
  }
}
```

### Search Query Example
```python
# Semantic search with intent understanding
search_body = {
    "query": {
        "bool": {
            "should": [
                # Vector similarity (primary)
                {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": 10,
                            "boost": 2.0
                        }
                    }
                },
                # Text relevance (secondary)
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["content^1", "title^3"],
                        "type": "best_fields",
                        "boost": 1.0
                    }
                }
            ],
            "minimum_should_match": 1
        }
    },
    "size": 10,
    "_source": ["content", "title", "intent_category"],
    "highlight": {
        "fields": {
            "content": {}
        }
    }
}
```

## Performance Considerations

### Vector Search
- **Latency**: 50-200ms (depending on index size)
- **Memory**: Higher (stores embeddings)
- **Accuracy**: 80-95% for intent understanding

### Text Search  
- **Latency**: 10-50ms
- **Memory**: Lower (inverted index)
- **Accuracy**: 20-60% for intent understanding

## Cost Analysis (AWS)

### OpenSearch with Vectors
- **Instance**: t3.medium.search (~$50/month)
- **Storage**: 50GB EBS (~$5/month)
- **Total**: ~$55/month for small-medium workload

### DynamoDB Only (Text)
- **Storage**: $0.25/GB/month
- **Queries**: $1.25/million reads
- **Total**: ~$10-20/month for small workload

## Recommendation

**For chatbot intent understanding: Use Vector Search**

1. **Better user experience** - understands natural language
2. **Higher accuracy** - finds relevant content semantically  
3. **Reduced support load** - users find answers faster
4. **Future-proof** - works with AI/ML advancements

The additional cost (~$35/month) is justified by significantly better intent understanding and user satisfaction.