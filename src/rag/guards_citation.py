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
