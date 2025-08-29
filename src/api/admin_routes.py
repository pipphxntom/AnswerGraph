"""
Admin routes for managing the application.

This module provides administrative endpoints for:
1. Reloading DSL and reindexing policies
2. Viewing policy changes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from src.core.db import get_session
from src.core.config import settings
from src.models.policy import Policy
from src.models.source import Source
from src.ingest.dsl_loader import DSLLoader
from src.ingest.embed_index import index_document_chunks

# Configure logging
logger = logging.getLogger(__name__)

# Create router
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Security - API Key header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Simple API key validation - in production, use a more secure approach
async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate API key."""
    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=403, 
            detail="Invalid or missing API Key"
        )
    return api_key


@admin_router.post("/reload", summary="Reload DSL and reindex policy")
async def reload_policy(
    policy_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(get_api_key)
):
    """
    Reload DSL and reindex a specific policy.
    
    This endpoint:
    1. Reloads the DSL for the specified policy
    2. Reindexes the policy documents in the vector database
    
    Args:
        policy_id: ID of the policy to reload
        background_tasks: Background tasks for long-running operations
        session: Database session
        api_key: API key for authentication
    """
    try:
        # Check if policy exists
        policy = await session.get(Policy, policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy with ID {policy_id} not found")
        
        # Get policy sources
        sources_query = select(Source).where(Source.policy_id == policy_id)
        sources_result = await session.execute(sources_query)
        sources = sources_result.scalars().all()
        
        if not sources:
            raise HTTPException(status_code=404, detail=f"No sources found for policy ID {policy_id}")
        
        # Start reloading in background to avoid blocking the request
        background_tasks.add_task(
            reload_policy_background,
            policy_id=policy_id,
            source_ids=[source.id for source in sources]
        )
        
        return {
            "status": "reloading",
            "message": f"Started reloading policy ID {policy_id} with {len(sources)} sources",
            "policy_id": policy_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading policy {policy_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reloading policy: {str(e)}")


async def reload_policy_background(policy_id: int, source_ids: List[int]) -> None:
    """
    Background task to reload a policy.
    
    Args:
        policy_id: ID of the policy to reload
        source_ids: List of source IDs to reload
    """
    logger.info(f"Starting background reload for policy {policy_id}")
    
    try:
        # Create DSL loader
        dsl_loader = DSLLoader()
        
        # Process each source
        chunks = []
        
        async for session in get_session():
            for source_id in source_ids:
                try:
                    # Get source
                    source = await session.get(Source, source_id)
                    if not source:
                        logger.warning(f"Source {source_id} not found")
                        continue
                    
                    # Parse document
                    source_path = source.url
                    if source_path.startswith("file://"):
                        source_path = source_path[7:]
                    
                    logger.info(f"Parsing document: {source_path}")
                    parsed_doc = await dsl_loader.parse_document(source_path)
                    
                    # Extract chunks
                    if parsed_doc.get("sections"):
                        for section in parsed_doc["sections"]:
                            # Create chunk
                            chunk = {
                                "content": section.get("text", ""),
                                "page_number": section.get("page"),
                                "section": section.get("title"),
                                "source_id": source.id,
                                "policy_id": policy_id
                            }
                            chunks.append(chunk)
                
                except Exception as e:
                    logger.error(f"Error processing source {source_id}: {str(e)}")
            
            # Index chunks
            if chunks:
                logger.info(f"Indexing {len(chunks)} chunks for policy {policy_id}")
                vector_ids = await index_document_chunks(chunks)
                logger.info(f"Indexed {len(vector_ids)} vectors for policy {policy_id}")
            else:
                logger.warning(f"No chunks extracted for policy {policy_id}")
        
    except Exception as e:
        logger.error(f"Error in background reload for policy {policy_id}: {str(e)}")


@admin_router.get("/changes", summary="Get recent policy changes")
async def get_policy_changes(
    days: int = 30,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(get_api_key)
) -> List[Dict[str, Any]]:
    """
    Get list of newest policies by effective_from date.
    
    Args:
        days: Number of days to look back
        limit: Maximum number of policies to return
        session: Database session
        api_key: API key for authentication
        
    Returns:
        List of policy information dictionaries
    """
    try:
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Query for newest policies
        query = (
            select(Policy)
            .where(Policy.effective_from >= cutoff_date)
            .order_by(Policy.effective_from.desc())
            .limit(limit)
        )
        
        result = await session.execute(query)
        policies = result.scalars().all()
        
        # Format response
        policy_changes = []
        for policy in policies:
            policy_changes.append({
                "id": policy.id,
                "title": policy.title,
                "effective_from": policy.effective_from.isoformat() if policy.effective_from else None,
                "effective_to": policy.effective_to.isoformat() if policy.effective_to else None,
                "version": policy.version,
                "status": policy.status
            })
        
        return policy_changes
        
    except Exception as e:
        logger.error(f"Error getting policy changes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting policy changes: {str(e)}")
