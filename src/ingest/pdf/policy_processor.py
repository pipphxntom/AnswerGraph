"""
PDF policy processor for A2G.

This module integrates PDF text extraction with policy creation and database loading.
"""
import os
import json
import logging
import argparse
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.ingest.pdf.extractor import process_pdf, save_chunks_to_json
from src.models.policy import Policy
from src.models.source import Source
from src.models.chunk import Chunk
from src.core.db import async_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_policy_from_pdf(
    pdf_path: str,
    policy_id: Optional[str] = None,
    title: Optional[str] = None,
    issuer: str = "Unknown",
    min_tokens: int = 200,
    max_tokens: int = 400
) -> Dict[str, Any]:
    """
    Process a PDF and create a policy with chunks in the database.
    
    Args:
        pdf_path: Path or URL to the PDF file
        policy_id: Optional policy ID (generated if not provided)
        title: Optional policy title (extracted from PDF if not provided)
        issuer: Policy issuer
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        
    Returns:
        Dictionary with created entity counts
    """
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Process the PDF to get chunks
    chunks = process_pdf(pdf_path, min_tokens, max_tokens)
    
    if not chunks:
        logger.warning(f"No text chunks extracted from {pdf_path}")
        return {"policies": 0, "sources": 0, "chunks": 0}
    
    # Generate policy ID if not provided
    if not policy_id:
        from uuid import uuid4
        policy_id = f"POL-{uuid4().hex[:8]}"
    
    # Use first chunk section as title if not provided
    if not title and chunks:
        title = chunks[0].get("section", "Untitled Policy")
    
    # Create full text by joining all chunks
    full_text = "\n\n".join(chunk["text"] for chunk in chunks)
    
    # Database operations
    async with async_session_factory() as session:
        try:
            # Create policy
            policy = Policy(
                id=policy_id,
                title=title,
                issuer=issuer,
                text_full=full_text,
                last_updated=datetime.now().date()
            )
            
            # Create source
            source = Source(
                id=f"SRC-{policy_id}-1",
                policy_id=policy_id,
                url=pdf_path if pdf_path.startswith(("http://", "https://")) else f"file://{pdf_path}",
                page=None,
                bbox={}
            )
            
            # Create chunks
            db_chunks = []
            for i, chunk_data in enumerate(chunks):
                chunk = Chunk(
                    id=f"CHK-{policy_id}-{i+1}",
                    policy_id=policy_id,
                    source_id=source.id,
                    procedure_id=None,
                    text=chunk_data["text"],
                    page=chunk_data["page"],
                    bbox=chunk_data["bbox"],
                    section=chunk_data["section"],
                    embedding=None  # Will be computed separately
                )
                db_chunks.append(chunk)
            
            # Add to session
            session.add(policy)
            session.add(source)
            for chunk in db_chunks:
                session.add(chunk)
            
            # Commit changes
            await session.commit()
            
            logger.info(f"Successfully created policy {policy_id} with {len(db_chunks)} chunks")
            
            return {
                "policies": 1,
                "sources": 1,
                "chunks": len(db_chunks)
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating policy from PDF: {str(e)}")
            raise


async def process_pdf_directory(
    directory: str,
    min_tokens: int = 200,
    max_tokens: int = 400
) -> Dict[str, int]:
    """
    Process all PDFs in a directory and create policies.
    
    Args:
        directory: Directory containing PDF files
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        
    Returns:
        Dictionary with created entity counts
    """
    logger.info(f"Processing PDFs in directory: {directory}")
    
    if not os.path.isdir(directory):
        raise ValueError(f"Directory does not exist: {directory}")
    
    # Find all PDF files in the directory
    pdf_files = [os.path.join(directory, f) for f in os.listdir(directory) 
                if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {directory}")
        return {"policies": 0, "sources": 0, "chunks": 0, "errors": 0}
    
    # Process each PDF
    counts = {"policies": 0, "sources": 0, "chunks": 0, "errors": 0}
    
    for pdf_file in pdf_files:
        try:
            # Generate title from filename
            title = os.path.splitext(os.path.basename(pdf_file))[0].replace('_', ' ').title()
            
            # Process PDF
            result = await create_policy_from_pdf(
                pdf_file,
                title=title,
                min_tokens=min_tokens,
                max_tokens=max_tokens
            )
            
            # Update counts
            counts["policies"] += result["policies"]
            counts["sources"] += result["sources"]
            counts["chunks"] += result["chunks"]
            
            logger.info(f"Processed {pdf_file}")
            
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {str(e)}")
            counts["errors"] += 1
    
    return counts


async def main_async():
    """Async entry point for the command-line tool."""
    parser = argparse.ArgumentParser(description="Process PDFs and create policies")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Process single PDF command
    pdf_parser = subparsers.add_parser("process", help="Process a single PDF file")
    pdf_parser.add_argument("pdf_path", help="Path or URL to the PDF file")
    pdf_parser.add_argument("--policy-id", help="Optional policy ID")
    pdf_parser.add_argument("--title", help="Optional policy title")
    pdf_parser.add_argument("--issuer", default="Unknown", help="Policy issuer")
    pdf_parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    pdf_parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    pdf_parser.add_argument("--output", "-o", help="Output JSON file for chunks")
    
    # Process directory command
    dir_parser = subparsers.add_parser("process-dir", help="Process all PDFs in a directory")
    dir_parser.add_argument("directory", help="Directory containing PDF files")
    dir_parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    dir_parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    
    args = parser.parse_args()
    
    if args.command == "process":
        # Process a single PDF
        try:
            # Extract chunks from PDF
            chunks = process_pdf(args.pdf_path, args.min_tokens, args.max_tokens)
            
            # Save chunks to JSON if output specified
            if args.output:
                save_chunks_to_json(chunks, args.output)
                logger.info(f"Saved {len(chunks)} chunks to {args.output}")
            
            # Create policy in database
            result = await create_policy_from_pdf(
                args.pdf_path,
                policy_id=args.policy_id,
                title=args.title,
                issuer=args.issuer,
                min_tokens=args.min_tokens,
                max_tokens=args.max_tokens
            )
            
            logger.info(f"Successfully created policy with {result['chunks']} chunks")
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return 1
    
    elif args.command == "process-dir":
        # Process all PDFs in a directory
        try:
            counts = await process_pdf_directory(
                args.directory,
                min_tokens=args.min_tokens,
                max_tokens=args.max_tokens
            )
            
            logger.info(f"Processing complete:")
            logger.info(f"  - Policies created: {counts['policies']}")
            logger.info(f"  - Sources created: {counts['sources']}")
            logger.info(f"  - Chunks created: {counts['chunks']}")
            
            if counts["errors"] > 0:
                logger.warning(f"  - Errors: {counts['errors']}")
                return 1
                
        except Exception as e:
            logger.error(f"Error processing directory: {str(e)}")
            return 1
    
    else:
        parser.print_help()
        return 1
    
    return 0


def main():
    """Command-line entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    import sys
    sys.exit(main())
