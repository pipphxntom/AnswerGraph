"""
Additional guard functions for the guards module.

This module provides additional guard functions that are referenced in
the apply_guards function but were not implemented in the original guards.py.
"""
import datetime
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def staleness_guard(source_date: str, max_age_days: int = 365) -> Tuple[bool, str]:
    """
    Check if a source is too old to be reliable.
    
    Args:
        source_date: ISO format date string of the source
        max_age_days: Maximum age in days for a source to be considered fresh
        
    Returns:
        Tuple of (passed, message) where passed is True if the guard passes
    """
    if not source_date:
        return False, "Source date is missing"
    
    try:
        # Parse the date string
        if 'T' in source_date:
            # ISO format with time
            source_datetime = datetime.datetime.fromisoformat(source_date)
        else:
            # Date-only format
            source_datetime = datetime.datetime.strptime(source_date, "%Y-%m-%d")
        
        source_date = source_datetime.date()
        today = datetime.datetime.now().date()
        
        # Calculate age in days
        age_days = (today - source_date).days
        
        if age_days <= max_age_days:
            return True, f"Source is {age_days} days old, within limit of {max_age_days} days"
        else:
            return False, f"Source is {age_days} days old, exceeding limit of {max_age_days} days"
    
    except Exception as e:
        logger.error(f"Error in staleness_guard: {str(e)}")
        return False, f"Failed to parse source date: {source_date}"


def confidence_gate(confidence: float, threshold: float = 0.7) -> Tuple[bool, str]:
    """
    Check if confidence level is sufficient.
    
    Args:
        confidence: Confidence score (0-1)
        threshold: Minimum acceptable confidence
        
    Returns:
        Tuple of (passed, message) where passed is True if the guard passes
    """
    if confidence >= threshold:
        return True, f"Confidence {confidence:.2f} meets threshold {threshold:.2f}"
    else:
        return False, f"Confidence {confidence:.2f} below threshold {threshold:.2f}"
