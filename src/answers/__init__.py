"""
Answer generation module for A2G.

This package contains modules for generating answers 
through both rule-based and RAG-based approaches.
"""

from .rules_path import (
    answer_from_rules,
    NoAnswer,
    AnswerContract
)

__all__ = [
    'answer_from_rules',
    'NoAnswer',
    'AnswerContract'
]
