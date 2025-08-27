from typing import Dict, Any
import re


def route_query(query: str) -> str:
    """
    Route the query to the appropriate handler based on the query text.
    
    This is a simple keyword-based router that can be extended with more 
    sophisticated logic (e.g., classification models).
    """
    query_lower = query.lower()
    
    # Define patterns for different query types
    policy_patterns = [
        r"policy", r"policies", r"governance", r"compliance", 
        r"rule", r"guideline", r"standard"
    ]
    
    procedure_patterns = [
        r"procedure", r"process", r"how to", r"steps", r"workflow", 
        r"instruction", r"guide", r"manual"
    ]
    
    # Check for policy-related queries
    for pattern in policy_patterns:
        if re.search(r"\b" + pattern + r"\b", query_lower):
            return "policy"
    
    # Check for procedure-related queries
    for pattern in procedure_patterns:
        if re.search(r"\b" + pattern + r"\b", query_lower):
            return "procedure"
    
    # Default to general query
    return "general"


def get_query_intent(query: str) -> Dict[str, Any]:
    """
    Analyze the query to determine user intent.
    
    This could be extended with more sophisticated NLP techniques
    like intent classification models.
    """
    query_lower = query.lower()
    
    # Simple rule-based intent detection
    intents = {
        "search": False,
        "comparison": False,
        "explanation": False,
        "example": False,
        "temporal": False
    }
    
    # Search intent
    if any(term in query_lower for term in ["find", "search", "where", "locate"]):
        intents["search"] = True
    
    # Comparison intent
    if any(term in query_lower for term in ["compare", "difference", "versus", "vs"]):
        intents["comparison"] = True
    
    # Explanation intent
    if any(term in query_lower for term in ["explain", "why", "how", "what is"]):
        intents["explanation"] = True
    
    # Example intent
    if any(term in query_lower for term in ["example", "instance", "sample"]):
        intents["example"] = True
    
    # Temporal intent
    if any(term in query_lower for term in ["when", "date", "deadline", "timeline"]):
        intents["temporal"] = True
    
    return {
        "query": query,
        "primary_intent": next((k for k, v in intents.items() if v), "general"),
        "intents": intents
    }
