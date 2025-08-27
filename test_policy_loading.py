"""
Test script for policy JSON loading functionality.

This script tests the loading of policy JSON files into the database.
"""
import os
import asyncio
import logging
import argparse
from src.scripts.process_excel_templates import load_dir
from src.core.db import get_async_session, async_session_factory
from sqlalchemy import select
from src.models.policy import Policy
from src.models.procedure import Procedure
from src.models.source import Source

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def count_entities():
    """Count entities in the database."""
    async with async_session_factory() as session:
        # Count policies
        result = await session.execute(select(Policy))
        policies = result.scalars().all()
        
        # Count procedures
        result = await session.execute(select(Procedure))
        procedures = result.scalars().all()
        
        # Count sources
        result = await session.execute(select(Source))
        sources = result.scalars().all()
        
        return {
            "policies": len(policies),
            "procedures": len(procedures),
            "sources": len(sources)
        }

async def list_policies():
    """List all policies in the database."""
    async with async_session_factory() as session:
        result = await session.execute(select(Policy))
        policies = result.scalars().all()
        
        print("\nPolicies in database:")
        print("-" * 80)
        for policy in policies:
            print(f"ID: {policy.id}")
            print(f"Title: {policy.title}")
            print(f"Issuer: {policy.issuer}")
            print(f"Last Updated: {policy.last_updated}")
            
            # Count related entities
            proc_result = await session.execute(
                select(Procedure).where(Procedure.policy_id == policy.id)
            )
            procedures = proc_result.scalars().all()
            
            src_result = await session.execute(
                select(Source).where(Source.policy_id == policy.id)
            )
            sources = src_result.scalars().all()
            
            print(f"Procedures: {len(procedures)}")
            print(f"Sources: {len(sources)}")
            print("-" * 80)

async def main_async():
    parser = argparse.ArgumentParser(description="Test policy JSON loading functionality")
    parser.add_argument(
        "--dir",
        default="data/policies",
        help="Directory containing JSON policy files (default: data/policies)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all policies in the database"
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Count entities in the database"
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Load policy JSON files into the database"
    )
    
    args = parser.parse_args()
    
    if args.count:
        counts = await count_entities()
        print("\nCurrent database counts:")
        print(f"Policies: {counts['policies']}")
        print(f"Procedures: {counts['procedures']}")
        print(f"Sources: {counts['sources']}")
    
    if args.list:
        await list_policies()
    
    if args.load:
        if not os.path.exists(args.dir):
            logger.error(f"Directory does not exist: {args.dir}")
            return 1
            
        logger.info(f"Loading policies from {args.dir}")
        counts = await load_dir(args.dir)
        
        print("\nLoading results:")
        print(f"Policies loaded: {counts['policies']}")
        print(f"Procedures loaded: {counts['procedures']}")
        print(f"Sources loaded: {counts['sources']}")
        print(f"Errors: {counts['errors']}")

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
