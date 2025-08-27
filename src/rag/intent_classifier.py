"""
Intent classification and slot extraction module for rule-based intents.
"""
from typing import Dict, Any, List, Tuple, Optional
import re
import logging
from rapidfuzz import fuzz, process
from src.core.rule_settings import RULE_INTENTS, INTENT_PATTERNS, SLOT_VALUES, INTENT_SLOTS

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text for better matching.
    
    Args:
        text: Input text to normalize
        
    Returns:
        Normalized text
    """
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation that might interfere with matching
    text = re.sub(r'[?!.,;:"]', ' ', text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_slots(text: str) -> Dict[str, str]:
    """
    Extract slot values from text using regex and fuzzy matching.
    
    Args:
        text: Input text to extract slots from
        
    Returns:
        Dictionary of slot names and their extracted values
    """
    text = normalize_text(text)
    slots = {}
    
    # Extract program names using fuzzy matching
    for program in SLOT_VALUES["program"]:
        if program in text or fuzz.partial_ratio(program, text) > 85:
            slots["program"] = program
            break
    
    # Try to extract any program name not in our predefined list
    if "program" not in slots:
        program_patterns = [
            r"(?:for|about|in|the)\s+([a-z]+(?:\s+[a-z]+){0,3})\s+(?:program|degree|major|course|department)",
            r"([a-z]+(?:\s+[a-z]+){0,3})\s+(?:program|degree|major|course|department)"
        ]
        
        for pattern in program_patterns:
            match = re.search(pattern, text)
            if match:
                slots["program"] = match.group(1).strip()
                break
    
    # Extract semester
    for semester in SLOT_VALUES["semester"]:
        if semester in text or fuzz.partial_ratio(semester, text) > 90:
            slots["semester"] = semester
            break
    
    # Extract campus
    for campus in SLOT_VALUES["campus"]:
        if campus in text or fuzz.partial_ratio(campus, text) > 90:
            slots["campus"] = campus
            break
    
    # Extract service (for campus_services intent)
    for service in SLOT_VALUES["service"]:
        if service in text or fuzz.partial_ratio(service, text) > 90:
            slots["service"] = service
            break
    
    return slots


def match_intent_patterns(text: str) -> List[Tuple[str, float]]:
    """
    Match text against intent patterns using fuzzy matching.
    
    Args:
        text: Input text to match against patterns
        
    Returns:
        List of (intent, score) tuples sorted by score descending
    """
    text = normalize_text(text)
    intent_scores = []
    
    for intent, patterns in INTENT_PATTERNS.items():
        # Get the best match for this intent
        best_score = 0
        for pattern in patterns:
            # Replace slot placeholders with empty strings for matching
            clean_pattern = re.sub(r'\{[a-z_]+\}', '', pattern).strip()
            
            # Calculate fuzzy match score
            score = fuzz.token_set_ratio(text, clean_pattern)
            if score > best_score:
                best_score = score
        
        intent_scores.append((intent, best_score))
    
    # Sort by score descending
    return sorted(intent_scores, key=lambda x: x[1], reverse=True)


def calculate_slot_confidence(intent: str, slots: Dict[str, str]) -> float:
    """
    Calculate confidence score based on slot filling.
    
    Args:
        intent: The matched intent
        slots: The extracted slots
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    required_slots = INTENT_SLOTS.get(intent, [])
    
    if not required_slots:
        return 1.0
    
    # Calculate percentage of required slots that were filled
    filled_slots = sum(1 for slot in required_slots if slot in slots)
    slot_ratio = filled_slots / len(required_slots)
    
    return slot_ratio


def classify_intent_and_slots(text: str) -> Tuple[str, Dict[str, str], float]:
    """
    Classify the intent of a text and extract slots.
    
    Args:
        text: Input text to classify
        
    Returns:
        Tuple of (intent, slots, confidence) where:
        - intent is the classified intent or "freeform" if no match
        - slots is a dictionary of extracted slot values
        - confidence is a score between 0.0 and 1.0
    """
    if not text or not text.strip():
        return "freeform", {}, 0.0
    
    # Extract slots from the text
    slots = extract_slots(text)
    
    # Match against intent patterns
    intent_scores = match_intent_patterns(text)
    
    if not intent_scores or intent_scores[0][1] < 60:
        return "freeform", slots, 0.0
    
    # Get the top intent
    top_intent, pattern_score = intent_scores[0]
    
    # Calculate confidence based on pattern match and slot filling
    pattern_confidence = pattern_score / 100.0
    slot_confidence = calculate_slot_confidence(top_intent, slots)
    
    # Combine scores with weights
    combined_confidence = (pattern_confidence * 0.7) + (slot_confidence * 0.3)
    
    # Only consider rule intents
    if top_intent in RULE_INTENTS and combined_confidence >= 0.6:
        return top_intent, slots, combined_confidence
    
    return "freeform", slots, combined_confidence
