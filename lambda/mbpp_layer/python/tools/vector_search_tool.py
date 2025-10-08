"""Vector search tool for MCP server."""
import sys
sys.path.append('/opt')
sys.path.append('/var/task')

from shared.vector_rag_handler import search_embedded_documents

def search_documents(query: str, limit: int = 5):
    """
    Search embedded documents using vector similarity.
    
    Args:
        query: Search query text
        limit: Maximum number of results (default: 5)
    
    Returns:
        List of relevant document chunks with similarity scores
    """
    return search_embedded_documents(query, limit)
