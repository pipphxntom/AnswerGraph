from typing import Dict, Any, List, Tuple, Optional, Union
import re
import datetime
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

# Import models
from src.models.policy import Policy
from src.models.source import Source
from src.schemas.answer import AnswerContract, GuardDecision

# Configure logging
logger = logging.getLogger(__name__)


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


def require_citation(answer_contract: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verify that the answer contains at least one source citation with URL and page.
    
    Args:
        answer_contract: Dictionary containing the answer and its metadata
        
    Returns:
        Tuple of (passed, message) where passed is True if the guard passes
    """
    # Handle both RAG and Rules path contract formats
    if "sources" in answer_contract:
        sources = answer_contract.get("sources", [])
    elif "source" in answer_contract:
        # Rules path format - single source
        sources = [answer_contract.get("source", {})]
    else:
        return False, "Answer lacks any source citations"
    
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


def staleness_guard(source_date_str: Optional[str], max_age_days: int = 365) -> Tuple[bool, str]:
    """
    Check if a source is too old to be considered reliable.
    
    Args:
        source_date_str: ISO format date string (YYYY-MM-DD)
        max_age_days: Maximum age in days for a source to be fresh
        
    Returns:
        Tuple of (passed, message) where passed is True if the guard passes
    """
    if not source_date_str:
        return False, "No source date provided to check freshness"
    
    try:
        # Parse the date string
        source_date = datetime.datetime.fromisoformat(source_date_str.replace('Z', '+00:00'))
        
        # Convert to date only if it's a datetime
        if isinstance(source_date, datetime.datetime):
            source_date = source_date.date()
        
        # Calculate the age
        today = datetime.date.today()
        age_days = (today - source_date).days
        
        # Check if it's too old
        if age_days > max_age_days:
            return False, f"Source is {age_days} days old (max allowed: {max_age_days})"
        
        return True, f"Source is {age_days} days old (within {max_age_days} day limit)"
    
    except Exception as e:
        logger.error(f"Error in staleness guard: {str(e)}")
        return False, f"Invalid date format: {source_date_str}"


def apply_guards(contract: AnswerContract,
                 newest_policy_date: Optional[str],
                 lang_ok: bool,
                 max_age_days: int = 365) -> GuardDecision:
    """
    Apply all guards to an answer contract and return a structured decision.
    
    This is the main guard orchestrator that should be used for both
    rule-based and RAG-based answers.
    
    Args:
        contract: The answer contract to check
        newest_policy_date: The date of the newest policy (ISO format)
        lang_ok: Whether the language of the answer is acceptable
        max_age_days: Maximum age in days for a source to be considered fresh
        
    Returns:
        GuardDecision with validation result and reasons
    """
    reasons, ok = [], True
    
    # 1. Citation guard - ensure URL and page are present
    citation_passed, _ = require_citation(contract.model_dump())
    if not citation_passed: 
        ok = False
        reasons.append("no_citation")
    
    # 2. Numeric consistency guard - check numbers in answer match evidence
    if contract.evidence_texts:
        num_passed, _, _ = numeric_consistency(contract.answer, contract.evidence_texts)
        if not num_passed:
            ok = False
            reasons.append("numeric_mismatch")
    
    # 3. Temporal guard - check dates in answer for logical consistency
    if contract.sources:
        sources_dict = [source.model_dump() for source in contract.sources]
        temporal_passed, _, _ = temporal_guard(sources_dict)
        if not temporal_passed:
            ok = False
            reasons.append("temporal_violation")
    
    # 4. Staleness guard - check if sources are recent enough
    if newest_policy_date:
        stale_passed, _ = staleness_guard(newest_policy_date, max_age_days)
        if not stale_passed:
            ok = False
            reasons.append("stale_source")
    
    # 5. Language check
    if not lang_ok:
        reasons.append("lang_mismatch")
    
    # Calculate confidence penalty based on failures
    penalty = 0.0
    penalty += 0.2 * ("no_citation" in reasons)
    penalty += 0.2 * ("numeric_mismatch" in reasons)
    penalty += 0.2 * ("temporal_violation" in reasons)
    penalty += 0.2 * ("stale_source" in reasons)
    penalty += 0.1 * ("lang_mismatch" in reasons)
    
    confidence = max(0.0, 1.0 - penalty)
    
    return GuardDecision(ok=ok, reasons=reasons, confidence=confidence)


async def temporal_guard(sources: List[Dict[str, Any]], session: AsyncSession = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
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


def disambiguation_guard(
    answer_text: str, 
    query: str,
    min_confidence: float = 0.7
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Check if the answer is likely to need disambiguation due to ambiguity in the query.
    
    This guard identifies when a query might have multiple valid interpretations
    and suggests disambiguation options.
    
    Args:
        answer_text: The generated answer text
        query: The original user query
        min_confidence: Minimum confidence threshold to consider the answer unambiguous
        
    Returns:
        Tuple of (passed, message, details) where:
        - passed is True if the answer is unambiguous
        - message explains the result
        - details contains disambiguation options if any
    """
    # Patterns that suggest ambiguity
    ambiguity_patterns = [
        r"(?i)there\s+are\s+(?:several|multiple|many|different)\s+(?:types|kinds|ways|interpretations)",
        r"(?i)your\s+question\s+could\s+(?:be interpreted|refer to|mean)\s+(?:in|as)",
        r"(?i)(?:did you mean|are you asking about|do you want to know about)",
        r"(?i)(?:unclear|ambiguous|vague)",
        r"(?i)(?:could you clarify|could you specify|can you provide more details)",
    ]
    
    # Check for ambiguity indicators in the answer
    confidence = 1.0
    ambiguity_matches = []
    
    for pattern in ambiguity_patterns:
        matches = re.findall(pattern, answer_text)
        if matches:
            ambiguity_matches.extend(matches)
            # Reduce confidence with each ambiguity indicator
            confidence *= 0.8
    
    # Count question marks in the answer (too many suggests clarification questions)
    question_marks = answer_text.count("?")
    if question_marks > 2:
        confidence *= (1.0 - (question_marks - 2) * 0.1)  # Decrease confidence for excessive questions
    
    # Extract potential disambiguation options
    options = []
    option_pattern = r"(?:1\.\s+|•\s+|Option\s+\d+:\s+|-)([^\\n.]{5,100})"
    option_matches = re.findall(option_pattern, answer_text)
    
    if option_matches:
        options = [opt.strip() for opt in option_matches]
    
    # Final determination
    details = {
        "confidence": confidence,
        "ambiguity_indicators": ambiguity_matches,
        "question_count": question_marks,
        "disambiguation_options": options
    }
    
    if confidence < min_confidence:
        return False, f"Answer suggests ambiguity (confidence: {confidence:.2f})", details
    else:
        return True, f"Answer appears unambiguous (confidence: {confidence:.2f})", details


async def apply_guards(
    answer_contract: Dict[str, Any], 
    evidence_texts: List[str] = None,
    session: Optional[AsyncSession] = None,
    guards_to_apply: List[str] = None,
    fail_fast: bool = False,
    query: str = None
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Apply all guards to an answer contract and return if it passes.
    
    Args:
        answer_contract: The answer contract to check
        evidence_texts: List of evidence texts used to generate the answer
        session: Optional database session for guards that need database access
        guards_to_apply: Optional list of specific guards to apply (default: all guards)
        fail_fast: If True, stop applying guards after first failure
        query: Original user query (needed for disambiguation guard)
        
    Returns:
        Tuple of (passed, reasons, details) where:
        - passed is True if all guards pass
        - reasons is a list of messages explaining which guards passed/failed
        - details is a dictionary with detailed results from each guard
    """
    # Default: apply all guards
    all_guards = ["citation", "staleness", "numeric", "temporal", "disambiguation"]
    guards_to_apply = guards_to_apply or all_guards
    
    reasons = []
    details = {}
    all_passed = True
    
    try:
        # Validate input
        if not answer_contract:
            return False, ["Invalid answer contract: empty or null"], {"error": "Invalid input"}
            
        # 1. Citation guard - ensure URL and page are present
        if "citation" in guards_to_apply:
            try:
                citation_passed, citation_msg = require_citation(answer_contract)
                reasons.append(f"Citation Guard: {citation_msg}")
                details["citation"] = {"passed": citation_passed, "message": citation_msg}
                
                if not citation_passed:
                    all_passed = False
                    if fail_fast:
                        return False, reasons, details
            except Exception as e:
                error_msg = f"Citation Guard: Error - {str(e)}"
                logger.error(error_msg)
                reasons.append(error_msg)
                details["citation"] = {"passed": False, "message": error_msg, "error": str(e)}
                all_passed = False
                if fail_fast:
                    return False, reasons, details
        
        # 2. Staleness guard - check source date
        if "staleness" in guards_to_apply:
            try:
                source_date = None
                if "source" in answer_contract and "updated_at" in answer_contract["source"]:
                    source_date = answer_contract["source"]["updated_at"]
                elif "sources" in answer_contract and answer_contract["sources"]:
                    # Get the most recent source date from the list
                    dates = [s.get("updated_at") for s in answer_contract["sources"] if "updated_at" in s]
                    if dates:
                        source_date = max(dates)
                
                if source_date:
                    staleness_passed, staleness_msg = staleness_guard(source_date)
                    reasons.append(f"Staleness Guard: {staleness_msg}")
                    details["staleness"] = {"passed": staleness_passed, "message": staleness_msg, "source_date": source_date}
                    
                    if not staleness_passed:
                        all_passed = False
                        if fail_fast:
                            return False, reasons, details
                else:
                    skip_msg = "Staleness Guard: Skipped (no source date found)"
                    reasons.append(skip_msg)
                    details["staleness"] = {"passed": True, "message": skip_msg, "skipped": True}
            except Exception as e:
                error_msg = f"Staleness Guard: Error - {str(e)}"
                logger.error(error_msg)
                reasons.append(error_msg)
                details["staleness"] = {"passed": False, "message": error_msg, "error": str(e)}
                all_passed = False
                if fail_fast:
                    return False, reasons, details
        
        # 3. Numeric consistency guard - if evidence is provided
        if "numeric" in guards_to_apply:
            try:
                if evidence_texts and "text" in answer_contract:
                    num_passed, num_msg, missing = numeric_consistency(answer_contract["text"], evidence_texts)
                    reasons.append(f"Numeric Consistency Guard: {num_msg}")
                    details["numeric"] = {
                        "passed": num_passed, 
                        "message": num_msg, 
                        "missing_values": missing
                    }
                    
                    if not num_passed:
                        all_passed = False
                        reasons.extend([f"- Missing: {item}" for item in missing])
                        if fail_fast:
                            return False, reasons, details
                else:
                    skip_msg = "Numeric Consistency Guard: Skipped (no evidence texts provided or no answer text)"
                    reasons.append(skip_msg)
                    details["numeric"] = {"passed": True, "message": skip_msg, "skipped": True}
            except Exception as e:
                error_msg = f"Numeric Consistency Guard: Error - {str(e)}"
                logger.error(error_msg)
                reasons.append(error_msg)
                details["numeric"] = {"passed": False, "message": error_msg, "error": str(e)}
                all_passed = False
                if fail_fast:
                    return False, reasons, details
        
        # 4. Temporal guard - if session is provided
        if "temporal" in guards_to_apply:
            try:
                if session and "sources" in answer_contract and answer_contract["sources"]:
                    temporal_passed, temporal_msg, outdated_sources = await temporal_guard(answer_contract["sources"], session)
                    reasons.append(f"Temporal Guard: {temporal_msg}")
                    details["temporal"] = {
                        "passed": temporal_passed, 
                        "message": temporal_msg,
                        "outdated_sources": outdated_sources
                    }
                    
                    if not temporal_passed:
                        all_passed = False
                        if fail_fast:
                            return False, reasons, details
                else:
                    skip_msg = "Temporal Guard: Skipped (no database session or sources provided)"
                    reasons.append(skip_msg)
                    details["temporal"] = {"passed": True, "message": skip_msg, "skipped": True}
            except Exception as e:
                error_msg = f"Temporal Guard: Error - {str(e)}"
                logger.error(error_msg)
                reasons.append(error_msg)
                details["temporal"] = {"passed": False, "message": error_msg, "error": str(e)}
                all_passed = False
                if fail_fast:
                    return False, reasons, details
        
        # 5. Disambiguation guard - check if answer suggests ambiguity
        if "disambiguation" in guards_to_apply:
            try:
                if query and "text" in answer_contract:
                    disambiguation_passed, disambiguation_msg, disambiguation_details = disambiguation_guard(
                        answer_contract["text"], 
                        query
                    )
                    reasons.append(f"Disambiguation Guard: {disambiguation_msg}")
                    details["disambiguation"] = {
                        "passed": disambiguation_passed,
                        "message": disambiguation_msg,
                        **disambiguation_details
                    }
                    
                    # Note: We don't fail the overall check for disambiguation
                    # Instead, we use this to add disambiguation options to the response
                    # So we don't set all_passed = False here
                else:
                    skip_msg = "Disambiguation Guard: Skipped (no query or answer text provided)"
                    reasons.append(skip_msg)
                    details["disambiguation"] = {"passed": True, "message": skip_msg, "skipped": True}
            except Exception as e:
                error_msg = f"Disambiguation Guard: Error - {str(e)}"
                logger.error(error_msg)
                reasons.append(error_msg)
                details["disambiguation"] = {"passed": True, "message": error_msg, "error": str(e)}
                # We don't fail for disambiguation errors
        
        # Add overall validation summary
        details["overall"] = {
            "passed": all_passed,
            "guards_applied": guards_to_apply,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Return the final result
        return all_passed, reasons, details
        
    except Exception as e:
        # Catch any unexpected errors
        error_msg = f"Unexpected error in guard application: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, [error_msg], {"error": str(e), "overall": {"passed": False}}
