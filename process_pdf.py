"""
Command-line tool for PDF extraction and chunking.

This script provides a command-line interface for extracting text from PDFs
and splitting it into chunks suitable for embedding and retrieval.
"""
import os
import sys
import argparse
import logging
from src.ingest.pdf.extractor import process_pdf, save_chunks_to_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Extract and chunk text from PDF files")
    parser.add_argument("source", help="URL or local path to PDF file")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    
    args = parser.parse_args()
    
    try:
        # Process the PDF
        chunks = process_pdf(args.source, args.min_tokens, args.max_tokens)
        
        # Determine output path if not specified
        if not args.output:
            if os.path.isfile(args.source):
                base_name = os.path.splitext(os.path.basename(args.source))[0]
                args.output = f"{base_name}_chunks.json"
            else:
                args.output = "pdf_chunks.json"
        
        # Save results
        save_chunks_to_json(chunks, args.output)
        logger.info(f"Successfully processed PDF and saved {len(chunks)} chunks to {args.output}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
