"""
Script to seed the database from an Excel file containing policy and procedure data.

This script imports policy and procedure data from an Excel file and stores it
in the database, generating text chunks for RAG.
"""
import argparse
import asyncio
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from src.core.db import async_session, Base, engine
from src.models.source import Source
from src.models.policy import Policy
from src.models.procedure import Procedure
from src.models.chunk import Chunk
from src.ingest.embed_index import index_document_chunks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExcelSeeder:
    """
    Seeds the database with policy and procedure data from Excel files.
    """
    
    def __init__(self, excel_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize the seeder.
        
        Args:
            excel_path: Path to Excel file
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between adjacent chunks
        """
        self.excel_path = excel_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        logger.info(f"Initialized Excel Seeder for {excel_path}")
    
    async def seed_database(self) -> Dict[str, int]:
        """
        Seed database with data from Excel file.
        
        Returns:
            Dictionary with counts of created records
        """
        # Check if file exists
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"Excel file not found: {self.excel_path}")
        
        # Load Excel file
        logger.info(f"Loading Excel file: {self.excel_path}")
        
        # Create async database session
        async with async_session() as session:
            # Create source record
            source = await self._create_source(session)
            
            # Process policies
            policy_count = await self._process_policies(session, source)
            
            # Process procedures
            procedure_count = await self._process_procedures(session, source)
            
            # Commit changes
            await session.commit()
        
        logger.info(f"Successfully seeded database from {self.excel_path}")
        return {
            "sources": 1,
            "policies": policy_count,
            "procedures": procedure_count
        }
    
    async def _create_source(self, session: AsyncSession) -> Source:
        """Create a source record for the Excel file."""
        source = Source(
            name=os.path.basename(self.excel_path),
            description="Imported from Excel file",
            source_type="excel",
            file_path=self.excel_path,
            metadata="{}"
        )
        
        session.add(source)
        await session.flush()
        logger.info(f"Created source record with ID {source.id}")
        
        return source
    
    async def _process_policies(self, session: AsyncSession, source: Source) -> int:
        """
        Process policies from Excel file.
        
        Args:
            session: Database session
            source: Source record
            
        Returns:
            Number of policies created
        """
        try:
            # Load policies sheet
            policies_df = pd.read_excel(self.excel_path, sheet_name="Policies")
            logger.info(f"Found {len(policies_df)} policies in Excel file")
            
            policy_count = 0
            
            for _, row in policies_df.iterrows():
                # Create policy record
                policy = Policy(
                    title=row.get("Title", "Untitled Policy"),
                    description=row.get("Description", ""),
                    policy_number=row.get("PolicyNumber", ""),
                    source_id=source.id
                )
                
                # Handle dates if present
                if "EffectiveDate" in row and pd.notna(row["EffectiveDate"]):
                    policy.effective_date = row["EffectiveDate"]
                
                if "ReviewDate" in row and pd.notna(row["ReviewDate"]):
                    policy.review_date = row["ReviewDate"]
                
                session.add(policy)
                await session.flush()
                
                # Create chunks from content
                if "Content" in row and pd.notna(row["Content"]):
                    content = str(row["Content"])
                    await self._create_chunks(
                        session, content, source.id, policy_id=policy.id
                    )
                
                policy_count += 1
                
                # Log progress
                if policy_count % 10 == 0:
                    logger.info(f"Processed {policy_count} policies")
            
            logger.info(f"Completed processing {policy_count} policies")
            return policy_count
            
        except Exception as e:
            logger.error(f"Error processing policies: {str(e)}")
            return 0
    
    async def _process_procedures(self, session: AsyncSession, source: Source) -> int:
        """
        Process procedures from Excel file.
        
        Args:
            session: Database session
            source: Source record
            
        Returns:
            Number of procedures created
        """
        try:
            # Load procedures sheet
            procedures_df = pd.read_excel(self.excel_path, sheet_name="Procedures")
            logger.info(f"Found {len(procedures_df)} procedures in Excel file")
            
            procedure_count = 0
            
            for _, row in procedures_df.iterrows():
                # Create procedure record
                procedure = Procedure(
                    title=row.get("Title", "Untitled Procedure"),
                    description=row.get("Description", ""),
                    procedure_number=row.get("ProcedureNumber", ""),
                    source_id=source.id
                )
                
                # Handle dates if present
                if "EffectiveDate" in row and pd.notna(row["EffectiveDate"]):
                    procedure.effective_date = row["EffectiveDate"]
                
                if "ReviewDate" in row and pd.notna(row["ReviewDate"]):
                    procedure.review_date = row["ReviewDate"]
                
                session.add(procedure)
                await session.flush()
                
                # Create chunks from content
                if "Content" in row and pd.notna(row["Content"]):
                    content = str(row["Content"])
                    await self._create_chunks(
                        session, content, source.id, procedure_id=procedure.id
                    )
                
                procedure_count += 1
                
                # Log progress
                if procedure_count % 10 == 0:
                    logger.info(f"Processed {procedure_count} procedures")
            
            logger.info(f"Completed processing {procedure_count} procedures")
            return procedure_count
            
        except Exception as e:
            logger.error(f"Error processing procedures: {str(e)}")
            return 0
    
    async def _create_chunks(
        self, 
        session: AsyncSession, 
        content: str, 
        source_id: int, 
        policy_id: Optional[int] = None, 
        procedure_id: Optional[int] = None
    ) -> List[Chunk]:
        """
        Create text chunks from content.
        
        Args:
            session: Database session
            content: Text content to chunk
            source_id: Source ID
            policy_id: Optional policy ID
            procedure_id: Optional procedure ID
            
        Returns:
            List of created chunks
        """
        chunks = []
        content_length = len(content)
        
        # If content is shorter than chunk_size, create a single chunk
        if content_length <= self.chunk_size:
            chunk = Chunk(
                content=content,
                source_id=source_id,
                policy_id=policy_id,
                procedure_id=procedure_id
            )
            session.add(chunk)
            chunks.append(chunk)
            return chunks
        
        # Create overlapping chunks
        start = 0
        while start < content_length:
            end = min(start + self.chunk_size, content_length)
            
            # If not at the end and not a full chunk, try to find a good break point
            if end < content_length and end - start == self.chunk_size:
                # Find the last period, question mark, or paragraph break
                last_break = max(
                    content.rfind('. ', start, end),
                    content.rfind('? ', start, end),
                    content.rfind('! ', start, end),
                    content.rfind('\\n', start, end)
                )
                
                if last_break != -1 and last_break > start + self.chunk_size // 2:
                    end = last_break + 1
            
            chunk_text = content[start:end].strip()
            if chunk_text:  # Only add non-empty chunks
                chunk = Chunk(
                    content=chunk_text,
                    source_id=source_id,
                    policy_id=policy_id,
                    procedure_id=procedure_id
                )
                session.add(chunk)
                chunks.append(chunk)
            
            # Move start position for next chunk, accounting for overlap
            start = end - self.chunk_overlap
            
            # Ensure we make progress even if no good break point
            if start <= 0 or start >= content_length:
                break
        
        return chunks


async def create_tables():
    """Create database tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created (if they didn't exist)")


async def process_chunks_for_embedding():
    """Process all chunks and index them in the vector database."""
    logger.info("Processing chunks for embedding")
    
    async with async_session() as session:
        # Get all chunks that don't have a vector ID
        result = await session.execute(
            select(Chunk).where(Chunk.vector_id.is_(None))
        )
        chunks = result.scalars().all()
        
        if not chunks:
            logger.info("No chunks found for embedding")
            return
        
        logger.info(f"Found {len(chunks)} chunks to embed")
        
        # Convert chunks to dictionary format for embedding
        chunk_dicts = []
        for chunk in chunks:
            chunk_dict = {
                "id": chunk.id,
                "content": chunk.content,
                "source_id": chunk.source_id,
                "policy_id": chunk.policy_id,
                "procedure_id": chunk.procedure_id,
                "page_number": chunk.page_number
            }
            chunk_dicts.append(chunk_dict)
        
        # Index chunks in batches
        batch_size = 100
        for i in range(0, len(chunk_dicts), batch_size):
            batch = chunk_dicts[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {len(chunk_dicts)//batch_size + 1}")
            
            # Index batch
            vector_ids = await index_document_chunks(batch)
            
            # Update chunks with vector IDs
            for j, vector_id in enumerate(vector_ids):
                chunk_id = batch[j]["id"]
                chunk = await session.get(Chunk, chunk_id)
                if chunk:
                    chunk.vector_id = vector_id
            
            await session.commit()
            logger.info(f"Batch {i//batch_size + 1} completed")
    
    logger.info("All chunks have been embedded")


async def main():
    parser = argparse.ArgumentParser(description="Seed database from Excel file")
    parser.add_argument(
        "--excel-file", 
        required=True, 
        help="Path to Excel file with policy/procedure data"
    )
    parser.add_argument(
        "--chunk-size", 
        type=int, 
        default=1000, 
        help="Size of text chunks"
    )
    parser.add_argument(
        "--chunk-overlap", 
        type=int, 
        default=200, 
        help="Overlap between adjacent chunks"
    )
    parser.add_argument(
        "--skip-embedding", 
        action="store_true", 
        help="Skip embedding chunks in vector database"
    )
    
    args = parser.parse_args()
    
    # Create tables if they don't exist
    await create_tables()
    
    # Seed database
    seeder = ExcelSeeder(
        excel_path=args.excel_file,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    
    result = await seeder.seed_database()
    logger.info(f"Seeding complete: {result}")
    
    # Process chunks for embedding
    if not args.skip_embedding:
        await process_chunks_for_embedding()
    else:
        logger.info("Skipping chunk embedding as requested")


if __name__ == "__main__":
    asyncio.run(main())
