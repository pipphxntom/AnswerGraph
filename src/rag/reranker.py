from typing import List, Dict, Any, Union, Tuple
import numpy as np
from sentence_transformers import CrossEncoder

# CrossEncoder models for reranking
DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MXBAI_MODEL = "mixedbread-ai/mxbai-rerank-large-v1"


class Reranker:
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model = CrossEncoder(model_name, max_length=512)
    
    def rerank(self, query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rerank documents based on query-document relevance."""
        if not documents:
            return []
        
        # Prepare pairs for reranking
        pairs = [(query, doc["content"]) for doc in documents]
        
        # Get scores
        scores = self.model.predict(pairs)
        
        # Assign new scores to documents
        for i, doc in enumerate(documents):
            doc["score"] = float(scores[i])
        
        # Sort by new scores
        reranked_docs = sorted(documents, key=lambda x: x["score"], reverse=True)
        
        return reranked_docs


def cross_encode_rerank(
    query: str, 
    candidates: List[Dict[str, Any]], 
    top_n: int = 8,
    model_name: str = MXBAI_MODEL
) -> List[Dict[str, Any]]:
    """
    Rerank candidates using a cross-encoder model.
    
    Args:
        query: The search query
        candidates: List of candidate documents to rerank
        top_n: Number of top candidates to return after reranking
        model_name: Name of the cross-encoder model to use
        
    Returns:
        List of top_n documents reranked by relevance with final_score
    """
    if not candidates:
        return []
    
    # Initialize cross-encoder
    cross_encoder = CrossEncoder(model_name, max_length=512)
    
    # Create pairs for scoring
    text_field = "text" if "text" in candidates[0] else "content"
    pairs = [(query, doc[text_field]) for doc in candidates]
    
    # Predict relevance scores
    scores = cross_encoder.predict(pairs)
    
    # Add scores to candidates
    for i, doc in enumerate(candidates):
        # Store both the original score and the new cross-encoder score
        doc["original_score"] = doc.get("score", 0.0)
        doc["cross_encoder_score"] = float(scores[i])
        doc["final_score"] = float(scores[i])  # Use cross-encoder score as final
    
    # Sort by cross-encoder score and take top_n
    reranked = sorted(candidates, key=lambda x: x["cross_encoder_score"], reverse=True)[:top_n]
    
    return reranked


def rerank_documents(query: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rerank documents based on query."""
    return reranker.rerank(query, documents)


# Create a singleton instance
reranker = Reranker()
