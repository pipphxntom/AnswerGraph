"""Module for embedding document chunks and indexing them in Qdrant."""
from typing import Dict, List, Any, Optional, Union
import logging
import uuid
import time
import asyncio
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance, VectorParams, PointStruct, BatchPoints,
    OptimizersConfigDiff, CreateCollection
)

from src.core.config import settings
from src.core.db import get_session, Base
from src.core.dependencies import get_embedding_model, get_qdrant_client
from src.models.chunk import Chunk

logger = logging.getLogger(__name__)


class EmbedIndex:
    """
    Embed document chunks and index them in the vector database.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.embedding_model_name = self.config.get(
            "embedding_model", 
            settings.EMBEDDING_MODEL
        )
        self.collection_name = self.config.get(
            "collection_name", 
            settings.QDRANT_COLLECTION_NAME
        )
        
        # Use singletons from dependencies
        self.embedding_model = get_embedding_model()
        self.vector_size = self.embedding_model.get_sentence_embedding_dimension()
        self.qdrant_client = get_qdrant_client()
        
        logger.info(
            f"Initialized EmbedIndex with model={self.embedding_model_name}, "
            f"vector_size={self.vector_size}"
        )
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self) -> None:
        """Ensure the vector collection exists in Qdrant."""
        collections = self.qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            logger.info(f"Creating collection {self.collection_name}")
            
            # Create the collection
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                ),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=10000  # Optimize for larger collections
                )
            )
            
            # Create payload indexes for faster filtering
            self._create_payload_indexes()
        else:
            logger.info(f"Collection {self.collection_name} already exists")
    
    def _create_payload_indexes(self) -> None:
        """Create payload indexes for efficient filtering."""
        payload_indexes = [
            ("source_id", "integer"),
            ("policy_id", "integer"),
            ("procedure_id", "integer"),
            ("page_number", "integer"),
            ("section", "text")
        ]
        
        for field_name, field_type in payload_indexes:
            self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=field_type
            )
    
    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        return self.embedding_model.encode(text).tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of text strings.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        return self.embedding_model.encode(texts).tolist()
    
    async def index_chunks(
        self, 
        chunks: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> List[str]:
        """
        Index document chunks in Qdrant.
        
        Args:
            chunks: List of chunk dictionaries with content and metadata
            batch_size: Number of chunks to process in each batch
            
        Returns:
            List of vector IDs created
        """
        if not chunks:
            logger.warning("No chunks provided for indexing")
            return []
        
        logger.info(f"Indexing {len(chunks)} chunks in batches of {batch_size}")
        vector_ids = []
        
        # Process in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_ids = await self._process_batch(batch)
            vector_ids.extend(batch_ids)
            
            # Log progress
            logger.info(f"Indexed batch {i//batch_size + 1}, "
                        f"progress: {min(i+batch_size, len(chunks))}/{len(chunks)}")
        
        logger.info(f"Successfully indexed {len(vector_ids)} chunks")
        return vector_ids
    
    async def _process_batch(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Process a batch of chunks for indexing."""
        # Extract text for embedding
        texts = [chunk["content"] for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.embed_batch(texts)
        
        # Generate IDs
        ids = [str(uuid.uuid4()) for _ in range(len(chunks))]
        
        # Prepare points for Qdrant
        points = []
        for i, (chunk, embedding, id_) in enumerate(zip(chunks, embeddings, ids)):
            # Extract relevant metadata for payload
            payload = {
                "content": chunk["content"],
                "page_number": chunk.get("page_number"),
                "section": chunk.get("section"),
                "source_id": chunk.get("source_id"),
                "policy_id": chunk.get("policy_id"),
                "procedure_id": chunk.get("procedure_id")
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # Add to points
            points.append(PointStruct(
                id=id_,
                vector=embedding,
                payload=payload
            ))
        
        # Upload to Qdrant
        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        # Update database with vector IDs
        await self._update_database(chunks, ids)
        
        return ids
    
    async def _update_database(
        self, 
        chunks: List[Dict[str, Any]], 
        vector_ids: List[str]
    ) -> None:
        """Update the SQL database with vector IDs."""
        async for session in get_session():
            for chunk_data, vector_id in zip(chunks, vector_ids):
                # Check if chunk has a database ID
                chunk_id = chunk_data.get("id")
                
                if chunk_id:
                    # Update existing chunk
                    chunk = await session.get(Chunk, chunk_id)
                    if chunk:
                        chunk.vector_id = vector_id
                else:
                    # This is handling chunks that aren't yet in the database
                    logger.debug(f"Chunk not in database, vector ID {vector_id} not linked")
            
            await session.commit()
    
    async def delete_by_filter(self, filter_dict: Dict[str, Any]) -> int:
        """
        Delete vectors from the index based on a filter.
        
        Args:
            filter_dict: Dictionary with filter conditions
            
        Returns:
            Number of deleted vectors
        """
        # Convert filter dict to Qdrant filter format
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        
        filter_conditions = []
        for field, value in filter_dict.items():
            if isinstance(value, list):
                # Handle multiple possible values
                for val in value:
                    filter_conditions.append(
                        FieldCondition(key=field, match=MatchValue(value=val))
                    )
            else:
                filter_conditions.append(
                    FieldCondition(key=field, match=MatchValue(value=value))
                )
        
        if filter_conditions:
            qdrant_filter = Filter(must=filter_conditions)
            
            # Get points to delete
            search_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                filter=qdrant_filter,
                limit=10000  # Adjust as needed
            )
            
            if search_result and search_result[0]:
                # Extract IDs
                ids_to_delete = [point.id for point in search_result[0]]
                
                # Delete points
                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=ids_to_delete
                )
                
                logger.info(f"Deleted {len(ids_to_delete)} vectors based on filter: {filter_dict}")
                return len(ids_to_delete)
        
        logger.info(f"No vectors found for deletion with filter: {filter_dict}")
        return 0


# Create a singleton instance for easy import
# This will be lazily initialized when first accessed
_embed_indexer = None

def get_embed_indexer() -> EmbedIndex:
    """Get the singleton EmbedIndex instance."""
    global _embed_indexer
    if _embed_indexer is None:
        _embed_indexer = EmbedIndex()
    return _embed_indexer


async def index_document_chunks(chunks: List[Dict[str, Any]]) -> List[str]:
    """
    Index document chunks in the vector database.
    
    This is a convenience function that uses the singleton instance.
    """
    indexer = get_embed_indexer()
    return await indexer.index_chunks(chunks)
