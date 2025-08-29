from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel

from src.core.db import get_session
from src.rag.retriever import retrieve_documents
from src.rag.reranker import rerank_documents
from src.rag.router import route_query
from src.rag.guards import validate_query
from src.models.policy import Policy
from src.models.procedure import Procedure
from src.models.source import Source
from src.models.chunk import Chunk
from src.api.ask_routes import ask_router

router = APIRouter()

# Include the ask router
router.include_router(ask_router, tags=["ask"])


class HealthResponse(BaseModel):
    """Model for health check response."""
    status: str = "ok"


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint for the API."""
    return HealthResponse()


class QueryRequest(BaseModel):
    """Model for query requests."""
    query: str
    limit: Optional[int] = 5
    filters: Optional[dict] = None


class ChunkResponse(BaseModel):
    """Model for chunk responses."""
    id: int
    content: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    relevance_score: Optional[float] = None


class QueryResponse(BaseModel):
    """Model for query responses."""
    query: str
    chunks: List[ChunkResponse]
    query_type: Optional[str] = None
    processing_time: Optional[float] = None


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session)
):
    """Query documents using RAG."""
    # Guard clause to validate query
    validation_result = validate_query(request.query)
    if not validation_result["valid"]:
        raise HTTPException(status_code=400, detail=validation_result["message"])
    
    # Route query to appropriate handler
    query_type = route_query(request.query)
    
    # Retrieve relevant documents
    retrieval_results = await retrieve_documents(
        query=request.query,
        limit=request.limit,
        filters=request.filters
    )
    
    # Rerank results if we have enough documents
    if len(retrieval_results) > 1:
        retrieval_results = rerank_documents(
            query=request.query,
            documents=retrieval_results
        )
    
    # Convert to response model
    chunks = [
        ChunkResponse(
            id=result["id"],
            content=result["content"],
            page_number=result.get("page_number"),
            section=result.get("section"),
            source_name=result.get("source_name"),
            source_type=result.get("source_type"),
            relevance_score=result.get("score")
        )
        for result in retrieval_results
    ]
    
    return QueryResponse(
        query=request.query,
        chunks=chunks,
        query_type=query_type,
        processing_time=retrieval_results[0].get("processing_time") if retrieval_results else None
    )


@router.get("/policies", response_model=List[dict])
async def get_policies(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all policies."""
    policies = await session.execute(
        Policy.__table__.select().offset(skip).limit(limit)
    )
    return policies.mappings().all()


@router.get("/procedures", response_model=List[dict])
async def get_procedures(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all procedures."""
    procedures = await session.execute(
        Procedure.__table__.select().offset(skip).limit(limit)
    )
    return procedures.mappings().all()


@router.get("/sources", response_model=List[dict])
async def get_sources(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Get all sources."""
    sources = await session.execute(
        Source.__table__.select().offset(skip).limit(limit)
    )
    return sources.mappings().all()
