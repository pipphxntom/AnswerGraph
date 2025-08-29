"""
Dependency injection module for FastAPI application.

This module provides singleton instances and dependencies for:
1. Database session
2. Embedding model
3. Qdrant client
4. Reranker model
5. Cross-encoder model
"""
from typing import Optional, AsyncGenerator, Any
import logging
from functools import lru_cache
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer
from sentence_transformers import CrossEncoder

from src.core.config import settings
from src.core.db import get_async_session

logger = logging.getLogger(__name__)

# Singleton instances
_embedding_model: Optional[SentenceTransformer] = None
_qdrant_client: Optional[QdrantClient] = None
_reranker: Optional[Any] = None
_cross_encoder: Optional[CrossEncoder] = None
_retriever: Optional[Any] = None

# Default model names
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_CROSS_ENCODER_MODEL = "mixedbread-ai/mxbai-rerank-large-v1"


def init_embedding_model() -> SentenceTransformer:
    """
    Initialize the embedding model singleton.
    
    Returns:
        SentenceTransformer instance
    """
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Initializing embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedding_model


def init_qdrant_client() -> QdrantClient:
    """
    Initialize the Qdrant client singleton.
    
    Returns:
        QdrantClient instance
    """
    global _qdrant_client
    if _qdrant_client is None:
        logger.info(f"Initializing Qdrant client: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        _qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
    return _qdrant_client


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    """
    Get the embedding model singleton.
    
    Returns:
        SentenceTransformer instance
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = init_embedding_model()
    return _embedding_model


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """
    Get the Qdrant client singleton.
    
    Returns:
        QdrantClient instance
    """
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = init_qdrant_client()
    return _qdrant_client


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get a database session.
    
    Yields:
        AsyncSession instance
    """
    async for session in get_async_session():
        yield session


def get_embedding_function():
    """
    Get a function that will embed text using the singleton model.
    
    Returns:
        Callable that embeds text
    """
    model = get_embedding_model()
    
    def embed_function(text: str) -> list[float]:
        """Embed a single text string."""
        return model.encode(text).tolist()
    
    return embed_function


def get_batch_embedding_function():
    """
    Get a function that will embed batches of text using the singleton model.
    
    Returns:
        Callable that embeds batches of text
    """
    model = get_embedding_model()
    
    def batch_embed_function(texts: list[str]) -> list[list[float]]:
        """Embed a batch of text strings."""
        return model.encode(texts).tolist()
    
    return batch_embed_function


def init_reranker():
    """
    Initialize the reranker singleton.
    
    Returns:
        Reranker instance
    """
    global _reranker
    if _reranker is None:
        # Import here to avoid circular imports
        from src.rag.reranker import Reranker
        logger.info(f"Initializing reranker model with {DEFAULT_RERANKER_MODEL}")
        _reranker = Reranker(model_name=DEFAULT_RERANKER_MODEL)
    return _reranker


def init_cross_encoder(model_name: str = DEFAULT_CROSS_ENCODER_MODEL):
    """
    Initialize the cross-encoder singleton.
    
    Args:
        model_name: Name of the cross-encoder model to use
        
    Returns:
        CrossEncoder instance
    """
    global _cross_encoder
    if _cross_encoder is None:
        logger.info(f"Initializing cross-encoder model: {model_name}")
        _cross_encoder = CrossEncoder(model_name, max_length=512)
    return _cross_encoder


@lru_cache
def get_reranker():
    """
    Get the reranker singleton.
    
    Returns:
        Reranker instance
    """
    global _reranker
    if _reranker is None:
        _reranker = init_reranker()
    return _reranker


@lru_cache
def get_cross_encoder(model_name: str = DEFAULT_CROSS_ENCODER_MODEL):
    """
    Get the cross-encoder singleton.
    
    Args:
        model_name: Name of the cross-encoder model to use
        
    Returns:
        CrossEncoder instance
    """
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = init_cross_encoder(model_name)
    return _cross_encoder


def init_retriever():
    """
    Initialize the retriever singleton.
    
    Returns:
        Retriever instance
    """
    global _retriever
    if _retriever is None:
        # Import here to avoid circular imports
        from src.rag.retriever import Retriever
        logger.info("Initializing Retriever")
        _retriever = Retriever()
    return _retriever


@lru_cache
def get_retriever():
    """
    Get the retriever singleton.
    
    Returns:
        Retriever instance
    """
    global _retriever
    if _retriever is None:
        _retriever = init_retriever()
    return _retriever
