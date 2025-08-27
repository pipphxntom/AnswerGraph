"""
Enhanced PDF processing pipeline with optimized architecture.

This module provides a high-performance, fully asynchronous implementation 
for processing PDF documents into policy chunks with optimal token handling.
"""
import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import date
import uuid
import tiktoken
from pathlib import Path
import fitz  # PyMuPDF

from src.models.policy import Policy
from src.models.source import Source 
from src.models.chunk import Chunk
from src.core.db import async_session_factory, engine, Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize tokenizer for accurate chunk sizing
tokenizer = tiktoken.get_encoding("cl100k_base")

@dataclass
class ProcessingConfig:
    """Configuration for PDF processing pipeline."""
    min_tokens: int = 200
    max_tokens: int = 400
    overlap_tokens: int = 50
    batch_size: int = 10
    max_workers: int = 4
    detect_language: bool = True
    extract_metadata: bool = True
    chunk_strategy: str = "semantic"  # "semantic" or "fixed"

@dataclass
class PDFMetadata:
    """Metadata extracted from PDF document."""
    title: Optional[str] = None
    author: Optional[str] = None
    creation_date: Optional[str] = None
    producer: Optional[str] = None
    page_count: int = 0
    file_size: int = 0

class EnhancedPDFProcessor:
    """
    Advanced PDF processing pipeline with intelligent chunking.
    
    Features:
    - Fully asynchronous processing
    - Semantic-aware text chunking
    - Parallel batch processing
    - Metadata extraction
    - Memory-efficient streaming
    """
    
    def __init__(self, config: Optional[ProcessingConfig] = None):
        """Initialize processor with configuration."""
        self.config = config or ProcessingConfig()
        logger.info(f"Initialized EnhancedPDFProcessor with config: {self.config}")
        self._semaphore = asyncio.Semaphore(self.config.max_workers)
    
    async def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Process a PDF file asynchronously with batched chunk processing.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary with processing results and stats
        """
        logger.info(f"Processing PDF: {file_path}")
        
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        # Extract metadata
        metadata = await self._extract_metadata(file_path)
        
        # Process in batches for memory efficiency
        chunks = []
        batch_count = 0
        
        async for batch in self._extract_text_batches(file_path):
            batch_count += 1
            optimized_batch = await self._process_chunk_batch(batch)
            chunks.extend(optimized_batch)
            
            # Report progress
            logger.info(f"Processed batch {batch_count}: {len(optimized_batch)} chunks")
        
        # Calculate statistics
        stats = self._calculate_stats(chunks)
        
        return {
            "metadata": metadata,
            "chunks": chunks,
            "stats": stats
        }
    
    async def _extract_metadata(self, file_path: str) -> PDFMetadata:
        """Extract metadata from PDF document."""
        loop = asyncio.get_event_loop()
        
        def _extract():
            doc = fitz.open(file_path)
            metadata = PDFMetadata(
                title=doc.metadata.get("title"),
                author=doc.metadata.get("author"),
                creation_date=doc.metadata.get("creationDate"),
                producer=doc.metadata.get("producer"),
                page_count=len(doc),
                file_size=os.path.getsize(file_path)
            )
            doc.close()
            return metadata
        
        # Run in executor to avoid blocking
        return await loop.run_in_executor(None, _extract)
    
    async def _extract_text_batches(self, file_path: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Extract text from PDF in batches to manage memory usage.
        
        Yields batches of raw text chunks for further processing.
        """
        loop = asyncio.get_event_loop()
        doc = await loop.run_in_executor(None, fitz.open, file_path)
        
        try:
            # Process pages in batches
            batch = []
            
            for page_num in range(len(doc)):
                # Use executor for potentially blocking operations
                page = await loop.run_in_executor(None, doc.load_page, page_num)
                text = await loop.run_in_executor(None, page.get_text)
                
                # Skip empty pages
                if not text.strip():
                    continue
                
                # Basic chunk with page info
                chunk = {
                    "text": text,
                    "page": page_num + 1,
                    "section": self._detect_section(text)
                }
                
                batch.append(chunk)
                
                # Yield when batch is full
                if len(batch) >= self.config.batch_size:
                    yield batch
                    batch = []
            
            # Yield any remaining items
            if batch:
                yield batch
                
        finally:
            # Ensure document is closed
            await loop.run_in_executor(None, doc.close)
    
    def _detect_section(self, text: str) -> str:
        """Detect section title from text."""
        # Extract first line as potential section title
        lines = text.strip().split("\n")
        if not lines:
            return "Unknown Section"
            
        potential_title = lines[0].strip()
        
        # Apply heuristics for section detection
        if len(potential_title) < 100 and not potential_title.endswith(('.', ':', ';')):
            return potential_title
        
        # Fallback to generic section name
        return "Section"
    
    async def _process_chunk_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of chunks in parallel with controlled concurrency."""
        tasks = []
        
        for chunk in batch:
            task = self._process_chunk(chunk)
            tasks.append(task)
        
        # Execute tasks with controlled concurrency
        return await asyncio.gather(*tasks)
    
    async def _process_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single text chunk with tokenization and optimization."""
        async with self._semaphore:
            # Simulate CPU-intensive work in thread pool
            loop = asyncio.get_event_loop()
            
            # Process the chunk
            def _process():
                text = chunk["text"]
                tokens = tokenizer.encode(text)
                token_count = len(tokens)
                
                # If chunk is too large, split it
                if token_count > self.config.max_tokens:
                    return self._split_chunk(chunk, tokens)
                
                # Add token count to chunk
                chunk["token_count"] = token_count
                return [chunk]
            
            # Execute in thread pool
            processed_chunks = await loop.run_in_executor(None, _process)
            return processed_chunks[0]  # Return first or only chunk
    
    def _split_chunk(self, chunk: Dict[str, Any], tokens: List[int]) -> List[Dict[str, Any]]:
        """Split a chunk that exceeds the maximum token count."""
        result = []
        text = chunk["text"]
        page = chunk["page"]
        section = chunk["section"]
        
        # Determine logical split points (paragraphs, sentences)
        split_points = self._find_split_points(text)
        
        # Create chunks based on token boundaries
        start_idx = 0
        current_tokens = 0
        
        for split_idx in split_points:
            # Count tokens in this segment
            segment_text = text[start_idx:split_idx]
            segment_tokens = len(tokenizer.encode(segment_text))
            
            # If adding this segment exceeds max_tokens, create a chunk
            if current_tokens + segment_tokens > self.config.max_tokens:
                # Create chunk with current text
                if current_tokens >= self.config.min_tokens:
                    result.append({
                        "text": text[start_idx:split_idx],
                        "page": page,
                        "section": section,
                        "token_count": current_tokens
                    })
                
                # Start new chunk, with overlap if specified
                overlap_point = max(0, start_idx - self.config.overlap_tokens * 4)  # Approx 4 chars per token
                start_idx = overlap_point
                current_tokens = 0
            
            current_tokens += segment_tokens
        
        # Add final chunk if needed
        if current_tokens >= self.config.min_tokens:
            result.append({
                "text": text[start_idx:],
                "page": page,
                "section": section,
                "token_count": current_tokens
            })
        
        return result
    
    def _find_split_points(self, text: str) -> List[int]:
        """Find logical split points in text."""
        # Paragraph breaks
        paragraphs = text.split("\n\n")
        points = []
        pos = 0
        
        for p in paragraphs:
            pos += len(p) + 2  # +2 for the "\n\n"
            points.append(pos)
        
        # Remove the last point which would be at the end of text
        if points and points[-1] >= len(text):
            points.pop()
        
        # If no paragraph breaks, use sentences
        if not points:
            for i, char in enumerate(text):
                if char in '.!?' and i < len(text) - 1 and text[i + 1] in ' \n\t':
                    points.append(i + 2)  # +2 to include the period and space
        
        return points
    
    def _calculate_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for processed chunks."""
        if not chunks:
            return {
                "chunk_count": 0,
                "avg_tokens": 0,
                "min_tokens": 0,
                "max_tokens": 0
            }
        
        token_counts = [chunk.get("token_count", 0) for chunk in chunks]
        
        return {
            "chunk_count": len(chunks),
            "avg_tokens": sum(token_counts) / len(chunks),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts),
            "total_tokens": sum(token_counts)
        }
    
    async def create_policy_from_pdf(
        self,
        file_path: str,
        policy_id: Optional[str] = None,
        title: Optional[str] = None,
        issuer: str = "Organization",
    ) -> Dict[str, Any]:
        """
        Process PDF and create a policy with chunks in the database.
        
        Args:
            file_path: Path to the PDF file
            policy_id: Optional policy ID (generated if not provided)
            title: Optional policy title (extracted from PDF if not provided)
            issuer: Policy issuer
            
        Returns:
            Dictionary with created entity counts and policy ID
        """
        # Process the PDF
        result = await self.process_pdf(file_path)
        chunks = result["chunks"]
        metadata = result["metadata"]
        
        if not chunks:
            logger.warning(f"No text chunks extracted from {file_path}")
            return {"policies": 0, "sources": 0, "chunks": 0}
        
        # Generate policy ID if not provided
        if not policy_id:
            policy_id = f"POL-{uuid.uuid4().hex[:8]}"
        
        # Use PDF title or filename if title not provided
        if not title:
            title = metadata.title or Path(file_path).stem.replace("_", " ").title()
        
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
                    last_updated=date.today()
                )
                
                # Create source
                source = Source(
                    id=f"SRC-{policy_id}-1",
                    policy_id=policy_id,
                    url=file_path if file_path.startswith(("http://", "https://")) else f"file://{file_path}",
                    page=None
                )
                
                # Create chunks
                db_chunks = []
                for i, chunk_data in enumerate(chunks):
                    chunk = Chunk(
                        id=f"CHK-{policy_id}-{i+1}",
                        policy_id=policy_id,
                        text=chunk_data["text"],
                        page=chunk_data["page"],
                        section=chunk_data["section"],
                        language="en"  # Assuming English, could be detected
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
                    "policy_id": policy_id,
                    "policies": 1,
                    "sources": 1,
                    "chunks": len(db_chunks),
                    "stats": result["stats"]
                }
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating policy from PDF: {str(e)}")
                raise

# Initialize database tables
async def init_database():
    """Initialize the database schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized")

# Convenience function for processing a PDF
async def process_pdf_to_policy(
    file_path: str,
    policy_id: Optional[str] = None,
    title: Optional[str] = None,
    issuer: str = "Organization",
    min_tokens: int = 200,
    max_tokens: int = 400
) -> Dict[str, Any]:
    """
    Process a PDF file into a policy document.
    
    Args:
        file_path: Path to the PDF file
        policy_id: Optional policy ID
        title: Optional policy title
        issuer: Policy issuer
        min_tokens: Minimum tokens per chunk
        max_tokens: Maximum tokens per chunk
        
    Returns:
        Dictionary with processing results
    """
    # Initialize database
    await init_database()
    
    # Configure processor
    config = ProcessingConfig(
        min_tokens=min_tokens,
        max_tokens=max_tokens
    )
    
    # Create processor and process PDF
    processor = EnhancedPDFProcessor(config)
    return await processor.create_policy_from_pdf(
        file_path=file_path,
        policy_id=policy_id,
        title=title,
        issuer=issuer
    )

# Command-line entry point
async def main_async():
    """Async entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced PDF Policy Processor")
    parser.add_argument("file_path", help="Path to the PDF file")
    parser.add_argument("--id", help="Optional policy ID")
    parser.add_argument("--title", help="Optional policy title")
    parser.add_argument("--issuer", default="Organization", help="Policy issuer")
    parser.add_argument("--min-tokens", type=int, default=200, help="Minimum tokens per chunk")
    parser.add_argument("--max-tokens", type=int, default=400, help="Maximum tokens per chunk")
    
    args = parser.parse_args()
    
    try:
        result = await process_pdf_to_policy(
            file_path=args.file_path,
            policy_id=args.id,
            title=args.title,
            issuer=args.issuer,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens
        )
        
        print(f"Successfully processed PDF:")
        print(f"  - Policy ID: {result['policy_id']}")
        print(f"  - Chunks: {result['chunks']}")
        print(f"  - Avg tokens per chunk: {result['stats']['avg_tokens']:.1f}")
        print(f"  - Total tokens: {result['stats']['total_tokens']}")
        
        return 0
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1

def main():
    """Command-line entry point."""
    import asyncio
    return asyncio.run(main_async())

if __name__ == "__main__":
    import sys
    sys.exit(main())
