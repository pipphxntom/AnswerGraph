"""
Natural language processing module for A2G.

This package contains modules for language detection, 
normalization, and processing of user queries.
"""

from .lang import (
    detect_lang,
    normalize_hinglish,
    pivot_mt,
    process_query
)

__all__ = [
    'detect_lang',
    'normalize_hinglish',
    'pivot_mt',
    'process_query'
]
