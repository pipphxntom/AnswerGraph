from typing import Dict, Any, List, Tuple, Optional, Union
import re
import datetime
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# Import models
from src.models.policy import Policy
from src.models.source import Source


def validate_query(query: str) -> Dict[str, Any]:
    """
    Validate the query to ensure it meets basic requirements.
    
    This implements simple guardrails to prevent misuse.
    """
    # Check if query is empty
    if not query or query.strip() == "":
        return {
            "valid": False,
            "message": "Query cannot be empty"
        }
    
    # Check query length
    if len(query) < 3:
        return {
            "valid": False,
            "message": "Query must be at least 3 characters long"
        }
    
    # Check for potential harmful queries (very basic check)
    harmful_patterns = [
        r"(?i)\b(exec|eval|system|os\.|subprocess|import os|import subprocess)\b",
        r"(?i)(DROP|DELETE|INSERT|UPDATE)\s+.*",
        r"(?i)<script.*?>.*?</script>",
        r"(?i)javascript:"
    ]
    
    for pattern in harmful_patterns:
        if re.search(pattern, query):
            return {
                "valid": False,
                "message": "Query contains potentially harmful content"
            }
    
    # All checks passed
    return {
        "valid": True,
        "message": "Query is valid"
    }


def ensure_sensitive_data_protection(content: str) -> str:
    """
    Ensure that sensitive data is not included in the response.
    
    This implements basic PII masking. In a real system, you would use
    more sophisticated NER or pattern matching for thorough protection.
    """
    # Pattern for potential PII
    patterns = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b(?:\d{4}[- ]?){3}\d{4}\b'
    }
    
    # Mask each type of PII
    masked_content = content
    for pii_type, pattern in patterns.items():
        masked_content = re.sub(pattern, f"[REDACTED {pii_type.upper()}]", masked_content)
    
    return masked_content


def check_information_quality(content: str) -> Dict[str, Any]:
    """
    Check the quality of the information being returned.
    
    This is a simple heuristic-based quality check that could be expanded
    with more sophisticated metrics.
    """
    # Simple heuristics for quality
    quality_score = 1.0
    issues = []
    
    # Check length
    if len(content) < 20:
        quality_score *= 0.5
        issues.append("Content is too short")
    
    # Check for vague language
    vague_terms = ["maybe", "perhaps", "possibly", "not sure", "unclear"]
    vague_count = sum(1 for term in vague_terms if term in content.lower())
    if vague_count > 2:
        quality_score *= 0.8
        issues.append("Content contains vague language")
    
    # Overall assessment
    quality_assessment = "high" if quality_score > 0.8 else "medium" if quality_score > 0.5 else "low"
    
    return {
        "quality_score": quality_score,
        "quality_assessment": quality_assessment,
        "issues": issues
    }


def require_citation(answer: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verify that the answer contains at least one source citation with URL and page.
    
    Args:
        answer: Dictionary containing the answer and its metadata
        
    Returns:
        Tuple of (passed, message) where passed is True if the guard passes
    """
    sources = answer.get("sources", [])
    
    if not sources:
        return False, "Answer lacks any source citations"
    
    valid_sources = 0
    for source in sources:
        # Check if source has both URL and page number
        has_url = bool(source.get("url"))
        has_page = "page" in source and source["page"] is not None
        
        if has_url and has_page:
            valid_sources += 1
    
    if valid_sources == 0:
        return False, "Answer lacks valid source citations with URL and page number"
    
    return True, f"Answer contains {valid_sources} valid source citations"


async def temporal_guard(sources: List[Dict[str, Any]], session: AsyncSession) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Check temporal validity of sources used in the answer.
    
    This guard:
    1. Prefers Policy with max(effective_from) date
    2. Rejects if all policies are older than 180 days and newer policies exist for the same topic
    
    Args:
        sources: List of source dictionaries with policy_id
        session: Database session for querying policy information
        
    Returns:
        Tuple of (passed, message, preferred_source) where:
        - passed is True if the guard passes
        - message explains the result
        - preferred_source is the most recent valid source (if any)
    """
    if not sources:
        return False, "No sources provided", None
    
    today = datetime.datetime.now().date()
    cutoff_date = today - timedelta(days=180)
    
    # Extract all policy IDs
    policy_ids = [source.get("policy_id") for source in sources if source.get("policy_id")]
    
    if not policy_ids:
        return False, "No policy IDs found in sources", None
    
    # Query database for policy information
    stmt = select(Policy).where(Policy.id.in_(policy_ids))
    result = await session.execute(stmt)
    policies = result.scalars().all()
    
    if not policies:
        return False, "No matching policies found in database", None
    
    # Find the most recent policy
    most_recent = max(policies, key=lambda p: p.effective_from if p.effective_from else datetime.date.min)
    
    # Check if the most recent policy is newer than the cutoff date
    if most_recent.effective_from and most_recent.effective_from >= cutoff_date:
        # Find the source that matches this policy
        preferred_source = next((s for s in sources if s.get("policy_id") == most_recent.id), None)
        return True, f"Using most recent policy from {most_recent.effective_from}", preferred_source
    
    # All policies are older than the cutoff, check if newer policies exist for the same topics
    topic_ids = [p.topic_id for p in policies if p.topic_id]
    
    if topic_ids:
        # Query for newer policies on the same topics
        newer_policy_stmt = select(Policy).where(
            Policy.topic_id.in_(topic_ids),
            Policy.effective_from >= cutoff_date
        )
        newer_result = await session.execute(newer_policy_stmt)
        newer_policies = newer_result.scalars().all()
        
        if newer_policies:
            return False, f"Outdated policies used. {len(newer_policies)} newer policies available.", None
    
    # No newer policies found, use the most recent one even if it's old
    preferred_source = next((s for s in sources if s.get("policy_id") == most_recent.id), None)
    return True, f"Using most recent available policy from {most_recent.effective_from} (older than 180 days)", preferred_source


def numeric_consistency(answer_text: str, evidence_texts: List[str]) -> Tuple[bool, str, List[str]]:
    """
    Verify that all dates and numeric amounts in the answer appear in at least one evidence text.
    
    This guards against the model hallucinating specific dates, dollar amounts, or other numeric values
    that do not appear in the source documents.
    
    Args:
        answer_text: The generated answer text
        evidence_texts: List of evidence texts used to generate the answer
        
    Returns:
        Tuple of (passed, message, missing_values) where:
        - passed is True if all numeric values in the answer appear in evidence
        - message explains the result
        - missing_values lists any numeric values that weren't found in evidence
    """
    # Patterns for dates and numeric amounts
    patterns = {
        "date": [
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b',  # January 1, 2023
            r'\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b',  # 1 January 2023
            r'\b\d{4}-\d{2}-\d{2}\b',  # 2023-01-01
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # 1/1/2023 or 01/01/2023
            r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',  # 1.1.2023 or 01.01.2023
        ],
        "amount": [
            r'\$\s?\d+(?:,\d{3})*(?:\.\d{2})?\b',  # $1,000.00
            r'\b\d+(?:,\d{3})*\s?(?:dollars|USD|CAD|EUR|GBP)\b',  # 1,000 dollars
            r'\b\d+\s?%\b',  # 10%
            r'\b\d+(?:,\d{3})*(?:\.\d+)?\s?(?:million|billion|trillion)\b',  # 1.5 million
        ],
        "number": [
            r'\b\d{3}-\d{3}-\d{4}\b',  # phone numbers like 555-123-4567
            r'\b\d{4}\b',  # 4-digit numbers like years or codes
            r'\b\d{5,}\b',  # larger numbers like zip codes or IDs
        ]
    }
    
    # Find all dates and amounts in the answer
    answer_values = []
    for category, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.findall(pattern, answer_text)
            for match in matches:
                answer_values.append((category, match))
    
    if not answer_values:
        return True, "No numeric values found in answer", []
    
    # Check if each value appears in at least one evidence text
    missing_values = []
    for category, value in answer_values:
        found = False
        for evidence in evidence_texts:
            if value in evidence:
                found = True
                break
        
        if not found:
            missing_values.append(f"{category}: {value}")
    
    if missing_values:
        return False, f"Found {len(missing_values)} numeric values in answer that don't appear in evidence", missing_values
    
    return True, f"All {len(answer_values)} numeric values in answer are supported by evidence", []


def confidence_gate(
    margin: float, 
    coverage: float, 
    lang_ok: bool, 
    factual_score: Optional[float] = None,
    source_quality: Optional[float] = None
) -> Tuple[bool, float, str]:
    """
    Compute final confidence score and apply thresholding.
    
    This function combines multiple quality signals to determine if the answer
    meets the quality threshold for being returned to the user.
    
    Args:
        margin: Confidence margin (typically from retrieval scores)
        coverage: How much of the answer is covered by evidence (0.0-1.0)
        lang_ok: Whether the language quality check passed
        factual_score: Optional factual consistency score (0.0-1.0)
        source_quality: Optional source quality score (0.0-1.0)
        
    Returns:
        Tuple of (passed, final_score, message) where:
        - passed is True if the confidence gate passes
        - final_score is the computed confidence score
        - message explains the result
    """
    # Weights for different components
    weights = {
        "margin": 0.3,
        "coverage": 0.3,
        "lang": 0.1,
        "factual": 0.2,
        "source": 0.1
    }
    
    # Calculate the base score
    score_components = {
        "margin": min(max(margin, 0.0), 1.0),  # Clip to 0-1 range
        "coverage": coverage,
        "lang": 1.0 if lang_ok else 0.0
    }
    
    # Add optional components if provided
    if factual_score is not None:
        score_components["factual"] = factual_score
    else:
        # Redistribute weight if factual score is not provided
        weights["margin"] += weights["factual"] * 0.5
        weights["coverage"] += weights["factual"] * 0.5
        weights["factual"] = 0.0
        
    if source_quality is not None:
        score_components["source"] = source_quality
    else:
        # Redistribute weight if source quality is not provided
        weights["margin"] += weights["source"] * 0.5
        weights["coverage"] += weights["source"] * 0.5
        weights["source"] = 0.0
    
    # Calculate weighted score
    final_score = sum(score * weights[key] for key, score in score_components.items())
    
    # Threshold for acceptance (adjustable)
    threshold = 0.6
    
    if final_score >= threshold:
        return True, final_score, f"Confidence score {final_score:.2f} meets threshold {threshold:.2f}"
    else:
        return False, final_score, f"Confidence score {final_score:.2f} below threshold {threshold:.2f}"
