"""
Policy JSON loader functionality.
"""
import os
import json
import glob
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from standalone_loader.models import Policy, Procedure, Source
from standalone_loader.db import async_session_factory

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
        
        return {
            "policies": policy_count,
            "procedures": proc_count,
            "sources": source_count
        }
