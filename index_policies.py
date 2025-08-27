#!/usr/bin/env python
"""
Index Policy Documents in Qdrant

This script processes and indexes policy documents in Qdrant using the BGE-M3 embedding model.
It can process all PDF sources in the database or specific policies/files.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.ingest.embedding_indexer import EmbeddingIndexer, index_all_policy_sources

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


async def index_policies():
    """Main async function for indexing policies."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Index policy documents in Qdrant")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Index all sources command
    all_parser = subparsers.add_parser("all", help="Index all sources in database")
    all_parser.add_argument("--collection", help="Qdrant collection name")
    
    # Index policy command
    policy_parser = subparsers.add_parser("policy", help="Index sources for specific policy ID")
    policy_parser.add_argument("policy_id", help="Policy ID to index")
    policy_parser.add_argument("--collection", help="Qdrant collection name")
    
    # Index PDF command
    pdf_parser = subparsers.add_parser("pdf", help="Index a specific PDF file")
    pdf_parser.add_argument("pdf_path", help="Path to the PDF file")
    pdf_parser.add_argument("--policy-id", required=True, help="Policy ID to associate with the PDF")
    pdf_parser.add_argument("--collection", help="Qdrant collection name")
    
    # Initialize collection command
    init_parser = subparsers.add_parser("init", help="Initialize Qdrant collection")
    init_parser.add_argument("--collection", help="Qdrant collection name")
    
    args = parser.parse_args()
    
    # Create indexer
    collection_name = args.collection if hasattr(args, "collection") and args.collection else "a2g_chunks"
    indexer = EmbeddingIndexer(collection_name=collection_name)
    
    if args.command == "all":
        # Process all sources
        logger.info("Indexing all policy sources")
        await index_all_policy_sources()
        
    elif args.command == "policy":
        # Process sources for specific policy
        from src.core.db import get_session
        from src.models.source import Source
        
        logger.info(f"Indexing sources for policy {args.policy_id}")
        
        async for session in get_session():
            sources = await session.query(Source).filter(Source.policy_id == args.policy_id).all()
            
            if not sources:
                logger.warning(f"No sources found for policy {args.policy_id}")
                return
            
            logger.info(f"Found {len(sources)} sources for policy {args.policy_id}")
            
            for source in sources:
                # Extract URL
                url = source.url
                if url.startswith("file://"):
                    url = url[7:]
                
                if not os.path.exists(url) and not url.startswith(("http://", "https://")):
                    logger.warning(f"Source file not found: {url}")
                    continue
                
                # Process PDF into chunks
                from src.ingest.pdf.extractor import process_pdf
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
                
                logger.info(f"Successfully indexed source {source.id}")
    
    elif args.command == "pdf":
        # Process a specific PDF file
        if not os.path.exists(args.pdf_path):
            logger.error(f"PDF file not found: {args.pdf_path}")
            return
        
        logger.info(f"Indexing PDF {args.pdf_path} for policy {args.policy_id}")
        
        # Process PDF into chunks
        from src.ingest.pdf.extractor import process_pdf
        chunks = process_pdf(args.pdf_path, min_tokens=200, max_tokens=400)
        
        if not chunks:
            logger.warning(f"No chunks extracted from {args.pdf_path}")
            return
        
        logger.info(f"Extracted {len(chunks)} chunks from {args.pdf_path}")
        
        # Index chunks
        await indexer.index_chunks(
            policy_id=args.policy_id,
            source_url=f"file://{args.pdf_path}",
            chunks=chunks
        )
        
        logger.info(f"Successfully indexed PDF {args.pdf_path}")
    
    elif args.command == "init":
        # Initialize collection
        logger.info(f"Initializing Qdrant collection: {collection_name}")
        client = indexer.connect_qdrant()
        created = indexer.ensure_collection(client, collection_name)
        
        if created:
            logger.info(f"Created collection {collection_name}")
        else:
            logger.info(f"Collection {collection_name} already exists")
    
    else:
        logger.error("No command specified")
        parser.print_help()
        return 1
    
    logger.info("Indexing complete")
    return 0


def main():
    """Command-line entry point."""
    try:
        return asyncio.run(index_policies())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
