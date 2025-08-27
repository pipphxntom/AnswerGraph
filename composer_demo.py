#!/usr/bin/env python
"""
Answer Composition Demo

This script demonstrates the answer composition functionality using the Qwen2-7B-Instruct LLM.
"""
import sys
import asyncio
import argparse
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.db import async_session_factory
from src.rag.composer import compose_answer
from src.rag.deterministic_fetch import fetch_procedure_with_related
from src.rag.retriever import retrieve_documents
from src.rag.guards import numeric_consistency, require_citation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Sample evidence documents for standalone demo
SAMPLE_EVIDENCE = [
    {
        "text": "The university policy states that a bachelor's degree requires completion of 120 credit hours, including 40 hours of general education requirements and at least 30 hours in the major field. Transfer students must complete at least 30 credit hours in residence. The minimum GPA for graduation is 2.0 overall and 2.5 in the major.",
        "metadata": {
            "url": "https://university.edu/policies/graduation",
            "name": "Graduation Requirements",
            "page": 1,
            "section": "Undergraduate Degrees"
        }
    },
    {
        "text": "Students may withdraw from courses without academic penalty until the end of the tenth week of the semester. After this date, withdrawals are only permitted in cases of illness or emergency, with documentation and approval from the dean's office. A grade of 'W' will appear on the transcript for any withdrawn course.",
        "metadata": {
            "url": "https://university.edu/policies/registration",
            "name": "Course Registration and Withdrawal",
            "page": 3,
            "section": "Withdrawals"
        }
    },
    {
        "text": "The Computer Science department requires 45 credits in the major, including CS 101, CS 201, CS 301, and CS 401 as core courses. Students must also complete 15 credits of CS electives at the 300 level or above. A minimum grade of C is required in all major courses. The department offers a senior capstone project worth 6 credits.",
        "metadata": {
            "url": "https://university.edu/cs/requirements",
            "name": "Computer Science Program",
            "page": 2,
            "section": "Major Requirements"
        }
    }
]

# Sample queries to test with sample evidence
SAMPLE_QUERIES = [
    "How many credits do I need to graduate?",
    "What is the policy for withdrawing from courses?",
    "Tell me about the requirements for a Computer Science major",
    "What is the minimum GPA for graduation?",
]


async def demo_with_retrieval(query):
    """Demonstrate compose_answer with retrieved documents."""
    logger.info(f"Retrieving documents for query: {query}")
    
    # Retrieve documents
    documents = await retrieve_documents(
        query=query,
        limit=5
    )
    
    if not documents:
        print("No documents found for the query.")
        return
    
    logger.info(f"Retrieved {len(documents)} documents")
    
    # Compose answer
    result = await compose_answer(query, documents)
    
    if result:
        print("\n===== COMPOSED ANSWER =====\n")
        print(result["text"])
        print("\n===== COMPONENTS =====\n")
        print(f"Direct Answer: {result['direct_answer']}")
        print("\nKey Points:")
        for point in result["key_points"]:
            print(f"• {point}")
        print("\nSource:")
        source = result["sources"][0]
        print(f"URL: {source['url']}")
        print(f"Page: {source['page']}")
        print(f"Policy ID: {source['policy_id']}")
    else:
        print("\nAnswer composition failed or quality checks didn't pass.")


async def demo_with_procedure(procedure_id):
    """Demonstrate compose_answer with a specific procedure."""
    logger.info(f"Fetching procedure: {procedure_id}")
    
    async with async_session_factory() as session:
        # Fetch procedure
        procedures = await fetch_procedure_with_related(
            session=session,
            procedure_id=procedure_id
        )
        
        if not procedures:
            print(f"Procedure {procedure_id} not found.")
            return
        
        # Convert to evidence format
        procedure = procedures[0]
        evidence = [{
            "content": json.dumps(procedure["fields"], indent=2),
            "policy_id": procedure["policy"]["id"],
            "url": procedure["source"].get("url"),
            "page": procedure["source"].get("page")
        }]
        
        query = f"What are the details of {procedure['fields']['name']}?"
        
        # Compose answer
        result = await compose_answer(query, evidence)
        
        if result:
            print("\n===== COMPOSED ANSWER =====\n")
            print(result["text"])
            print("\n===== COMPONENTS =====\n")
            print(f"Direct Answer: {result['direct_answer']}")
            print("\nKey Points:")
            for point in result["key_points"]:
                print(f"• {point}")
            print("\nSource:")
            source = result["sources"][0]
            print(f"URL: {source['url']}")
            print(f"Page: {source['page']}")
            print(f"Policy ID: {source['policy_id']}")
        else:
            print("\nAnswer composition failed or quality checks didn't pass.")


def demo_with_sample_evidence():
    """
    Demonstrate compose_answer with sample evidence.
    This doesn't require any database access or retrieval.
    """
    print("\n" + "="*80)
    print("SAMPLE EVIDENCE DEMO")
    print("="*80)
    
    for i, query in enumerate(SAMPLE_QUERIES):
        print(f"\nQUERY {i+1}: {query}")
        print("-"*80)
        
        # Extract evidence texts for guard functions
        evidence_texts = [doc["text"] for doc in SAMPLE_EVIDENCE]
        
        # Generate answer
        result = compose_answer(query, SAMPLE_EVIDENCE)
        
        # Print the answer
        print("GENERATED ANSWER:")
        print(result.get("answer", "No answer generated"))
        
        # Check guard functions
        guard_results = {
            "numeric_consistency": numeric_consistency(result.get("answer", ""), evidence_texts),
            "has_citations": require_citation(result.get("answer", ""))
        }
        
        print("\nGUARD FUNCTION CHECKS:")
        print(f"Numeric consistency: {'PASSED' if guard_results['numeric_consistency'] else 'FAILED'}")
        print(f"Citation check: {'PASSED' if guard_results['has_citations'] else 'FAILED'}")
        
        print("\nSOURCES:")
        if "sources" in result:
            for source in result["sources"]:
                print(f"- {source.get('name', 'Unknown')} ({source.get('url', 'No URL')})")
        else:
            print("No sources provided")
        
        print("\n" + "="*80)


async def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Answer Composition Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Retrieval-based demo
    retrieval_parser = subparsers.add_parser("retrieval", help="Demo with retrieved documents")
    retrieval_parser.add_argument("query", help="Query to retrieve documents for")
    
    # Procedure-based demo
    procedure_parser = subparsers.add_parser("procedure", help="Demo with a specific procedure")
    procedure_parser.add_argument("procedure_id", help="ID of the procedure")
    
    # Sample evidence demo
    sample_parser = subparsers.add_parser("sample", help="Demo with sample evidence")
    
    args = parser.parse_args()
    
    if args.command == "retrieval":
        await demo_with_retrieval(args.query)
    elif args.command == "procedure":
        await demo_with_procedure(args.procedure_id)
    elif args.command == "sample":
        demo_with_sample_evidence()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
