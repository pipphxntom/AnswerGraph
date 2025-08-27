"""
Policy JSON loader for A2G.

This script provides functions to load policy JSON files into the database.
"""
import os
import json
import glob
import uuid
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.policy import Policy
from src.models.procedure import Procedure
from src.models.source import Source
from src.core.db import async_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def load_policy_json(path: str, session: AsyncSession) -> Tuple[Policy, List[Procedure], List[Source]]:
    """
    Load a policy JSON DSL file and upsert to the database.
    
    Args:
        path: Path to the JSON file
        session: AsyncSession for database operations
        
    Returns:
        Tuple of (Policy, List[Procedure], List[Source]) objects
    """
    logger.info(f"Loading policy from: {path}")
    
    # Read JSON file
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract policy data
    policy_id = data.get("policy_id")
    if not policy_id:
        # Generate a policy ID if not provided
        policy_id = f"POL-{uuid.uuid4().hex[:8]}"
    
    # Convert dates from strings to date objects
    effective_from = None
    if data.get("effective_from"):
        try:
            effective_from = datetime.strptime(data["effective_from"], "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid effective_from date format in {path}")
    
    last_updated = None
    if data.get("last_updated"):
        try:
            last_updated = datetime.strptime(data["last_updated"], "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid last_updated date format in {path}")
    
    # Create policy object
    policy = Policy(
        id=policy_id,
        title=data.get("title", "Untitled Policy"),
        issuer=data.get("issuer", "Unknown Issuer"),
        effective_from=effective_from,
        expires_on=None,  # Not in JSON format
        scope={},  # Default empty JSON
        text_full=data.get("text_full"),
        last_updated=last_updated or datetime.now().date()
    )
    
    # Upsert policy using SQLAlchemy 2.0 style
    stmt = select(Policy).where(Policy.id == policy_id)
    result = await session.execute(stmt)
    existing_policy = result.scalars().first()
    
    if existing_policy:
        # Update existing policy
        existing_policy.title = policy.title
        existing_policy.issuer = policy.issuer
        existing_policy.effective_from = policy.effective_from
        existing_policy.text_full = policy.text_full
        existing_policy.last_updated = policy.last_updated
        # Don't overwrite these if they exist
        if existing_policy.expires_on:
            policy.expires_on = existing_policy.expires_on
        if existing_policy.scope:
            policy.scope = existing_policy.scope
        policy = existing_policy
    else:
        # Add new policy
        session.add(policy)
    
    # Handle procedures
    procedures = []
    for proc_data in data.get("procedures", []):
        proc_id = proc_data.get("id")
        if not proc_id:
            proc_id = f"PROC-{uuid.uuid4().hex[:8]}"
        
        procedure = Procedure(
            id=proc_id,
            policy_id=policy_id,
            name=proc_data.get("name", "Unnamed Procedure"),
            applies_to=proc_data.get("applies_to", {}),
            deadlines=proc_data.get("deadlines", {}),
            fees=proc_data.get("fees", {}),
            contacts=proc_data.get("contacts", {})
        )
        
        # Check if procedure exists
        stmt = select(Procedure).where(Procedure.id == proc_id)
        result = await session.execute(stmt)
        existing_proc = result.scalars().first()
        
        if existing_proc:
            # Update existing procedure
            existing_proc.name = procedure.name
            existing_proc.applies_to = procedure.applies_to
            existing_proc.deadlines = procedure.deadlines
            existing_proc.fees = procedure.fees
            existing_proc.contacts = procedure.contacts
            procedures.append(existing_proc)
        else:
            # Add new procedure
            session.add(procedure)
            procedures.append(procedure)
    
    # Handle sources (citations)
    sources = []
    for idx, cite_data in enumerate(data.get("citations", [])):
        source_id = f"SRC-{policy_id}-{idx}"
        
        source = Source(
            id=source_id,
            policy_id=policy_id,
            url=cite_data.get("url", data.get("source_url", "")),
            page=cite_data.get("page"),
            clause=cite_data.get("text", ""),
            bbox={}  # Default empty JSON
        )
        
        # Check if source exists
        stmt = select(Source).where(Source.id == source_id)
        result = await session.execute(stmt)
        existing_source = result.scalars().first()
        
        if existing_source:
            # Update existing source
            existing_source.url = source.url
            existing_source.page = source.page
            existing_source.clause = source.clause
            sources.append(existing_source)
        else:
            # Add new source
            session.add(source)
            sources.append(source)
    
    # Flush changes to get IDs (but don't commit yet)
    await session.flush()
    
    return policy, procedures, sources


async def load_dir(dirpath: str) -> Dict[str, int]:
    """
    Load all JSON policy files from a directory into the database.
    
    Args:
        dirpath: Path to directory containing JSON files
        
    Returns:
        Dictionary with counts of loaded entities
    """
    logger.info(f"Loading policies from directory: {dirpath}")
    
    # Find all JSON files
    json_files = glob.glob(os.path.join(dirpath, "*.json"))
    logger.info(f"Found {len(json_files)} JSON files")
    
    counts = {
        "policies": 0,
        "procedures": 0,
        "sources": 0,
        "errors": 0
    }
    
    # Create async session
    async with async_session_factory() as session:
        try:
            # Process each file
            for json_file in json_files:
                try:
                    policy, procedures, sources = await load_policy_json(json_file, session)
                    counts["policies"] += 1
                    counts["procedures"] += len(procedures)
                    counts["sources"] += len(sources)
                    logger.info(f"Loaded policy {policy.id} with {len(procedures)} procedures and {len(sources)} sources")
                except Exception as e:
                    logger.error(f"Error loading {json_file}: {str(e)}")
                    counts["errors"] += 1
            
            # Commit all changes
            await session.commit()
            logger.info(f"Successfully committed {counts['policies']} policies to database")
            
        except Exception as e:
            logger.error(f"Error loading policies: {str(e)}")
            await session.rollback()
            raise
    
    return counts


async def count_entities():
    """Count entities in the database."""
    from sqlalchemy import func
    
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
    
    return {
        "policies": policy_count,
        "procedures": proc_count,
        "sources": source_count
    }


async def list_policies():
    """List all policies in the database."""
    async with async_session_factory() as session:
        # Get policies
        result = await session.execute(select(Policy))
        policies = result.scalars().all()
        
        if not policies:
            print("No policies found in the database.")
            return []
        
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
        
        return policies


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
    
    args = parser.parse_args()
    
    # Execute requested command
    if args.command == "load-dir":
        counts = await load_dir(args.dir_path)
        print(f"\nLoaded {counts['policies']} policies")
        print(f"Loaded {counts['procedures']} procedures")
        print(f"Loaded {counts['sources']} sources")
        print(f"Errors: {counts['errors']}")
        
    elif args.command == "load-file":
        async with async_session_factory() as session:
            try:
                policy, procedures, sources = await load_policy_json(args.file_path, session)
                await session.commit()
                print(f"\nLoaded policy {policy.id}")
                print(f"Loaded {len(procedures)} procedures")
                print(f"Loaded {len(sources)} sources")
            except Exception as e:
                await session.rollback()
                print(f"Error: {str(e)}")
                return 1
    
    elif args.command == "list":
        await list_policies()
    
    elif args.command == "count":
        await count_entities()
    
    else:
        parser.print_help()
        return 1
    
    return 0


def main():
    """Command-line entry point."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    import sys
    sys.exit(main())
