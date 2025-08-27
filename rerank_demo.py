#!/usr/bin/env python
"""
Cross-Encoder Reranking Demo

This script demonstrates how to use the cross-encoder reranking
functionality to improve search results quality.
"""
import sys
import argparse
import logging
from typing import List, Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.rag.hybrid_retriever import hybrid_retrieve
from src.rag.reranker import cross_encode_rerank
from src.ingest.embedding_indexer import EmbeddingIndexer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def search_with_reranking(
    query: str,
    first_stage_k: int = 20,
    final_k: int = 8,
    collection: str = "a2g_chunks",
    rerank_model: str = "mixedbread-ai/mxbai-rerank-large-v1"
) -> List[Dict[str, Any]]:
    """
    Two-stage retrieval with cross-encoder reranking.
    
    Args:
        query: Search query
        first_stage_k: Number of candidates to retrieve in first stage
        final_k: Number of final results after reranking
        collection: Qdrant collection name
        rerank_model: Cross-encoder model to use for reranking
        
    Returns:
        List of reranked search results
    """
    logger.info(f"First stage retrieval for query: '{query}'")
    
    # Initialize components
    indexer = EmbeddingIndexer(collection_name=collection)
    client = indexer.connect_qdrant()
    
    # First stage: hybrid retrieval
    candidates = hybrid_retrieve(
        query=query,
        qdrant_client=client,
        embedder=indexer,
        top_k=first_stage_k,
        collection_name=collection
    )
    
    logger.info(f"Retrieved {len(candidates)} candidates, reranking with {rerank_model}")
    
    # Second stage: cross-encoder reranking
    reranked_results = cross_encode_rerank(
        query=query,
        candidates=candidates,
        top_n=final_k,
        model_name=rerank_model
    )
    
    return reranked_results


def print_results(results: List[Dict[str, Any]], query: str, show_details: bool = True) -> None:
    """
    Print search results in a readable format.
    
    Args:
        results: Search results
        query: Original query
        show_details: Whether to show scoring details
    """
    print("\n" + "="*80)
    print(f"RERANKED SEARCH RESULTS FOR: '{query}'")
    print(f"Found {len(results)} results")
    print("="*80 + "\n")
    
    for i, result in enumerate(results):
        # Print result header
        print(f"[{i+1}] Final Score: {result['final_score']:.4f}")
        
        # Print score details if requested
        if show_details:
            if 'original_score' in result:
                print(f"    Original Score: {result['original_score']:.4f}")
            if 'score_v' in result and 'score_bm25' in result:
                print(f"    Vector Score: {result['score_v']:.4f} | BM25 Score: {result['score_bm25']:.4f}")
            if 'cross_encoder_score' in result:
                print(f"    Cross-Encoder Score: {result['cross_encoder_score']:.4f}")
        
        # Print metadata
        print(f"    Policy: {result['policy_id']} | Page: {result['page']}")
        if result.get('section'):
            print(f"    Section: {result['section']}")
        
        # Print text preview
        preview = result['text'][:200].replace('\n', ' ')
        print(f"    {preview}...\n")


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Cross-Encoder Reranking Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("query", help="Search query")
    parser.add_argument("--first-stage", "-f", type=int, default=20, 
                       help="Number of candidates to retrieve in first stage")
    parser.add_argument("--final", "-k", type=int, default=8, 
                       help="Number of final results after reranking")
    parser.add_argument("--collection", "-c", default="a2g_chunks", 
                       help="Qdrant collection name")
    parser.add_argument("--model", "-m", default="mixedbread-ai/mxbai-rerank-large-v1", 
                       help="Cross-encoder model to use for reranking")
    parser.add_argument("--no-details", action="store_true", 
                       help="Hide scoring details")
    
    args = parser.parse_args()
    
    try:
        # Search with reranking
        results = search_with_reranking(
            query=args.query,
            first_stage_k=args.first_stage,
            final_k=args.final,
            collection=args.collection,
            rerank_model=args.model
        )
        
        # Print results
        print_results(results, args.query, not args.no_details)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
