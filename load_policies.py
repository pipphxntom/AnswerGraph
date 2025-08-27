"""
Command-line tool for loading policy JSON files into the database.

This script provides a simple interface for loading policy JSON files into the database.
"""
import sys
import os
import argparse
import asyncio
import logging

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingest.policy_loader import load_dir, load_policy_json
from src.core.db import async_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def list_policies_async():
    """List all policies in the database."""
    from sqlalchemy import select
    from src.models.policy import Policy
    from src.models.procedure import Procedure
    from src.models.source import Source
    
    async with async_session_factory() as session:
        # Get policies
        result = await session.execute(select(Policy))
        policies = result.scalars().all()
        
        if not policies:
            print("No policies found in the database.")
            return
        
        print("\nPolicies in database:")
        print("-" * 80)
        
        for policy in policies:
            # Count related entities
            proc_result = await session.execute(
                select(Procedure).where(Procedure.policy_id == policy.id)
            )
            procedures = proc_result.scalars().all()
            
            src_result = await session.execute(
                select(Source).where(Source.policy_id == policy.id)
            )
            sources = src_result.scalars().all()
            
            print(f"ID: {policy.id}")
            print(f"Title: {policy.title}")
            print(f"Issuer: {policy.issuer}")
            print(f"Last Updated: {policy.last_updated}")
            print(f"Procedures: {len(procedures)}")
            print(f"Sources: {len(sources)}")
            print("-" * 80)


async def load_single_file_async(file_path: str):
    """Load a single policy JSON file."""
    async with async_session_factory() as session:
        try:
            policy, procedures, sources = await load_policy_json(file_path, session)
            await session.commit()
            
            print(f"\nSuccessfully loaded policy:")
            print(f"ID: {policy.id}")
            print(f"Title: {policy.title}")
            print(f"Procedures: {len(procedures)}")
            print(f"Sources: {len(sources)}")
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {str(e)}")
            await session.rollback()
            return 1
    
    return 0


async def load_directory_async(dir_path: str):
    """Load all policy JSON files from a directory."""
    try:
        counts = await load_dir(dir_path)
        
        print(f"\nLoading results:")
        print(f"Policies loaded: {counts['policies']}")
        print(f"Procedures loaded: {counts['procedures']}")
        print(f"Sources loaded: {counts['sources']}")
        
        if counts['errors'] > 0:
            print(f"Errors: {counts['errors']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error loading policies: {str(e)}")
        return 1
    
    return 0


async def count_entities_async():
    """Count entities in the database."""
    from sqlalchemy import select, func
    from src.models.policy import Policy
    from src.models.procedure import Procedure
    from src.models.source import Source
    
    async with async_session_factory() as session:
        # Count policies
        policy_count = await session.execute(select(func.count()).select_from(Policy))
        policy_count = policy_count.scalar_one()
        
        # Count procedures
        proc_count = await session.execute(select(func.count()).select_from(Procedure))
        proc_count = proc_count.scalar_one()
        
        # Count sources
        source_count = await session.execute(select(func.count()).select_from(Source))
        source_count = source_count.scalar_one()
        
        print("\nDatabase entity counts:")
        print(f"Policies: {policy_count}")
        print(f"Procedures: {proc_count}")
        print(f"Sources: {source_count}")
    
    return 0


async def main_async():
    parser = argparse.ArgumentParser(description="Load policy JSON files into the database")
    
    # Command subparsers
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Load a directory of policies
    dir_parser = subparsers.add_parser("load-dir", help="Load all policies from a directory")
    dir_parser.add_argument("directory", help="Directory containing JSON policy files")
    
    # Load a single policy file
    file_parser = subparsers.add_parser("load-file", help="Load a single policy JSON file")
    file_parser.add_argument("file", help="Path to the JSON policy file")
    
    # List policies
    subparsers.add_parser("list", help="List all policies in the database")
    
    # Count entities
    subparsers.add_parser("count", help="Count database entities")
    
    args = parser.parse_args()
    
    if args.command == "load-dir":
        return await load_directory_async(args.directory)
    elif args.command == "load-file":
        return await load_single_file_async(args.file)
    elif args.command == "list":
        return await list_policies_async()
    elif args.command == "count":
        return await count_entities_async()
    else:
        parser.print_help()
        return 1


def main():
    """Entry point for the command-line tool."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
