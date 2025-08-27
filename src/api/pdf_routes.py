"""
Streaming PDF policy API endpoints.

This module implements FastAPI endpoints for processing PDFs with streaming responses,
allowing for immediate feedback during long-running operations.
"""
from typing import Dict, Any, List, Optional
import os
import asyncio
import tempfile
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from src.core.db import get_session
from src.ingest.pdf.enhanced_processor import EnhancedPDFProcessor, ProcessingConfig
from src.models.policy import Policy

router = APIRouter(prefix="/pdf", tags=["PDF Processing"])

# Request/response models
class ProcessPDFRequest(BaseModel):
    """Request model for PDF processing."""
    title: Optional[str] = Field(None, description="Policy title")
    issuer: str = Field("Organization", description="Policy issuer")
    min_tokens: int = Field(200, description="Minimum tokens per chunk")
    max_tokens: int = Field(400, description="Maximum tokens per chunk")
    store_in_db: bool = Field(True, description="Whether to store in database")


class ChunkProgress(BaseModel):
    """Progress information for chunk processing."""
    total_pages: int = Field(..., description="Total pages in document")
    processed_pages: int = Field(..., description="Pages processed so far")
    chunk_count: int = Field(..., description="Number of chunks created")
    percentage: float = Field(..., description="Percentage complete")
    status: str = Field(..., description="Current status")


class ProcessingResult(BaseModel):
    """Result of PDF processing."""
    policy_id: Optional[str] = Field(None, description="ID of created policy")
    title: str = Field(..., description="Policy title")
    chunk_count: int = Field(..., description="Number of chunks created")
    total_tokens: int = Field(..., description="Total tokens processed")
    avg_tokens_per_chunk: float = Field(..., description="Average tokens per chunk")


# Track background tasks
_active_tasks: Dict[str, Dict[str, Any]] = {}


async def _process_pdf_task(
    file_path: str,
    task_id: str,
    title: Optional[str] = None,
    issuer: str = "Organization",
    min_tokens: int = 200,
    max_tokens: int = 400,
    store_in_db: bool = True
):
    """Background task for processing PDFs."""
    try:
        # Update task status
        _active_tasks[task_id]["status"] = "processing"
        
        # Configure processor
        config = ProcessingConfig(
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            chunk_strategy="semantic"
        )
        
        # Create processor
        processor = EnhancedPDFProcessor(config)
        
        # Start processing and track progress
        result = await processor.process_pdf(file_path)
        metadata = result["metadata"]
        chunks = result["chunks"]
        stats = result["stats"]
        
        # Update progress information
        _active_tasks[task_id].update({
            "metadata": metadata,
            "chunks": chunks,
            "stats": stats,
            "progress": {
                "total_pages": metadata.page_count,
                "processed_pages": metadata.page_count,
                "chunk_count": len(chunks),
                "percentage": 100.0,
                "status": "processed"
            }
        })
        
        # Store in database if requested
        if store_in_db and chunks:
            policy_result = await processor.create_policy_from_pdf(
                file_path=file_path,
                title=title or metadata.title or os.path.basename(file_path),
                issuer=issuer
            )
            
            _active_tasks[task_id]["policy_id"] = policy_result["policy_id"]
            _active_tasks[task_id]["status"] = "completed"
        else:
            _active_tasks[task_id]["status"] = "processed"
        
    except Exception as e:
        # Update task with error
        _active_tasks[task_id]["status"] = "error"
        _active_tasks[task_id]["error"] = str(e)
    finally:
        # Clean up temp file
        try:
            if os.path.exists(file_path) and file_path.startswith(tempfile.gettempdir()):
                os.unlink(file_path)
        except Exception:
            pass


@router.post("/process")
async def process_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: ProcessPDFRequest = Depends()
) -> Dict[str, str]:
    """
    Process a PDF file and create policy document.
    
    This endpoint uploads a PDF, processes it asynchronously,
    and returns a task ID for tracking progress.
    """
    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.close()
    
    with open(temp_file.name, "wb") as f:
        f.write(await file.read())
    
    # Generate task ID
    import uuid
    task_id = str(uuid.uuid4())
    
    # Initialize task tracking
    _active_tasks[task_id] = {
        "status": "starting",
        "file_path": temp_file.name,
        "filename": file.filename,
        "progress": {
            "total_pages": 0,
            "processed_pages": 0,
            "chunk_count": 0,
            "percentage": 0,
            "status": "starting"
        }
    }
    
    # Start background processing
    background_tasks.add_task(
        _process_pdf_task,
        file_path=temp_file.name,
        task_id=task_id,
        title=request.title,
        issuer=request.issuer,
        min_tokens=request.min_tokens,
        max_tokens=request.max_tokens,
        store_in_db=request.store_in_db
    )
    
    return {"task_id": task_id}


@router.get("/progress/{task_id}")
async def get_processing_progress(task_id: str) -> ChunkProgress:
    """Get progress information for a processing task."""
    if task_id not in _active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = _active_tasks[task_id]
    progress = task.get("progress", {})
    
    return ChunkProgress(
        total_pages=progress.get("total_pages", 0),
        processed_pages=progress.get("processed_pages", 0),
        chunk_count=progress.get("chunk_count", 0),
        percentage=progress.get("percentage", 0),
        status=task.get("status", "unknown")
    )


@router.get("/result/{task_id}")
async def get_processing_result(task_id: str) -> ProcessingResult:
    """Get the final result of PDF processing."""
    if task_id not in _active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = _active_tasks[task_id]
    
    if task.get("status") not in ["completed", "processed"]:
        raise HTTPException(status_code=400, detail=f"Processing not complete. Current status: {task.get('status')}")
    
    stats = task.get("stats", {})
    metadata = task.get("metadata", {})
    
    return ProcessingResult(
        policy_id=task.get("policy_id"),
        title=task.get("title") or metadata.get("title") or task.get("filename", "Untitled"),
        chunk_count=stats.get("chunk_count", 0),
        total_tokens=stats.get("total_tokens", 0),
        avg_tokens_per_chunk=stats.get("avg_tokens", 0)
    )


@router.get("/stream/{task_id}")
async def stream_processing_updates(task_id: str):
    """
    Stream real-time updates of PDF processing.
    
    This endpoint returns a server-sent events (SSE) stream with
    progress updates during processing.
    """
    if task_id not in _active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def event_generator():
        """Generate SSE events for progress updates."""
        last_status = None
        last_percentage = -1
        
        while True:
            task = _active_tasks.get(task_id)
            if not task:
                # Task was removed
                yield f"data: {json.dumps({'status': 'removed'})}\n\n"
                break
                
            status = task.get("status")
            progress = task.get("progress", {})
            percentage = progress.get("percentage", 0)
            
            # Only send updates when something changes
            if status != last_status or abs(percentage - last_percentage) >= 1:
                yield f"data: {json.dumps({'status': status, 'progress': progress})}\n\n"
                last_status = status
                last_percentage = percentage
            
            # Exit loop when processing is done
            if status in ["completed", "processed", "error"]:
                # Send final event with result or error
                if status == "error":
                    yield f"data: {json.dumps({'status': 'error', 'error': task.get('error')})}\n\n"
                else:
                    stats = task.get("stats", {})
                    yield f"data: {json.dumps({'status': status, 'result': {
                        'policy_id': task.get('policy_id'),
                        'chunk_count': stats.get('chunk_count', 0),
                        'total_tokens': stats.get('total_tokens', 0)
                    }})}\n\n"
                break
            
            # Wait before checking again
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/policies")
async def list_pdf_policies(
    session = Depends(get_session),
    limit: int = 10,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """List policies created from PDFs."""
    # Query for policies with PDF sources
    query = (
        session.query(Policy)
        .filter(Policy.sources.any(url.like("file://%")))
        .order_by(Policy.last_updated.desc())
        .limit(limit)
        .offset(offset)
    )
    
    policies = await query.all()
    
    # Format response
    return [
        {
            "id": policy.id,
            "title": policy.title,
            "issuer": policy.issuer,
            "effective_from": policy.effective_from,
            "is_active": policy.is_active,
            "chunk_count": len(policy.chunks)
        }
        for policy in policies
    ]
