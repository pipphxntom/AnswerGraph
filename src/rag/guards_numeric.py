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
