#!/usr/bin/env python
"""
Hybrid Policy Search Tool

This script demonstrates the hybrid retrieval system combining
vector search and BM25 for improved policy document retrieval.
"""
import os
import sys
import argparse
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.rag.hybrid_retriever import hybrid_retrieve
from src.ingest.embedding_indexer import EmbeddingIndexer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def search_policies(
    query: str,
    top_k: int = 10,
    policy_id: Optional[str] = None,
    vector_weight: float = 0.7,
    collection: str = "a2g_chunks"
) -> List[Dict[str, Any]]:
    """
    Search for policy documents using hybrid retrieval.
    
    Args:
        query: Search query
        top_k: Number of results to return
        policy_id: Optional policy ID to filter by
        vector_weight: Weight given to vector scores (0.0-1.0)
        collection: Qdrant collection name
        
    Returns:
        List of search results
    """
    # Initialize components
    indexer = EmbeddingIndexer(collection_name=collection)
    client = indexer.connect_qdrant()
    
    # Call hybrid retrieve
    results = hybrid_retrieve(
        query=query,
        qdrant_client=client,
        embedder=indexer,
        top_k=top_k,
        policy_id=policy_id,
        rerank_weight=vector_weight,
        collection_name=collection
    )
    
    return results


def print_results(results: List[Dict[str, Any]], query: str, detailed: bool = False) -> None:
    """
    Print search results in a readable format.
    
    Args:
        results: Search results
        query: Original query
        detailed: Whether to show detailed information
    """
    print("\n" + "="*80)
    print(f"HYBRID SEARCH RESULTS FOR: '{query}'")
    print(f"Found {len(results)} results")
    print("="*80 + "\n")
    
    for i, result in enumerate(results):
        # Print result header
        print(f"[{i+1}] Combined Score: {result['score']:.4f}")
        
        # Print score details
        print(f"    Vector Score: {result['score_v']:.4f} | BM25 Score: {result['score_bm25']:.4f}")
        
        # Print metadata
        print(f"    Policy: {result['policy_id']} | Page: {result['page']}")
        if result.get('section'):
            print(f"    Section: {result['section']}")
        
        # Print text preview
        if detailed:
            print(f"\n    {result['text']}\n")
        else:
            preview = result['text'][:200].replace('\n', ' ')
            print(f"    {preview}...\n")


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Hybrid Policy Search Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--interactive", "-i", action="store_true", 
                       help="Run in interactive mode")
    parser.add_argument("--policy", "-p", help="Filter by policy ID")
    parser.add_argument("--top-k", "-k", type=int, default=10, 
                       help="Number of results to return")
    parser.add_argument("--weight", "-w", type=float, default=0.7, 
                       help="Weight given to vector scores (0.0-1.0)")
    parser.add_argument("--collection", "-c", default="a2g_chunks", 
                       help="Qdrant collection name")
    parser.add_argument("--detailed", "-d", action="store_true", 
                       help="Show detailed results")
    
    args = parser.parse_args()
    
    if args.interactive:
        # Interactive mode
        print("\nHybrid Policy Search Interactive Mode")
        print("Type 'exit' or 'quit' to exit\n")
        
        while True:
            # Get query
            query = input("Enter search query: ")
            
            # Check for exit command
            if query.lower() in ("exit", "quit"):
                break
            
            if not query.strip():
                continue
            
            try:
                # Search
                results = search_policies(
                    query=query,
                    top_k=args.top_k,
                    policy_id=args.policy,
                    vector_weight=args.weight,
                    collection=args.collection
                )
                
                # Print results
                print_results(results, query, args.detailed)
                
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                print(f"Error: {str(e)}")
                
    elif args.query:
        # Single query mode
        try:
            # Search
            results = search_policies(
                query=args.query,
                top_k=args.top_k,
                policy_id=args.policy,
                vector_weight=args.weight,
                collection=args.collection
            )
            
            # Print results
            print_results(results, args.query, args.detailed)
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            print(f"Error: {str(e)}")
            return 1
    else:
        parser.print_help()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
