"""
Embedding Indexer using BGE-M3 model for Qdrant integration.

This module provides functionality to embed text chunks and index them in Qdrant
using the state-of-the-art BGE-M3 embedding model.
"""
import os
import sys
import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance, 
    VectorParams, 
    PointStruct,
    BatchPoints,
    OptimizersConfigDiff, 
    CreateCollection,
    Filter,
    FieldCondition,
    MatchValue
)

# Add project root to path if running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import project modules
from src.core.config import settings
from src.core.db import get_session
from src.models.source import Source
from src.models.chunk import Chunk
from src.ingest.pdf.extractor import process_pdf

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmbeddingIndexer:
    """
    Embedding indexer using BGE-M3 model for Qdrant integration.
    
    This class handles:
    1. Loading and configuring the embedding model
    2. Creating and managing Qdrant collections
    3. Embedding and indexing text chunks
    4. Searching and retrieving similar chunks
    """
    
    def __init__(self, 
                 model_name: str = "BAAI/bge-m3", 
                 collection_name: str = "a2g_chunks",
                 batch_size: int = 32,
                 normalize_embeddings: bool = True):
        """
        Initialize the embedding indexer.
        
        Args:
            model_name: Name of the SentenceTransformer model to use
            collection_name: Name of the Qdrant collection
            batch_size: Batch size for embedding generation
            normalize_embeddings: Whether to normalize embeddings (recommended for cosine similarity)
        """
        self.model_name = model_name
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        
        # Load the embedding model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.vector_size = self.model.get_sentence_embedding_dimension()
        
        logger.info(f"Initialized EmbeddingIndexer with model={model_name}, "
                   f"vector_size={self.vector_size}")
        
        # Connect to Qdrant (done lazily when needed)
        self.client = None
    
    def connect_qdrant(self, 
                      host: Optional[str] = None, 
                      port: Optional[int] = None) -> QdrantClient:
        """
        Connect to Qdrant server.
        
        Args:
            host: Qdrant host (defaults to settings)
            port: Qdrant port (defaults to settings)
            
        Returns:
            QdrantClient instance
        """
        if self.client is not None:
            return self.client
            
        host = host or settings.QDRANT_HOST
        port = port or settings.QDRANT_PORT
        
        logger.info(f"Connecting to Qdrant at {host}:{port}")
        self.client = QdrantClient(host=host, port=port)
        return self.client
    
    def ensure_collection(self, 
                         client: Optional[QdrantClient] = None, 
                         name: Optional[str] = None) -> bool:
        """
        Ensure collection exists in Qdrant.
        
        Args:
            client: QdrantClient instance (uses self.client if None)
            name: Collection name (uses self.collection_name if None)
            
        Returns:
            True if collection was created, False if it already existed
        """
        client = client or self.connect_qdrant()
        name = name or self.collection_name
        
        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if name in collection_names:
            logger.info(f"Collection {name} already exists")
            return False
        
        # Create collection
        logger.info(f"Creating collection {name} with vector size {self.vector_size}")
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=10000  # Optimize for larger collections
            )
        )
        
        # Create payload indexes for faster filtering
        self._create_payload_indexes(client, name)
        
        logger.info(f"Created collection {name}")
        return True
    
    def _create_payload_indexes(self, 
                               client: QdrantClient, 
                               collection_name: str) -> None:
        """
        Create payload indexes for efficient filtering.
        
        Args:
            client: QdrantClient instance
            collection_name: Collection name
        """
        payload_indexes = [
            ("policy_id", "keyword"),
            ("url", "text"),
            ("page", "integer"),
            ("section", "text"),
            ("language", "keyword")
        ]
        
        for field_name, field_type in payload_indexes:
            logger.debug(f"Creating payload index for {field_name} ({field_type})")
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            Numpy array of embeddings
        """
        # Process in batches for memory efficiency
        if len(texts) > self.batch_size:
            embeddings = []
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i+self.batch_size]
                batch_embeddings = self.model.encode(
                    batch, 
                    normalize_embeddings=self.normalize_embeddings
                )
                embeddings.append(batch_embeddings)
            return np.vstack(embeddings)
        
        # Process small batches directly
        return self.model.encode(
            texts, 
            normalize_embeddings=self.normalize_embeddings
        )
    
    async def index_chunks(self,
                         policy_id: str,
                         source_url: str,
                         chunks: List[Dict[str, Any]],
                         collection_name: Optional[str] = None) -> List[str]:
        """
        Index chunks in Qdrant.
        
        Args:
            policy_id: Policy ID for the chunks
            source_url: Source URL for the chunks
            chunks: List of chunk dictionaries
            collection_name: Collection name (uses self.collection_name if None)
            
        Returns:
            List of vector IDs
        """
        if not chunks:
            logger.warning(f"No chunks provided for policy {policy_id}")
            return []
        
        collection_name = collection_name or self.collection_name
        client = self.connect_qdrant()
        
        # Ensure collection exists
        self.ensure_collection(client, collection_name)
        
        # Extract texts for embedding
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} chunks")
        embeddings = self.embed_texts(texts)
        
        # Generate IDs
        vector_ids = [str(uuid.uuid4()) for _ in range(len(chunks))]
        
        # Prepare points for Qdrant
        points = []
        for i, (chunk, embedding, vector_id) in enumerate(zip(chunks, embeddings, vector_ids)):
            # Extract metadata
            payload = {
                "text": chunk["text"],
                "policy_id": policy_id,
                "url": source_url,
                "page": chunk.get("page"),
                "section": chunk.get("section", ""),
                "language": chunk.get("language", "en")
            }
            
            # Add to points
            points.append(PointStruct(
                id=vector_id,
                vector=embedding.tolist(),
                payload=payload
            ))
        
        # Upload to Qdrant
        logger.info(f"Uploading {len(points)} points to Qdrant collection {collection_name}")
        client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        # Update database with vector IDs if there are chunk IDs
        await self._update_database(chunks, vector_ids)
        
        logger.info(f"Successfully indexed {len(vector_ids)} chunks for policy {policy_id}")
        return vector_ids
    
    async def _update_database(self, 
                              chunks: List[Dict[str, Any]], 
                              vector_ids: List[str]) -> None:
        """
        Update database with vector IDs.
        
        Args:
            chunks: List of chunk dictionaries
            vector_ids: List of vector IDs
        """
        chunk_ids = [chunk.get("id") for chunk in chunks]
        if not any(chunk_ids):
            logger.debug("No chunk IDs provided, skipping database update")
            return
        
        async for session in get_session():
            try:
                for chunk_id, vector_id in zip(chunk_ids, vector_ids):
                    if not chunk_id:
                        continue
                        
                    # Update existing chunk
                    chunk = await session.get(Chunk, chunk_id)
                    if chunk:
                        chunk.vector_id = vector_id
                        logger.debug(f"Updated chunk {chunk_id} with vector ID {vector_id}")
                
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating database with vector IDs: {str(e)}")
    
    async def delete_policy_vectors(self, 
                                  policy_id: str, 
                                  collection_name: Optional[str] = None) -> int:
        """
        Delete vectors for a specific policy.
        
        Args:
            policy_id: Policy ID to delete vectors for
            collection_name: Collection name (uses self.collection_name if None)
            
        Returns:
            Number of deleted vectors
        """
        collection_name = collection_name or self.collection_name
        client = self.connect_qdrant()
        
        # Create filter
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="policy_id",
                    match=MatchValue(value=policy_id)
                )
            ]
        )
        
        # Get points to delete
        search_result = client.scroll(
            collection_name=collection_name,
            filter=filter_condition,
            limit=10000  # Adjust as needed
        )
        
        if not search_result or not search_result[0]:
            logger.info(f"No vectors found for policy {policy_id}")
            return 0
        
        # Extract IDs
        ids_to_delete = [point.id for point in search_result[0]]
        
        # Delete points
        client.delete(
            collection_name=collection_name,
            points_selector=ids_to_delete
        )
        
        logger.info(f"Deleted {len(ids_to_delete)} vectors for policy {policy_id}")
        return len(ids_to_delete)


async def index_all_policy_sources():
    """
    Index all policy sources in the database.
    
    This function:
    1. Queries the database for all Source records
    2. Processes each source (PDF) into chunks
    3. Indexes the chunks in Qdrant
    """
    logger.info("Starting indexing of all policy sources")
    
    # Create indexer
    indexer = EmbeddingIndexer()
    
    # Connect to database
    async for session in get_session():
        # Query for all sources
        sources = await session.query(Source).all()
        
        if not sources:
            logger.warning("No sources found in database")
            return
        
        logger.info(f"Found {len(sources)} sources to process")
        
        # Process each source
        for source in sources:
            logger.info(f"Processing source {source.id} for policy {source.policy_id}")
            
            # Extract URL (remove file:// prefix if present)
            url = source.url
            if url.startswith("file://"):
                url = url[7:]
            
            if not os.path.exists(url) and not url.startswith(("http://", "https://")):
                logger.warning(f"Source file not found: {url}")
                continue
            
            try:
                # Process PDF into chunks
                logger.info(f"Extracting chunks from {url}")
                chunks = process_pdf(url, min_tokens=200, max_tokens=400)
                
                if not chunks:
                    logger.warning(f"No chunks extracted from {url}")
                    continue
                
                logger.info(f"Extracted {len(chunks)} chunks from {url}")
                
                # Index chunks
                await indexer.index_chunks(
                    policy_id=source.policy_id,
                    source_url=source.url,
                    chunks=chunks
                )
                
                logger.info(f"Successfully indexed chunks for source {source.id}")
                
            except Exception as e:
                logger.error(f"Error processing source {source.id}: {str(e)}")


async def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Index policy sources in Qdrant")
    parser.add_argument("--all", action="store_true", help="Process all sources in database")
    parser.add_argument("--policy", help="Process sources for specific policy ID")
    parser.add_argument("--pdf", help="Process a specific PDF file")
    parser.add_argument("--policy-id", help="Policy ID for the PDF file")
    parser.add_argument("--collection", help="Qdrant collection name")
    
    args = parser.parse_args()
    
    # Create indexer
    indexer = EmbeddingIndexer(
        collection_name=args.collection or "a2g_chunks"
    )
    
    if args.all:
        # Process all sources
        await index_all_policy_sources()
    
    elif args.policy:
        # Process sources for specific policy
        logger.info(f"Processing sources for policy {args.policy}")
        
        async for session in get_session():
            sources = await session.query(Source).filter(Source.policy_id == args.policy).all()
            
            if not sources:
                logger.warning(f"No sources found for policy {args.policy}")
                return
            
            logger.info(f"Found {len(sources)} sources for policy {args.policy}")
            
            for source in sources:
                # Extract URL
                url = source.url
                if url.startswith("file://"):
                    url = url[7:]
                
                if not os.path.exists(url) and not url.startswith(("http://", "https://")):
                    logger.warning(f"Source file not found: {url}")
                    continue
                
                # Process PDF into chunks
                chunks = process_pdf(url, min_tokens=200, max_tokens=400)
                
                if not chunks:
                    logger.warning(f"No chunks extracted from {url}")
                    continue
                
                # Index chunks
                await indexer.index_chunks(
                    policy_id=source.policy_id,
                    source_url=source.url,
                    chunks=chunks
                )
    
    elif args.pdf:
        # Process a specific PDF file
        if not args.policy_id:
            logger.error("--policy-id is required when processing a specific PDF file")
            return
        
        if not os.path.exists(args.pdf):
            logger.error(f"PDF file not found: {args.pdf}")
            return
        
        logger.info(f"Processing PDF {args.pdf} for policy {args.policy_id}")
        
        # Process PDF into chunks
        chunks = process_pdf(args.pdf, min_tokens=200, max_tokens=400)
        
        if not chunks:
            logger.warning(f"No chunks extracted from {args.pdf}")
            return
        
        # Index chunks
        await indexer.index_chunks(
            policy_id=args.policy_id,
            source_url=f"file://{args.pdf}",
            chunks=chunks
        )
    
    else:
        logger.error("No action specified. Use --all, --policy, or --pdf")
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
