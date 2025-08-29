"""
Script to test the /ask endpoint with Gold standard queries from Excel.

This script:
1. Reads queries from the Gold_tests sheet in A2G_templates.xlsx
2. Sends each query to the /ask endpoint
3. Validates responses against expected citations and numeric fields
4. Calculates precision metrics
"""
import os
import sys
import time
import json
import asyncio
import logging
import pandas as pd
import aiohttp
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API endpoint
API_URL = "http://localhost:8000/api/v1"


async def read_gold_tests(excel_path: str) -> pd.DataFrame:
    """
    Read the Gold_tests sheet from the Excel file.
    
    Args:
        excel_path: Path to the Excel file
        
    Returns:
        DataFrame containing the Gold_tests data
    """
    try:
        df = pd.read_excel(excel_path, sheet_name="Gold_tests")
        logger.info(f"Read {len(df)} gold test queries from {excel_path}")
        return df
    except Exception as e:
        logger.error(f"Error reading Excel file: {str(e)}")
        raise


async def test_ask_endpoint(
    session: aiohttp.ClientSession,
    query: str,
    expected_citation: Optional[str] = None,
    expected_numbers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Test the /ask endpoint with a single query.
    
    Args:
        session: aiohttp client session
        query: Query text
        expected_citation: Expected citation filename or pattern
        expected_numbers: List of expected numeric fields in the response
        
    Returns:
        Dictionary with test results
    """
    start_time = time.time()
    
    payload = {
        "text": query,
        "lang": "en"
    }
    
    try:
        async with session.post(f"{API_URL}/ask", json=payload) as response:
            response_time = time.time() - start_time
            
            if response.status != 200:
                error_text = await response.text()
                return {
                    "success": False,
                    "error": f"HTTP {response.status}: {error_text}",
                    "response_time": response_time,
                    "citation_match": False
                }
            
            result = await response.json()
            
            # Check for expected citation
            citation_match = False
            if expected_citation and result.get("sources"):
                for source in result["sources"]:
                    source_url = source.get("url", "")
                    if expected_citation.lower() in source_url.lower():
                        citation_match = True
                        break
            elif not expected_citation:
                citation_match = True  # No citation expected, so consider it a match
            
            # Check for expected numeric fields
            number_matches = []
            if expected_numbers:
                response_text = result.get("text", "")
                for expected_number in expected_numbers:
                    # Clean and normalize the expected number
                    clean_expected = expected_number.strip().replace(",", "")
                    if clean_expected.isdigit():
                        # Look for the exact number in the response
                        pattern = r'\b' + re.escape(clean_expected) + r'\b'
                        match = re.search(pattern, response_text.replace(",", ""))
                        number_matches.append(bool(match))
                    else:
                        # For non-numeric expected values, just check if it's in the text
                        number_matches.append(clean_expected in response_text)
            
            # Calculate FCR (First Call Resolution) - all checks passed
            fcr = citation_match
            if expected_numbers:
                fcr = fcr and all(number_matches)
            
            return {
                "success": True,
                "query": query,
                "response": result,
                "response_time": response_time,
                "citation_match": citation_match,
                "number_matches": number_matches if expected_numbers else [],
                "fcr": fcr
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response_time": time.time() - start_time,
            "citation_match": False
        }


async def run_tests(excel_path: str) -> Dict[str, Any]:
    """
    Run tests for all queries in the Gold_tests sheet.
    
    Args:
        excel_path: Path to the Excel file
        
    Returns:
        Dictionary with test results and metrics
    """
    # Read gold tests
    df = await read_gold_tests(excel_path)
    
    # Initialize metrics
    total_tests = len(df)
    citation_matches = 0
    fcr_count = 0
    response_times = []
    
    # Create results list
    results = []
    
    # Create HTTP session
    async with aiohttp.ClientSession() as session:
        for idx, row in df.iterrows():
            query = row.get("Query", "")
            if not query:
                logger.warning(f"Skipping row {idx+1}: No query found")
                continue
                
            # Get expected citation and numbers
            expected_citation = row.get("Expected Citation", None)
            expected_numbers = []
            
            # Extract expected numbers if any
            for col in df.columns:
                if col.startswith("Expected Number"):
                    value = row.get(col)
                    if pd.notna(value) and value:
                        expected_numbers.append(str(value))
            
            # Run test
            logger.info(f"Testing query {idx+1}/{total_tests}: {query[:50]}...")
            result = await test_ask_endpoint(
                session, query, expected_citation, expected_numbers
            )
            
            # Update metrics
            if result["success"]:
                response_times.append(result["response_time"])
                if result["citation_match"]:
                    citation_matches += 1
                if result.get("fcr", False):
                    fcr_count += 1
            
            # Add to results
            results.append(result)
            
            # Small delay to avoid overwhelming the API
            await asyncio.sleep(0.5)
    
    # Calculate metrics
    citation_precision = citation_matches / total_tests if total_tests > 0 else 0
    fcr = fcr_count / total_tests if total_tests > 0 else 0
    
    # Calculate p95 latency
    p95_latency = None
    if response_times:
        response_times.sort()
        idx = int(len(response_times) * 0.95)
        p95_latency = response_times[idx] if idx < len(response_times) else response_times[-1]
    
    metrics = {
        "total_tests": total_tests,
        "citation_precision": citation_precision,
        "fcr": fcr,
        "p95_latency": p95_latency,
        "avg_latency": sum(response_times) / len(response_times) if response_times else None
    }
    
    return {
        "metrics": metrics,
        "results": results
    }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test the /ask endpoint with Gold standard queries")
    parser.add_argument("--excel", default="A2G_templates.xlsx", help="Path to the Excel file")
    parser.add_argument("--output", default="gold_test_results.json", help="Path to save results")
    
    args = parser.parse_args()
    
    try:
        # Run tests
        logger.info(f"Starting tests with {args.excel}")
        results = await run_tests(args.excel)
        
        # Print metrics
        metrics = results["metrics"]
        logger.info("===== Test Results =====")
        logger.info(f"Total Tests: {metrics['total_tests']}")
        logger.info(f"Citation Precision: {metrics['citation_precision']:.2f}")
        logger.info(f"First Call Resolution: {metrics['fcr']:.2f}")
        logger.info(f"P95 Latency: {metrics['p95_latency']:.2f} seconds")
        logger.info(f"Average Latency: {metrics['avg_latency']:.2f} seconds")
        
        # Save results
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.output}")
        
    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
