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
