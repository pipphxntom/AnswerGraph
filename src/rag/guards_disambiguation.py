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
