"""
Command-line interface for policy loader.
"""
import os
import sys
import asyncio
import argparse
import logging

from standalone_loader.loader import load_policy_json, load_dir, count_entities
from standalone_loader.db import async_session_factory, init_db
from standalone_loader.models import Policy, Procedure, Source

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def init_database():
    """Initialize the database by creating tables."""
    await init_db()
    print("Database initialized successfully")


async def list_policies():
    """List all policies in the database."""
    from sqlalchemy import select
    
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


async def show_counts():
    """Show database entity counts."""
    counts = await count_entities()
    
    print("\nDatabase entity counts:")
    print(f"Policies: {counts['policies']}")
    print(f"Procedures: {counts['procedures']}")
    print(f"Sources: {counts['sources']}")


async def load_single_file(file_path: str):
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


async def main_async():
    parser = argparse.ArgumentParser(description="Load policy JSON files into the database")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Load directory command
    load_dir_parser = subparsers.add_parser("load-dir", help="Load all JSON files from a directory")
    load_dir_parser.add_argument("dir_path", help="Path to directory containing JSON files")
    
    # Load file command
    load_file_parser = subparsers.add_parser("load-file", help="Load a single JSON file")
    load_file_parser.add_argument("file_path", help="Path to JSON file")
    
    # List command
    subparsers.add_parser("list", help="List all policies in the database")
    
    # Count command
    subparsers.add_parser("count", help="Count entities in the database")
    
    # Init database command
    subparsers.add_parser("init-db", help="Initialize the database by creating tables")
    
    args = parser.parse_args()
    
    # Initialize database for all commands that need it
    if args.command != "init-db" and args.command is not None:
        await init_db()
    
    # Execute requested command
    if args.command == "load-dir":
        counts = await load_dir(args.dir_path)
        print(f"\nLoaded {counts['policies']} policies")
        print(f"Loaded {counts['procedures']} procedures")
        print(f"Loaded {counts['sources']} sources")
        print(f"Errors: {counts['errors']}")
        
    elif args.command == "load-file":
        return await load_single_file(args.file_path)
    
    elif args.command == "list":
        await list_policies()
    
    elif args.command == "count":
        await show_counts()
    
    elif args.command == "init-db":
        await init_database()
    
    else:
        parser.print_help()
        return 1
    
    return 0


def main():
    """Command-line entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
