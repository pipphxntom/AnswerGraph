"""
Policy loader script.

This script implements functions to load policy JSON files into the database.
"""
import os
import json
import argparse
import logging
import glob
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

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
    
    This function reads a JSON policy file and creates or updates the corresponding
    Policy, Procedure, and Source records in the database. It uses an upsert pattern
    to handle both new and existing records.
    
    Args:
        path: Path to the JSON file containing policy data
        session: AsyncSession for database operations (transaction should be managed by caller)
        
    Returns:
        Tuple of (Policy, List[Procedure], List[Source]) objects that were created or updated
        
    Notes:
        - This function does not commit the session, allowing it to be used within larger transactions
        - It does flush the session to ensure relations are properly set up
        - Existing records are updated with new values
        - New records are created if they don't exist
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
    
    This function scans a directory for JSON files, loads each one using load_policy_json,
    and commits all changes to the database in a single transaction. It manages its own
    database session and handles errors for individual files, allowing the process to
    continue even if some files fail.
    
    Args:
        dirpath: Path to directory containing JSON policy files
        
    Returns:
        Dictionary with counts of loaded entities:
        {
            "policies": int,  # Number of policies successfully loaded
            "procedures": int,  # Number of procedures successfully loaded
            "sources": int,  # Number of sources successfully loaded
            "errors": int  # Number of files that failed to load
        }
        
    Notes:
        - Creates and manages its own database session
        - Handles transaction commit/rollback
        - Continues processing if individual files fail
        - Reports detailed statistics on success/failure
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


async def main_async(args):
    # Handle database loading operations
    if args.load_dir:
        try:
            # Load from specified directory
            counts = await load_dir(args.load_dir)
            
            # Report results
            logger.info(f"Database loading complete:")
            logger.info(f"  - Policies: {counts['policies']}")
            logger.info(f"  - Procedures: {counts['procedures']}")
            logger.info(f"  - Sources: {counts['sources']}")
            if counts['errors'] > 0:
                logger.warning(f"  - Errors: {counts['errors']}")
                return 1
        except Exception as e:
            logger.error(f"Error loading policies into database: {str(e)}")
            return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Load policy JSON files into the database")
    parser.add_argument(
        "--load-dir",
        required=True,
        help="Directory containing JSON policy files to load"
    )
    
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    exit(main())
