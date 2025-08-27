#!/usr/bin/env python
"""
Deterministic Fetch Demo

This script demonstrates the deterministic fetch functionality for joining
Procedure, Policy, and Source data and returning formatted results.
"""
import sys
import asyncio
import argparse
import json
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.db import async_session_factory
from src.rag.deterministic_fetch import (
    deterministic_fetch,
    fetch_procedure_with_related,
    fetch_by_program_and_term
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


async def run_procedure_query(procedure_id=None, policy_id=None):
    """Run a procedure query with the given parameters."""
    async with async_session_factory() as session:
        logger.info(f"Fetching procedure data: procedure_id={procedure_id}, policy_id={policy_id}")
        
        procedures = await fetch_procedure_with_related(
            session=session,
            procedure_id=procedure_id,
            policy_id=policy_id
        )
        
        print(f"\nFound {len(procedures)} procedures\n")
        for proc in procedures:
            print(json.dumps(proc, indent=2))
            print("-" * 80)


async def run_program_query(program, term=None, campus=None):
    """Run a program query with the given parameters."""
    async with async_session_factory() as session:
        logger.info(f"Fetching program data: program={program}, term={term}, campus={campus}")
        
        procedures = await fetch_by_program_and_term(
            session=session,
            program=program,
            term=term,
            campus=campus
        )
        
        print(f"\nFound {len(procedures)} procedures for program '{program}'\n")
        for proc in procedures:
            print(json.dumps(proc, indent=2))
            print("-" * 80)


async def run_deterministic_query(query_type, **params):
    """Run a deterministic query with the given parameters."""
    async with async_session_factory() as session:
        logger.info(f"Running deterministic query: type={query_type}, params={params}")
        
        result = await deterministic_fetch(
            session=session,
            query_type=query_type,
            params=params
        )
        
        print("\nQuery result:\n")
        print(json.dumps(result, indent=2))


async def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Deterministic Fetch Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Procedure query
    proc_parser = subparsers.add_parser("procedure", help="Query procedures")
    proc_parser.add_argument("--id", help="Procedure ID")
    proc_parser.add_argument("--policy-id", help="Policy ID")
    
    # Program query
    program_parser = subparsers.add_parser("program", help="Query by program")
    program_parser.add_argument("name", help="Program name")
    program_parser.add_argument("--term", help="Term or semester")
    program_parser.add_argument("--campus", help="Campus location")
    
    # Deterministic query
    det_parser = subparsers.add_parser("query", help="Run deterministic query")
    det_parser.add_argument("type", choices=["procedure", "program_info", "deadline_info", "fee_info"],
                           help="Query type")
    det_parser.add_argument("--program", help="Program name")
    det_parser.add_argument("--term", help="Term or semester")
    det_parser.add_argument("--campus", help="Campus location")
    det_parser.add_argument("--procedure-id", help="Procedure ID")
    det_parser.add_argument("--policy-id", help="Policy ID")
    
    args = parser.parse_args()
    
    if args.command == "procedure":
        await run_procedure_query(args.id, args.policy_id)
    elif args.command == "program":
        await run_program_query(args.name, args.term, args.campus)
    elif args.command == "query":
        # Build params dict from arguments
        params = {}
        if args.program:
            params["program"] = args.program
        if args.term:
            params["term"] = args.term
        if args.campus:
            params["campus"] = args.campus
        if args.procedure_id:
            params["procedure_id"] = args.procedure_id
        if args.policy_id:
            params["policy_id"] = args.policy_id
        
        await run_deterministic_query(args.type, **params)
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
