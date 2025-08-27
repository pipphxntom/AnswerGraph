"""
Demo script for the complete RAG pipeline.

This script demonstrates the end-to-end pipeline from query to answer generation:
1. Intent classification
2. Document retrieval
3. Document reranking
4. Answer composition using LLM
5. Answer validation with guard functions

Usage:
    python demo_pipeline.py

Requirements:
    - All components must be properly set up
    - Database must be initialized with some data
"""

import asyncio
import os
from typing import Dict, Any, List
import logging
from datetime import datetime
import json
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set up SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Import necessary components
from src.core.db import get_session, get_async_session
from src.rag.intent_classifier import classify_intent_and_slots
from src.rag.retriever import retrieve_documents
from src.rag.reranker import rerank_documents, cross_encode_rerank
from src.rag.guards import validate_query, numeric_consistency, require_citation
from src.rag.composer import compose_answer


async def process_query(query: str) -> Dict[str, Any]:
    """
    Process a query through the complete RAG pipeline.
    
    Args:
        query: The user query string
        
    Returns:
        Dict with results from each stage of the pipeline
    """
    logger.info(f"Processing query: {query}")
    results = {"query": query, "timestamp": datetime.now().isoformat()}
    
    # Step 1: Validate query
    validation = validate_query(query)
    results["validation"] = validation
    if not validation["valid"]:
        logger.warning(f"Query validation failed: {validation['message']}")
        return results
    
    # Step 2: Classify intent and extract slots
    intent, slots, confidence = classify_intent_and_slots(query)
    results["intent"] = {
        "name": intent,
        "slots": slots,
        "confidence": confidence
    }
    logger.info(f"Classified intent: {intent} with confidence {confidence}")
    logger.info(f"Extracted slots: {slots}")
    
    # Step 3: Retrieve documents
    retrieved_docs = await retrieve_documents(query=query, limit=10)
    results["retrieval"] = {
        "count": len(retrieved_docs),
        "top_docs": [
            {
                "id": doc.get("id"),
                "source_name": doc.get("source_name"),
                "score": doc.get("score"),
                "content_preview": doc.get("content", "")[:100] + "..." if doc.get("content") else ""
            }
            for doc in retrieved_docs[:3]
        ]
    }
    logger.info(f"Retrieved {len(retrieved_docs)} documents")
    
    if not retrieved_docs:
        logger.warning("No documents retrieved")
        results["answer"] = {
            "text": "I'm sorry, I couldn't find any relevant information for your query.",
            "sources": []
        }
        return results
    
    # Step 4: Rerank documents
    # First with simple reranker
    reranked_docs = rerank_documents(query=query, documents=retrieved_docs)
    
    # Then with cross-encoder
    final_docs = cross_encode_rerank(query=query, candidates=reranked_docs, top_n=5)
    
    results["reranking"] = {
        "count": len(final_docs),
        "top_docs": [
            {
                "id": doc.get("id"),
                "source_name": doc.get("source_name"),
                "score": doc.get("score"),
                "content_preview": doc.get("content", "")[:100] + "..." if doc.get("content") else ""
            }
            for doc in final_docs[:3]
        ]
    }
    logger.info(f"Reranked to {len(final_docs)} documents")
    
    # Step 5: Prepare evidence for answer composition
    evidence = []
    for doc in final_docs:
        evidence.append({
            "text": doc.get("content", ""),
            "metadata": {
                "id": doc.get("id"),
                "url": doc.get("url", ""),
                "name": doc.get("source_name", ""),
                "page": doc.get("page_number"),
                "section": doc.get("section")
            }
        })
    
    # Step 6: Compose answer using LLM
    answer_result = compose_answer(query, evidence)
    results["answer"] = answer_result
    logger.info(f"Generated answer: {answer_result.get('answer', '')[:100]}...")
    
    # Step 7: Validate answer with guard functions
    answer_text = answer_result.get("answer", "")
    
    # Check numeric consistency
    num_consistent = numeric_consistency(
        answer_text, 
        [doc.get("content", "") for doc in final_docs]
    )
    results["guards"] = {"numeric_consistency": num_consistent}
    logger.info(f"Numeric consistency check: {num_consistent}")
    
    # Check citation requirement
    has_citations = require_citation(answer_text)
    results["guards"]["has_citations"] = has_citations
    logger.info(f"Citation check: {has_citations}")
    
    return results


async def run_demo():
    """Run the demo with sample queries."""
    # Sample queries to demonstrate different aspects of the system
    sample_queries = [
        "What is the policy on student enrollment?",
        "Tell me about the graduation requirements for Computer Science",
        "How many credits do I need for a bachelor's degree?",
        "What are the course prerequisites for Math 301?",
        "When is the deadline for course withdrawal?"
    ]
    
    # Process each query
    all_results = []
    for query in sample_queries:
        print("\n" + "="*80)
        print(f"QUERY: {query}")
        print("="*80)
        
        result = await process_query(query)
        all_results.append(result)
        
        # Print summary of the result
        if "answer" in result and "answer" in result["answer"]:
            print("\nANSWER:")
            print("-"*80)
            print(result["answer"]["answer"])
            print("-"*80)
            
            if "sources" in result["answer"]:
                print("\nSOURCES:")
                for source in result["answer"]["sources"]:
                    print(f"- {source.get('name', 'Unknown')} ({source.get('url', 'No URL')})")
        
        # Add a pause between queries
        await asyncio.sleep(1)
    
    # Save all results to a file
    output_file = f"demo_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(run_demo())
