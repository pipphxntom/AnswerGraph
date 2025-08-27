#!/usr/bin/env python
"""
Guard Functions Demo

This script demonstrates how to use the RAG guard functions
to ensure high-quality and factually accurate answers.
"""
import sys
import asyncio
import argparse
import logging
import json
from typing import Dict, Any, List
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.rag.guards import (
    require_citation,
    temporal_guard,
    numeric_consistency,
    confidence_gate
)
from src.core.db import async_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


async def evaluate_answer(
    answer_data: Dict[str, Any], 
    check_temporal: bool = True,
    check_numeric: bool = True,
    check_confidence: bool = True,
) -> Dict[str, Any]:
    """
    Evaluate an answer using the guard functions.
    
    Args:
        answer_data: The answer data including text, sources, and evidence
        check_temporal: Whether to check temporal validity
        check_numeric: Whether to check numeric consistency
        check_confidence: Whether to apply the confidence gate
        
    Returns:
        Dictionary containing evaluation results
    """
    results = {
        "passed_all": True,
        "guards_results": {}
    }
    
    # Check for citations
    citation_passed, citation_msg = require_citation(answer_data)
    results["guards_results"]["citation"] = {
        "passed": citation_passed,
        "message": citation_msg
    }
    
    if not citation_passed:
        results["passed_all"] = False
    
    # Check temporal validity if requested
    if check_temporal and "sources" in answer_data:
        async with async_session_factory() as session:
            temporal_passed, temporal_msg, preferred_source = await temporal_guard(
                answer_data.get("sources", []), session
            )
            
            results["guards_results"]["temporal"] = {
                "passed": temporal_passed,
                "message": temporal_msg,
                "preferred_source": preferred_source
            }
            
            if not temporal_passed:
                results["passed_all"] = False
    
    # Check numeric consistency if requested
    if check_numeric and "text" in answer_data and "evidence_texts" in answer_data:
        numeric_passed, numeric_msg, missing_values = numeric_consistency(
            answer_data["text"], answer_data.get("evidence_texts", [])
        )
        
        results["guards_results"]["numeric"] = {
            "passed": numeric_passed,
            "message": numeric_msg,
            "missing_values": missing_values
        }
        
        if not numeric_passed:
            results["passed_all"] = False
    
    # Apply confidence gate if requested
    if check_confidence:
        # Get inputs for confidence gate
        margin = answer_data.get("margin", 0.7)  # Default if not provided
        coverage = answer_data.get("coverage", 0.8)  # Default if not provided
        lang_ok = answer_data.get("lang_ok", True)  # Default if not provided
        factual_score = answer_data.get("factual_score")  # Optional
        source_quality = answer_data.get("source_quality")  # Optional
        
        confidence_passed, confidence_score, confidence_msg = confidence_gate(
            margin, coverage, lang_ok, factual_score, source_quality
        )
        
        results["guards_results"]["confidence"] = {
            "passed": confidence_passed,
            "score": confidence_score,
            "message": confidence_msg
        }
        
        if not confidence_passed:
            results["passed_all"] = False
    
    # Return the evaluation results
    return results


def load_sample_answer(file_path: str) -> Dict[str, Any]:
    """Load a sample answer from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def create_sample_answer() -> Dict[str, Any]:
    """Create a sample answer for demonstration."""
    return {
        "text": "The employee handbook was last updated on January 15, 2025. According to policy P-2023-01, employees must submit expense reports within 30 days and any amount over $500 requires manager approval. The company holiday schedule includes 12 paid holidays per year.",
        "sources": [
            {
                "policy_id": "P-2023-01",
                "url": "https://company.internal/policies/P-2023-01",
                "page": 5,
                "section": "Expense Reporting"
            },
            {
                "policy_id": "P-2024-08",
                "url": "https://company.internal/policies/P-2024-08",
                "page": 2,
                "section": "Company Holidays"
            }
        ],
        "evidence_texts": [
            "The employee handbook (Version 3.2) was last updated on January 15, 2025 and approved by the HR department.",
            "Policy P-2023-01 states: Employees must submit expense reports within 30 days of incurring the expense. Any amount over $500 requires manager approval prior to submission.",
            "According to the Company Holiday policy (P-2024-08), employees receive 12 paid holidays per calendar year."
        ],
        "margin": 0.85,
        "coverage": 0.92,
        "lang_ok": True,
        "factual_score": 0.89,
        "source_quality": 0.95
    }


async def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Guard Functions Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("--input", "-i", help="Path to JSON file with sample answer")
    parser.add_argument("--skip-temporal", action="store_true", help="Skip temporal guard check")
    parser.add_argument("--skip-numeric", action="store_true", help="Skip numeric consistency check")
    parser.add_argument("--skip-confidence", action="store_true", help="Skip confidence gate check")
    parser.add_argument("--create-bad-answer", action="store_true", help="Create a sample answer that fails checks")
    
    args = parser.parse_args()
    
    try:
        # Load or create sample answer
        if args.input:
            logger.info(f"Loading sample answer from {args.input}")
            answer_data = load_sample_answer(args.input)
        else:
            logger.info("Using built-in sample answer")
            answer_data = create_sample_answer()
            
            # Modify to create failures if requested
            if args.create_bad_answer:
                logger.info("Creating sample answer with deliberate failures")
                answer_data["text"] = "The employee handbook was updated on March 1, 2025. According to policy, employees must submit expense reports within 45 days and any amount over $750 requires manager approval."
                answer_data["sources"] = [{"policy_id": "P-2023-01"}]  # Missing URL and page
                answer_data["margin"] = 0.45
                answer_data["coverage"] = 0.58
        
        # Print the sample answer
        print("\n===== SAMPLE ANSWER =====")
        print(f"Text: {answer_data['text']}")
        print(f"Sources: {json.dumps(answer_data.get('sources', []), indent=2)}")
        print("==========================\n")
        
        # Evaluate the answer
        logger.info("Evaluating answer with guard functions")
        results = await evaluate_answer(
            answer_data,
            check_temporal=not args.skip_temporal,
            check_numeric=not args.skip_numeric,
            check_confidence=not args.skip_confidence
        )
        
        # Print the results
        print("\n===== GUARD RESULTS =====")
        print(f"Overall result: {'PASSED' if results['passed_all'] else 'FAILED'}")
        print("\nIndividual guard results:")
        
        for guard_name, guard_result in results["guards_results"].items():
            status = "✅ PASSED" if guard_result["passed"] else "❌ FAILED"
            print(f"\n{guard_name.upper()} GUARD: {status}")
            
            for key, value in guard_result.items():
                if key != "passed":
                    if isinstance(value, dict) and value:
                        print(f"  {key}: {json.dumps(value, indent=2)}")
                    elif isinstance(value, list) and value:
                        print(f"  {key}: {', '.join(value)}")
                    else:
                        print(f"  {key}: {value}")
        
        print("\n==========================")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    asyncio.run(main())
