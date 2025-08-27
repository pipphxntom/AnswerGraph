import os
import pytest
from src.ingest.pdf.extractor import process_pdf

def test_process_pdf_sample():
    # Use a sample PDF file for testing
    sample_pdf = os.path.join(os.path.dirname(__file__), "sample.pdf")
    if not os.path.exists(sample_pdf):
        pytest.skip("sample.pdf not found")
    chunks = process_pdf(sample_pdf, min_tokens=200, max_tokens=400)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    for chunk in chunks:
        assert "text" in chunk
        assert "page" in chunk
        assert "section" in chunk
        assert isinstance(chunk["text"], str)
        assert isinstance(chunk["page"], int)
        assert isinstance(chunk["section"], str)
