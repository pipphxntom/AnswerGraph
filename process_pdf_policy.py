#!/usr/bin/env python
"""
PDF Policy Processor - Command-line interface

This script provides a simple interface to process PDF files into policy documents
and load them into the database.
"""
import os
import sys
import asyncio
import argparse
import logging
from typing import Optional, List

from src.ingest.pdf.policy_processor import create_policy_from_pdf, process_pdf_directory
from src.ingest.pdf.extractor import process_pdf, save_chunks_to_json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process PDF files into policy documents and chunks"
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Single PDF command
    pdf_parser = subparsers.add_parser("pdf", help="Process a single PDF file")
    pdf_parser.add_argument("pdf_path", help="Path or URL to the PDF file")
    pdf_parser.add_argument("--id", help="Optional policy ID")
    pdf_parser.add_argument("--title", help="Optional policy title")
    pdf_parser.add_argument("--issuer", default="Organization", help="Policy issuer")
    pdf_parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    pdf_parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    pdf_parser.add_argument("--output", "-o", help="Save chunks to JSON file")
    pdf_parser.add_argument("--skip-db", action="store_true", help="Skip database loading (JSON only)")
    
    # Directory command
    dir_parser = subparsers.add_parser("dir", help="Process all PDFs in a directory")
    dir_parser.add_argument("directory", help="Directory containing PDF files")
    dir_parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    dir_parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    dir_parser.add_argument("--issuer", default="Organization", help="Policy issuer")
    
    # View chunks command
    view_parser = subparsers.add_parser("view", help="View chunks from a PDF without storing")
    view_parser.add_argument("pdf_path", help="Path or URL to the PDF file")
    view_parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    view_parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    view_parser.add_argument("--output", "-o", help="Save chunks to JSON file")
    view_parser.add_argument("--count", "-c", action="store_true", help="Only show chunk count and stats")
    
    return parser.parse_args()


async def process_single_pdf(args):
    """Process a single PDF file."""
    try:
        # Extract chunks from PDF
        chunks = process_pdf(args.pdf_path, args.min_tokens, args.max_tokens)
        
        if not chunks:
            logger.error(f"No text extracted from {args.pdf_path}")
            return 1
            
        logger.info(f"Extracted {len(chunks)} text chunks from {args.pdf_path}")
        
        # Save chunks to JSON if requested
        if args.output:
            save_chunks_to_json(chunks, args.output)
            logger.info(f"Saved chunks to {args.output}")
        
        # Skip database if requested
        if args.skip_db:
            return 0
            
        # Create policy in database
        result = await create_policy_from_pdf(
            args.pdf_path,
            policy_id=args.id,
            title=args.title,
            issuer=args.issuer,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens
        )
        
        logger.info(f"Created policy with {result['chunks']} chunks in database")
        return 0
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return 1


async def process_directory(args):
    """Process all PDFs in a directory."""
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
            
        return 0
        
    except Exception as e:
        logger.error(f"Error processing directory: {str(e)}")
        return 1


async def view_pdf_chunks(args):
    """View chunks from a PDF without storing in database."""
    try:
        # Extract chunks from PDF
        chunks = process_pdf(args.pdf_path, args.min_tokens, args.max_tokens)
        
        if not chunks:
            logger.error(f"No text extracted from {args.pdf_path}")
            return 1
        
        # Save to JSON if requested
        if args.output:
            save_chunks_to_json(chunks, args.output)
            logger.info(f"Saved chunks to {args.output}")
        
        # Only show count and stats if requested
        if args.count:
            # Calculate token statistics
            import tiktoken
            tokenizer = tiktoken.get_encoding("cl100k_base")
            token_counts = [len(tokenizer.encode(c["text"])) for c in chunks]
            avg_tokens = sum(token_counts) / len(token_counts)
            min_tokens = min(token_counts)
            max_tokens = max(token_counts)
            
            logger.info(f"PDF: {args.pdf_path}")
            logger.info(f"Total chunks: {len(chunks)}")
            logger.info(f"Token statistics:")
            logger.info(f"  - Average: {avg_tokens:.1f} tokens per chunk")
            logger.info(f"  - Minimum: {min_tokens} tokens")
            logger.info(f"  - Maximum: {max_tokens} tokens")
        else:
            # Print summary of each chunk
            for i, chunk in enumerate(chunks):
                logger.info(f"Chunk {i+1}:")
                logger.info(f"  - Page: {chunk['page']}")
                logger.info(f"  - Section: {chunk['section']}")
                logger.info(f"  - Text preview: {chunk['text'][:100]}...")
                logger.info("")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error viewing PDF chunks: {str(e)}")
        return 1


async def main_async():
    """Async entry point."""
    args = parse_args()
    
    if args.command == "pdf":
        return await process_single_pdf(args)
    elif args.command == "dir":
        return await process_directory(args)
    elif args.command == "view":
        return await view_pdf_chunks(args)
    else:
        logger.error("No command specified. Use --help for usage information.")
        return 1


def main():
    """Command-line entry point."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
