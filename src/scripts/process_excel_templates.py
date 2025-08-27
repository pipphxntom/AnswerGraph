"""
Process A2G_templates.xlsx and generate JSON DSL files.

This script reads the FAQ_seed sheet from A2G_templates.xlsx and generates
JSON DSL files in the data/policies directory.
"""
import os
import json
import argparse
import logging
import glob
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd
import uuid
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.models.policy import Policy
from src.models.procedure import Procedure
from src.models.source import Source
from src.core.db import get_async_session, async_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def sanitize_filename(url: str) -> str:
    """Convert URL to a valid filename."""
    # Remove protocol and special characters
    filename = url.replace("http://", "").replace("https://", "")
    filename = filename.replace("/", "_").replace("\\", "_")
    filename = filename.replace(":", "_").replace("?", "_")
    filename = filename.replace("&", "_").replace("=", "_")
    filename = filename.replace(" ", "_").replace("%", "_")
    
    # Limit length and add .json extension
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename


def generate_policy_id(source_url: str) -> str:
    """Generate a unique policy ID based on source URL."""
    # Create a deterministic ID based on URL hash
    url_hash = abs(hash(source_url)) % 10000
    return f"POL-{datetime.now().strftime('%Y')}-{url_hash:04d}"


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """Parse date string into ISO format or return None."""
    if not date_str or pd.isna(date_str):
        return None
    
    try:
        # Handle various date formats
        if isinstance(date_str, datetime):
            return date_str.strftime("%Y-%m-%d")
        
        # Try to parse as datetime
        dt = pd.to_datetime(date_str)
        return dt.strftime("%Y-%m-%d")
    except:
        logger.warning(f"Could not parse date: {date_str}")
        return None


def process_excel_file(excel_path: str, output_dir: str) -> None:
    """
    Process Excel file and generate JSON DSL files.
    
    Args:
        excel_path: Path to the Excel file
        output_dir: Directory where JSON files will be saved
    """
    logger.info(f"Processing Excel file: {excel_path}")
    
    # Check if file exists
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read Excel file
    try:
        df = pd.read_excel(excel_path, sheet_name="FAQ_seed")
        logger.info(f"Successfully read FAQ_seed sheet with {len(df)} rows")
    except Exception as e:
        logger.error(f"Error reading Excel file: {str(e)}")
        raise
    
    # Group by Source URL
    url_groups = {}
    
    for _, row in df.iterrows():
        source_url = row.get("Source URL")
        
        # Skip rows without a source URL
        if not source_url or pd.isna(source_url):
            logger.warning(f"Skipping row without Source URL: {row}")
            continue
        
        # Add to group
        if source_url not in url_groups:
            url_groups[source_url] = []
        
        url_groups[source_url].append(row)
    
    logger.info(f"Found {len(url_groups)} unique Source URLs")
    
    # Process each group
    for source_url, rows in url_groups.items():
        process_url_group(source_url, rows, output_dir)


def process_url_group(source_url: str, rows: List[pd.Series], output_dir: str) -> None:
    """
    Process a group of rows with the same Source URL.
    
    Args:
        source_url: The Source URL for this group
        rows: List of dataframe rows
        output_dir: Directory where JSON file will be saved
    """
    # Generate policy ID based on source URL
    policy_id = generate_policy_id(source_url)
    
    # Create filename from source URL
    filename = sanitize_filename(source_url)
    output_path = os.path.join(output_dir, f"{filename}.json")
    
    # Extract common fields from first row (assuming they're the same for all rows)
    first_row = rows[0]
    
    # Get title and issuer
    title = first_row.get("Title", "")
    if pd.isna(title):
        title = "Untitled Policy"
    
    issuer = first_row.get("Issuer", "")
    if pd.isna(issuer):
        issuer = "Unknown Issuer"
    
    # Parse dates
    effective_from = parse_date(first_row.get("Effective Date"))
    last_updated = parse_date(first_row.get("Last Updated"))
    
    # Collect procedures
    procedures = []
    citations = []
    text_sections = []
    
    # Process each row
    for row in rows:
        # Add procedure if available
        procedure_name = row.get("Procedure")
        if procedure_name and not pd.isna(procedure_name):
            procedure = {
                "id": f"PROC-{uuid.uuid4().hex[:8]}",
                "name": procedure_name
            }
            
            # Add optional procedure fields
            for field in ["Applies To", "Deadlines", "Fees", "Contacts"]:
                value = row.get(field)
                if value and not pd.isna(value):
                    # Convert to appropriate format for JSON
                    if isinstance(value, str):
                        procedure[field.lower().replace(" ", "_")] = value
                    else:
                        procedure[field.lower().replace(" ", "_")] = str(value)
            
            procedures.append(procedure)
        
        # Add citation if available
        citation = row.get("Citation")
        if citation and not pd.isna(citation):
            cite_entry = {
                "text": citation,
                "url": source_url
            }
            
            # Add page number if available
            page = row.get("Page")
            if page and not pd.isna(page):
                cite_entry["page"] = int(page)
            
            citations.append(cite_entry)
        
        # Collect text content
        text = row.get("Text")
        if text and not pd.isna(text):
            text_sections.append(str(text))
    
    # Create policy object
    policy = {
        "policy_id": policy_id,
        "title": title,
        "issuer": issuer,
        "source_url": source_url,
        "procedures": procedures,
        "citations": citations,
        "last_updated": last_updated or datetime.now().strftime("%Y-%m-%d")
    }
    
    # Add effective date if available
    if effective_from:
        policy["effective_from"] = effective_from
    
    # Add full text if available
    if text_sections:
        policy["text_full"] = "\n\n".join(text_sections)
    
    # Save to JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(policy, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Generated policy file: {output_path}")


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
        policy_id = generate_policy_id(data.get("source_url", path))
    
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


def main():
    parser = argparse.ArgumentParser(description="Process A2G_templates.xlsx and generate JSON DSL files")
    parser.add_argument(
        "--excel-file",
        default="A2G_templates.xlsx",
        help="Path to the Excel file (default: A2G_templates.xlsx)"
    )
    parser.add_argument(
        "--output-dir",
        default="data/policies",
        help="Directory where JSON files will be saved (default: data/policies)"
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="Load generated JSON files into database"
    )
    parser.add_argument(
        "--load-dir",
        help="Load JSON files from specified directory into database"
    )
    parser.add_argument(
        "--skip-excel",
        action="store_true",
        help="Skip Excel processing and only load JSON files"
    )
    
    args = parser.parse_args()
    
    # Process Excel file if not skipped
    if not args.skip_excel:
        try:
            process_excel_file(args.excel_file, args.output_dir)
            logger.info("Excel processing complete")
        except Exception as e:
            logger.error(f"Error processing Excel file: {str(e)}")
            return 1
    
    # Handle database loading operations
    if args.load or args.load_dir:
        try:
            # Determine which directory to load from
            load_directory = args.load_dir if args.load_dir else args.output_dir
            
            # Create and run async function
            async def load_policies():
                return await load_dir(load_directory)
            
            # Run the async function
            counts = asyncio.run(load_policies())
            
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


if __name__ == "__main__":
    exit(main())
