"""PDF document chunking module for RAG."""
from typing import Dict, List, Any, Optional
import logging
import fitz  # PyMuPDF
import re
import regex
from python_bidi import algorithm as bidi_algorithm

logger = logging.getLogger(__name__)

class PDFChunker:
    """
    Extract and chunk content from PDF documents for RAG ingestion.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.chunk_size = self.config.get("chunk_size", 1000)
        self.chunk_overlap = self.config.get("chunk_overlap", 200)
        logger.info(f"Initialized PDF Chunker with chunk_size={self.chunk_size}, overlap={self.chunk_overlap}")
    
    async def process_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Process a PDF file and extract chunked content.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            List of chunk dictionaries with content and metadata
        """
        logger.info(f"Processing PDF: {file_path}")
        chunks = []
        
        try:
            # Open the PDF
            document = fitz.open(file_path)
            
            # Process each page
            for page_num, page in enumerate(document):
                text = page.get_text()
                
                # Handle RTL text if present
                text = self._handle_rtl_text(text)
                
                # Clean the text
                clean_text = self._clean_text(text)
                
                # Create chunks from the page
                page_chunks = self._create_chunks(clean_text, page_num + 1)
                chunks.extend(page_chunks)
                
            document.close()
            logger.info(f"Created {len(chunks)} chunks from {file_path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
    
    def _handle_rtl_text(self, text: str) -> str:
        """Handle right-to-left text if present."""
        # Use python-bidi to handle RTL text
        return bidi_algorithm.get_display(text)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\\s+', ' ', text)
        # Remove page numbers, headers, footers, etc. as needed
        # ...
        return text.strip()
    
    def _create_chunks(self, text: str, page_num: int) -> List[Dict[str, Any]]:
        """
        Create overlapping chunks from text.
        
        Args:
            text: The text to chunk
            page_num: Page number for metadata
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        text_length = len(text)
        
        # If text is shorter than chunk_size, return as single chunk
        if text_length <= self.chunk_size:
            return [{
                "content": text,
                "page_number": page_num,
                "start_char": 0,
                "end_char": text_length
            }]
        
        # Create overlapping chunks
        start = 0
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            
            # If not at the end and not a full chunk, try to find a good break point
            if end < text_length and end - start == self.chunk_size:
                # Find the last period, question mark, or paragraph break
                last_break = max(
                    text.rfind('. ', start, end),
                    text.rfind('? ', start, end),
                    text.rfind('! ', start, end),
                    text.rfind('\\n', start, end)
                )
                
                if last_break != -1 and last_break > start + self.chunk_size // 2:
                    end = last_break + 1
            
            chunk_text = text[start:end].strip()
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    "content": chunk_text,
                    "page_number": page_num,
                    "start_char": start,
                    "end_char": end
                })
            
            # Move start position for next chunk, accounting for overlap
            start = end - self.chunk_overlap
            
            # Ensure we make progress even if no good break point
            if start <= 0 or start >= text_length:
                break
        
        return chunks
