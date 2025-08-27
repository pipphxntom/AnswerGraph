#!/usr/bin/env python
"""
Intent Classification Demo

This script demonstrates the intent classification and slot extraction functionality.
"""
import sys
import argparse
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.rag.intent_classifier import classify_intent_and_slots
from src.core.rule_settings import RULE_INTENTS


def test_intent_classification(queries=None):
    """Test intent classification with example queries."""
    if not queries:
        # Default test queries
        queries = [
            "What is the deadline for applying to the computer science program?",
            "How much does the MBA program cost for fall semester?",
            "Tell me about the nursing program at the main campus",
            "What's the process for registering for psychology classes?",
            "Who do I contact about the data science program?",
            "Where can I find the library at the north campus?",
            "What's the history of the university?",  # Should be freeform
        ]
    
    print("\n===== INTENT CLASSIFICATION DEMO =====\n")
    
    for query in queries:
        intent, slots, confidence = classify_intent_and_slots(query)
        
        print(f"Query: {query}")
        print(f"Intent: {intent}")
        print(f"Confidence: {confidence:.2f}")
        print(f"Slots: {json.dumps(slots, indent=2)}")
        print("-" * 50)


def interactive_mode():
    """Run in interactive mode."""
    print("\n===== INTENT CLASSIFICATION INTERACTIVE MODE =====")
    print("Type 'exit' or 'quit' to exit\n")
    
    while True:
        query = input("Enter query: ")
        
        if query.lower() in ('exit', 'quit'):
            break
        
        if not query.strip():
            continue
        
        intent, slots, confidence = classify_intent_and_slots(query)
        
        print(f"Intent: {intent}")
        print(f"Confidence: {confidence:.2f}")
        print(f"Slots: {json.dumps(slots, indent=2)}")
        print("-" * 50)


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Intent Classification Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--interactive", "-i", action="store_true", 
                        help="Run in interactive mode")
    parser.add_argument("--query", "-q", nargs="+", 
                        help="Test specific queries")
    parser.add_argument("--list-intents", "-l", action="store_true",
                        help="List available rule-based intents")
    
    args = parser.parse_args()
    
    if args.list_intents:
        print("\nAvailable rule-based intents:")
        for intent in RULE_INTENTS:
            print(f"- {intent}")
        print()
        return 0
    
    if args.interactive:
        interactive_mode()
    else:
        test_intent_classification(args.query)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
