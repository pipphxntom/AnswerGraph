"""
Hybrid retrieval module combining vector search with BM25 text search.

This module provides a hybrid retrieval approach that leverages both
semantic embeddings (via Qdrant vector search) and lexical matching (via BM25),
then merges the results for improved retrieval quality.
"""
import re
import math
import logging
from typing import List, Dict, Any, Set, Tuple, Optional, Union
from collections import Counter, defaultdict

import numpy as np
from rank_bm25 import BM25Okapi
from qdrant_client.http.models import Filter, SearchParams

from src.core.dependencies import get_qdrant_client, get_embedding_function

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BM25Index:
    """
    BM25 index for efficient lexical search over policy chunks.
    
    This class implements an in-memory BM25 index for text retrieval,
    optimized for policy document chunks.
    """
    
    def __init__(self):
        """Initialize the BM25 index."""
        self.bm25 = None
        self.documents = []
        self.doc_metadata = []
        self.tokenized_docs = []
        self.is_built = False
        self.policy_indices = defaultdict(list)
    
    def add_document(self, text: str, metadata: Dict[str, Any]) -> None:
        """
        Add a document to the index.
        
        Args:
            text: Document text
            metadata: Document metadata (url, page, policy_id, etc.)
        """
        self.documents.append(text)
        self.doc_metadata.append(metadata)
        
        # Track document indices by policy
        if "policy_id" in metadata:
            policy_id = metadata["policy_id"]
            self.policy_indices[policy_id].append(len(self.documents) - 1)
        
        # Mark as not built since we've added a new document
        self.is_built = False
    
    def add_documents(self, texts: List[str], metadata_list: List[Dict[str, Any]]) -> None:
        """
        Add multiple documents to the index.
        
        Args:
            texts: List of document texts
            metadata_list: List of document metadata
        """
        if len(texts) != len(metadata_list):
            raise ValueError("Length of texts and metadata_list must match")
        
        for text, metadata in zip(texts, metadata_list):
            self.add_document(text, metadata)
    
    def build(self) -> None:
        """Build the BM25 index."""
        if self.is_built:
            logger.debug("BM25 index already built")
            return
        
        if not self.documents:
            logger.warning("No documents to build BM25 index")
            return
        
        # Tokenize documents
        logger.info(f"Tokenizing {len(self.documents)} documents for BM25 indexing")
        self.tokenized_docs = [self._tokenize(doc) for doc in self.documents]
        
        # Build BM25 index
        logger.info("Building BM25 index")
        self.bm25 = BM25Okapi(self.tokenized_docs)
        
        self.is_built = True
        logger.info(f"BM25 index built with {len(self.documents)} documents")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        # Convert to lowercase
        text = text.lower()
        
        # Replace special characters with spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Tokenize by whitespace
        tokens = text.split()
        
        # Filter out short tokens (optional)
        tokens = [token for token in tokens if len(token) > 1]
        
        return tokens
    
    def search(self, query: str, top_k: int = 10, policy_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search the BM25 index.
        
        Args:
            query: Search query
            top_k: Number of results to return
            policy_id: Optional policy ID to filter by
            
        Returns:
            List of search results with scores and metadata
        """
        if not self.is_built:
            self.build()
        
        if not self.bm25:
            logger.warning("BM25 index not built")
            return []
        
        # Tokenize query
        tokenized_query = self._tokenize(query)
        
        # Filter document indices by policy if specified
        doc_indices = None
        if policy_id:
            doc_indices = self.policy_indices.get(policy_id, [])
            if not doc_indices:
                logger.warning(f"No documents found for policy_id: {policy_id}")
                return []
        
        # Get BM25 scores
        if doc_indices is not None:
            # Score only documents for the specified policy
            scores = np.zeros(len(self.documents))
            for idx in doc_indices:
                scores[idx] = self.bm25.get_score(tokenized_query, idx)
        else:
            # Score all documents
            scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        # Prepare results
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include results with non-zero scores
                results.append({
                    "text": self.documents[idx],
                    "score_bm25": float(scores[idx]),
                    **self.doc_metadata[idx]
                })
        
        return results


# Global BM25 index cache by policy_id
_bm25_indices = {}


def _get_or_create_bm25_index(policy_chunks: List[Dict[str, Any]], policy_id: Optional[str] = None) -> BM25Index:
    """
    Get or create a BM25 index for policy chunks.
    
    Args:
        policy_chunks: List of policy chunks with text and metadata
        policy_id: Optional policy ID
        
    Returns:
        BM25Index instance
    """
    global _bm25_indices
    
    # Use policy_id as key if provided, otherwise use 'global'
    key = policy_id if policy_id else 'global'
    
    # Return cached index if it exists
    if key in _bm25_indices:
        logger.debug(f"Using cached BM25 index for {key}")
        return _bm25_indices[key]
    
    # Create new index
    logger.info(f"Creating new BM25 index for {key}")
    index = BM25Index()
    
    # Add documents to index
    texts = [chunk["text"] for chunk in policy_chunks]
    metadata = [{
        "policy_id": chunk.get("policy_id"),
        "url": chunk.get("url"),
        "page": chunk.get("page"),
        "section": chunk.get("section", "")
    } for chunk in policy_chunks]
    
    index.add_documents(texts, metadata)
    index.build()
    
    # Cache the index
    _bm25_indices[key] = index
    return index


def hybrid_retrieve(
    query: str,
    collection_name: str = "a2g_chunks",
    top_k: int = 24,
    policy_id: Optional[str] = None,
    rerank_weight: float = 0.7,  # Weight given to vector scores (0.0-1.0)
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval combining vector search with BM25.
    
    This function:
    1. Encodes the query using the provided embedder
    2. Performs vector search in Qdrant
    3. Builds/uses a BM25 index for the same policy chunks
    4. Merges and deduplicates results
    
    Args:
        query: User query string
        collection_name: Name of Qdrant collection
        top_k: Number of results to retrieve
        policy_id: Optional policy ID to filter by
        rerank_weight: Weight given to vector scores vs BM25 scores
        
    Returns:
        List of merged and reranked results
    """
    logger.info(f"Hybrid retrieval for query: '{query}'")
    
    # Get singletons from dependencies
    qdrant_client = get_qdrant_client()
    embed_function = get_embedding_function()
    
    # 1. Encode query
    query_embedding = embed_function(query)
    
    # Create filter if policy_id is provided
    search_filter = None
    if policy_id:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="policy_id",
                    match=MatchValue(value=policy_id)
                )
            ]
        )
    
    # 2. Perform vector search in Qdrant
    logger.info(f"Performing vector search with top_k={top_k}")
    vector_results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k,
        filter=search_filter,
        search_params=SearchParams(hnsw_ef=128)  # Increase search quality
    )
    
    # Convert vector results to standard format
    vector_candidates = []
    for result in vector_results:
        # Extract payload
        payload = result.payload
        
        vector_candidates.append({
            "text": payload.get("text", ""),
            "policy_id": payload.get("policy_id"),
            "url": payload.get("url"),
            "page": payload.get("page"),
            "section": payload.get("section", ""),
            "score_v": result.score,
            "score_bm25": 0.0,  # Will be filled in later
            "id": result.id
        })
    
    # If no vector results, return empty list
    if not vector_candidates:
        logger.warning("No vector search results found")
        return []
    
    # 3. BM25 search over the same policy chunks
    # First, extract all chunks to build the BM25 index
    logger.info("Building BM25 index from vector results")
    bm25_index = _get_or_create_bm25_index(vector_candidates, policy_id)
    
    # Perform BM25 search
    logger.info(f"Performing BM25 search with top_k={top_k}")
    bm25_results = bm25_index.search(query, top_k=top_k, policy_id=policy_id)
    
    # 4. Merge and deduplicate results
    # Create a unique key for each document based on url and page
    seen_docs = set()
    merged_results = []
    
    # Process vector results first
    for candidate in vector_candidates:
        doc_key = f"{candidate['url']}:{candidate['page']}"
        
        if doc_key not in seen_docs:
            seen_docs.add(doc_key)
            merged_results.append(candidate)
    
    # Process BM25 results and merge with vector results
    for bm25_result in bm25_results:
        doc_key = f"{bm25_result['url']}:{bm25_result['page']}"
        
        if doc_key in seen_docs:
            # Update existing result with BM25 score
            for candidate in merged_results:
                if candidate['url'] == bm25_result['url'] and candidate['page'] == bm25_result['page']:
                    candidate['score_bm25'] = bm25_result['score_bm25']
                    break
        else:
            # Add new result
            seen_docs.add(doc_key)
            bm25_result['score_v'] = 0.0  # No vector score
            merged_results.append(bm25_result)
    
    # Normalize scores
    if merged_results:
        # Find max scores for normalization
        max_vector_score = max(r['score_v'] for r in merged_results) if any(r['score_v'] for r in merged_results) else 1.0
        max_bm25_score = max(r['score_bm25'] for r in merged_results) if any(r['score_bm25'] for r in merged_results) else 1.0
        
        # Normalize and combine scores
        for result in merged_results:
            norm_vector_score = result['score_v'] / max_vector_score if max_vector_score > 0 else 0
            norm_bm25_score = result['score_bm25'] / max_bm25_score if max_bm25_score > 0 else 0
            
            # Combined score with weighting
            result['score'] = (rerank_weight * norm_vector_score) + ((1 - rerank_weight) * norm_bm25_score)
    
    # Sort by combined score
    merged_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Limit to top_k
    return merged_results[:top_k]


# Simple test function
def test_hybrid_retrieval():
    """Test the hybrid retrieval function."""
    # Test query
    query = "What is the policy for remote work?"
    
    # Call hybrid retrieve
    results = hybrid_retrieve(
        query=query,
        top_k=10
    )
    
    # Print results
    print(f"\nHybrid Search Results for: '{query}'")
    print(f"Found {len(results)} results\n")
    
    for i, result in enumerate(results):
        print(f"[{i+1}] Combined Score: {result['score']:.4f}")
        print(f"    Vector: {result['score_v']:.4f} | BM25: {result['score_bm25']:.4f}")
        print(f"    Policy: {result['policy_id']} | Page: {result['page']}")
        print(f"    {result['text'][:150]}...\n")


if __name__ == "__main__":
    # Run test if executed directly
    import sys
    import asyncio
    
    if len(sys.argv) > 1:
        # Use command line argument as query
        query = sys.argv[1]
        
        # Call hybrid retrieve
        results = hybrid_retrieve(
            query=query,
            top_k=10
        )
        
        # Print results
        print(f"\nHybrid Search Results for: '{query}'")
        print(f"Found {len(results)} results\n")
        
        for i, result in enumerate(results):
            print(f"[{i+1}] Combined Score: {result['score']:.4f}")
            print(f"    Vector: {result['score_v']:.4f} | BM25: {result['score_bm25']:.4f}")
            print(f"    Policy: {result['policy_id']} | Page: {result['page']}")
            print(f"    {result['text'][:150]}...\n")
    else:
        # Run default test
        test_hybrid_retrieval()
