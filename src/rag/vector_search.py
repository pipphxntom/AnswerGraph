"""
Vector search utility for policy retrieval.

This module provides functions to search for policy chunks using vector similarity.
"""
import sys
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.core.dependencies import get_embedding_model, get_qdrant_client
from src.core.config import settings
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

# Configure logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def search_policies(
    query: str,
    top_k: int = 5,
    policy_id: Optional[str] = None,
    collection_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Search for policy chunks using vector similarity.
    
    Args:
        query: Query string
        top_k: Number of results to return
        policy_id: Optional policy ID to filter by
        collection_name: Qdrant collection name (defaults to settings value)
        
    Returns:
        List of search results with metadata
    """
    # Get the Qdrant client and embedding model from dependencies
    client = get_qdrant_client()
    embedding_model = get_embedding_model()
    
    # Use default collection name if not provided
    if collection_name is None:
        collection_name = settings.QDRANT_COLLECTION_NAME
    
    # Embed query
    query_embedding = embedding_model.encode(query).tolist()
    
    # Create filter if policy_id is provided
    search_filter = None
    if policy_id:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="policy_id",
                    match=MatchValue(value=policy_id)
                )
            ]
        )
    
    # Search
    search_results = client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k,
        filter=search_filter
    )
    
    # Format results
    results = []
    for result in search_results:
        results.append({
            "score": result.score,
            "policy_id": result.payload.get("policy_id"),
            "url": result.payload.get("url"),
            "page": result.payload.get("page"),
            "section": result.payload.get("section"),
            "text": result.payload.get("text")
        })
    
    return results


async def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Search policy chunks")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--policy-id", help="Filter by policy ID")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--collection", default="a2g_chunks", help="Qdrant collection name")
    
    args = parser.parse_args()
    
    # Initialize singletons if running as script
    from src.core.dependencies import init_embedding_model, init_qdrant_client
    init_embedding_model()
    init_qdrant_client()
    
    # Search
    results = await search_policies(
        query=args.query,
        top_k=args.top_k,
        policy_id=args.policy_id,
        collection_name=args.collection
    )
    
    # Print results
    print(f"\nSearch Results for: '{args.query}'")
    print(f"Found {len(results)} results\n")
    
    for i, result in enumerate(results):
        print(f"[{i+1}] Score: {result['score']:.4f} | Policy: {result['policy_id']}")
        print(f"    Page: {result['page']} | Section: {result['section']}")
        print(f"    {result['text'][:200]}...\n")


if __name__ == "__main__":
    asyncio.run(main())
