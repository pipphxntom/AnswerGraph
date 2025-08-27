"""
PDF text extraction and chunking utility.

This module provides functions to extract text from PDFs and split it into
appropriate chunks for embedding and retrieval.
"""
import os
import re
import json
import logging
import tempfile
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
import urllib.request
import tiktoken
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define tokenizer
TOKENIZER = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer

@dataclass
class TextChunk:
    """Represents a chunk of text from a PDF document."""
    text: str
    page: int
    bbox: Dict[str, float]  # x0, y0, x1, y1
    section: str
    language: str = "auto"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


def download_pdf(url: str) -> str:
    """
    Download PDF from URL to a temporary file.
    
    Args:
        url: URL of the PDF to download
        
    Returns:
        Path to the downloaded temporary file
    """
    logger.info(f"Downloading PDF from {url}")
    
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temp_path = temp_file.name
    temp_file.close()
    
    # Download the file
    try:
        urllib.request.urlretrieve(url, temp_path)
        logger.info(f"Downloaded PDF to {temp_path}")
        return temp_path
    except Exception as e:
        # Clean up in case of error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        logger.error(f"Failed to download PDF: {str(e)}")
        raise


def get_pdf_path(source: str) -> str:
    """
    Get local path to PDF file, downloading if it's a URL.
    
    Args:
        source: URL or local path to PDF
        
    Returns:
        Local path to the PDF file
    """
    if source.startswith(("http://", "https://")):
        return download_pdf(source)
    elif os.path.exists(source) and source.lower().endswith(".pdf"):
        return source
    else:
        raise ValueError(f"Invalid source: {source}. Must be a URL or local path to a PDF file.")


def extract_headings(text: str) -> List[Tuple[str, int]]:
    """
    Extract headings and their positions from text.
    
    Args:
        text: Text to extract headings from
        
    Returns:
        List of (heading, position) tuples
    """
    # Pattern for common heading formats
    heading_patterns = [
        r"^#+\s+(.+)$",                    # Markdown headings
        r"^(?:CHAPTER|Section)\s+\d+[\.:]\s*(.+)$",  # Chapter/Section headings
        r"^\d+[\.:]\d*\s+(.+)$",           # Numbered headings like "1.2 Introduction"
        r"^(?:[A-Z][A-Za-z]*\s){1,3}$",    # Short all-caps or title case lines
        r"^[A-Z][A-Z\s]+(?:\([A-Z0-9]+\))?$"  # ALL CAPS headings
    ]
    
    # Combine patterns
    combined_pattern = "|".join(f"({pattern})" for pattern in heading_patterns)
    
    headings = []
    lines = text.split("\n")
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        if re.match(combined_pattern, line, re.MULTILINE):
            # Calculate position in original text
            pos = 0
            for j in range(i):
                pos += len(lines[j]) + 1  # +1 for newline
            headings.append((line, pos))
    
    return headings


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text.
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Number of tokens
    """
    return len(TOKENIZER.encode(text))


def split_text(text: str, headings: List[Tuple[str, int]], 
               min_tokens: int = 200, max_tokens: int = 400) -> List[Tuple[str, str]]:
    """
    Split text into chunks with appropriate headings.
    
    Args:
        text: Text to split
        headings: List of (heading, position) tuples
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        
    Returns:
        List of (chunk_text, section_heading) tuples
    """
    if not text:
        return []
    
    # If no headings found, create artificial sections
    if not headings:
        tokens = count_tokens(text)
        if tokens <= max_tokens:
            return [(text, "Document")]
            
        # Split into roughly equal chunks
        chunks = []
        words = text.split()
        chunk_size = max(1, len(words) // (tokens // min_tokens + 1))
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i+chunk_size])
            if count_tokens(chunk) <= max_tokens:
                chunks.append((chunk, "Document"))
            else:
                # Further split if still too large
                half = len(chunk) // 2
                chunks.append((" ".join(words[i:i+half]), "Document"))
                chunks.append((" ".join(words[i+half:i+chunk_size]), "Document"))
        
        return chunks
    
    # Add document end position
    headings.append(("END", len(text)))
    
    chunks = []
    current_section = "Document"
    
    for i in range(len(headings) - 1):
        # Update current section
        if i > 0:
            current_section = headings[i-1][0]
            
        # Extract text between headings
        start_pos = headings[i][1]
        end_pos = headings[i+1][1]
        section_text = text[start_pos:end_pos]
        
        # Count tokens
        tokens = count_tokens(section_text)
        
        if tokens <= max_tokens:
            # Include section heading with text
            full_text = f"{headings[i][0]}\n\n{section_text}" if i > 0 else section_text
            chunks.append((full_text, current_section))
        else:
            # Split into smaller chunks
            words = section_text.split()
            chunk_size = max(1, len(words) // (tokens // max_tokens + 1))
            
            for j in range(0, len(words), chunk_size):
                chunk_text = " ".join(words[j:j+chunk_size])
                # Add heading to first chunk
                if j == 0 and i > 0:
                    chunk_text = f"{headings[i][0]}\n\n{chunk_text}"
                chunks.append((chunk_text, current_section))
    
    # Remove the artificial end marker
    headings.pop()
    
    return chunks


def extract_pdf_text(pdf_path: str) -> Dict[int, str]:
    """
    Extract text from PDF, organized by page number.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary mapping page numbers to text content
    """
    logger.info(f"Extracting text from {pdf_path}")
    
    text_by_page = {}
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            text_by_page[page_num + 1] = text  # 1-indexed page numbers
            
        logger.info(f"Extracted text from {len(text_by_page)} pages")
        return text_by_page
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise
    finally:
        # Close the document
        if 'doc' in locals():
            doc.close()


def extract_bbox_for_text(page: fitz.Page, text_chunk: str) -> Dict[str, float]:
    """
    Find approximate bounding box for a text chunk.
    
    Args:
        page: PDF page object
        text_chunk: Text to find bounding box for
        
    Returns:
        Dictionary with x0, y0, x1, y1 coordinates
    """
    # Get all text spans on the page
    text_instances = page.search_for(text_chunk[:50]) if len(text_chunk) > 50 else page.search_for(text_chunk)
    
    if text_instances:
        # Use the first match
        return {
            "x0": text_instances[0].x0,
            "y0": text_instances[0].y0,
            "x1": text_instances[0].x1,
            "y1": text_instances[0].y1
        }
    
    # If exact match not found, return page bounds
    return {
        "x0": 0,
        "y0": 0,
        "x1": page.rect.width,
        "y1": page.rect.height
    }


def process_pdf(source: str, min_tokens: int = 200, max_tokens: int = 400) -> List[Dict[str, Any]]:
    """
    Process a PDF file and return chunked text with metadata.
    
    Args:
        source: URL or local path to the PDF file
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        
    Returns:
        List of dictionaries with text chunks and metadata
    """
    # Get PDF path (download if URL)
    pdf_path = get_pdf_path(source)
    temp_file = None
    
    if source.startswith(("http://", "https://")):
        temp_file = pdf_path
    
    try:
        # Extract text by page
        text_by_page = extract_pdf_text(pdf_path)
        
        chunks = []
        doc = fitz.open(pdf_path)
        
        for page_num, text in text_by_page.items():
            # Extract headings from page text
            headings = extract_headings(text)
            
            # Split text into chunks
            page_chunks = split_text(text, headings, min_tokens, max_tokens)
            
            # Get page object for bbox extraction
            page = doc[page_num - 1]  # 0-indexed in PyMuPDF
            
            # Create chunk objects with metadata
            for chunk_text, section in page_chunks:
                bbox = extract_bbox_for_text(page, chunk_text[:100])
                
                chunk = TextChunk(
                    text=chunk_text,
                    page=page_num,
                    bbox=bbox,
                    section=section
                )
                
                chunks.append(chunk.to_dict())
        
        logger.info(f"Created {len(chunks)} text chunks from PDF")
        return chunks
        
    finally:
        # Clean up temporary file if downloaded
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.info(f"Removed temporary file {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_file}: {str(e)}")


def save_chunks_to_json(chunks: List[Dict[str, Any]], output_path: str) -> None:
    """
    Save text chunks to a JSON file.
    
    Args:
        chunks: List of text chunk dictionaries
        output_path: Path to save the JSON file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(chunks)} chunks to {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract and chunk text from PDF files")
    parser.add_argument("source", help="URL or local path to PDF file")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    
    args = parser.parse_args()
    
    # Process the PDF
    chunks = process_pdf(args.source, args.min_tokens, args.max_tokens)
    
    # Save or print results
    if args.output:
        save_chunks_to_json(chunks, args.output)
    else:
        print(json.dumps(chunks, ensure_ascii=False, indent=2))
