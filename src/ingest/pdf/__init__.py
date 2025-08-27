"""
Package initialization for PDF extraction module.
"""
from .extractor import process_pdf, save_chunks_to_json, TextChunk

__all__ = ["process_pdf", "save_chunks_to_json", "TextChunk"]
