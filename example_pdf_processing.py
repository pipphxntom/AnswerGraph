"""
PDF Policy Processing Example

This script demonstrates how to use the PDF policy processor
to extract and load policy documents into the database.
"""
import asyncio
import os
import sys
from datetime import date

# Add the project root to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ingest.pdf.policy_processor import create_policy_from_pdf
from src.ingest.pdf.extractor import process_pdf, save_chunks_to_json


async def example_process_pdf():
    """
    Example of processing a PDF file into a policy document.
    
    This function demonstrates:
    1. Extract text chunks from a PDF
    2. Save chunks to JSON for inspection
    3. Create a policy in the database with chunks
    """
    # Replace with the path to your PDF file
    pdf_path = "path/to/your/policy.pdf"
    
    # Check if the file exists
    if not os.path.exists(pdf_path):
        print(f"ERROR: File {pdf_path} does not exist.")
        print("Please update the pdf_path variable in this script.")
        return
    
    print(f"Processing PDF: {pdf_path}")
    
    # Step 1: Extract text chunks from the PDF
    chunks = process_pdf(
        pdf_path,
        min_tokens=200,
        max_tokens=400
    )
    
    print(f"Extracted {len(chunks)} text chunks from PDF")
    
    # Step 2: Save chunks to JSON for inspection (optional)
    json_path = "extracted_chunks.json"
    save_chunks_to_json(chunks, json_path)
    print(f"Saved chunks to {json_path} for inspection")
    
    # Step 3: Create a policy in the database
    result = await create_policy_from_pdf(
        pdf_path,
        policy_id="POL-EXAMPLE-001",
        title="Example Policy Document",
        issuer="Example Organization",
        min_tokens=200,
        max_tokens=400
    )
    
    print(f"Created policy with {result['chunks']} chunks in database")
    print("Success! The policy is now ready for retrieval in the RAG system.")


if __name__ == "__main__":
    # Run the example
    asyncio.run(example_process_pdf())
