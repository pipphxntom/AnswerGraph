"""
Updated version of the ask_routes.py module with integrated guards.

This version integrates the full apply_guards function into the answer pipeline,
ensuring consistency checks are applied across both rule-based and RAG paths.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import time
import logging
import asyncio

from src.core.db import get_session
from src.core.rule_settings import RULE_INTENTS, STATS
from src.rag.intent_classifier import classify_intent_and_slots
from src.rag.rule_answers import answer_from_rules 
from src.rag.retriever import retrieve_documents
from src.rag.reranker import rerank_documents, cross_encode_rerank
from src.rag.guards import validate_query, apply_guards
from src.rag.deterministic_fetch import deterministic_fetch
from src.rag.composer import compose_answer
from src.schemas.answer import SourceInfo, GuardResult, GuardResults, AnswerContract

# Configure logging
logger = logging.getLogger(__name__)

# Create router
ask_router = APIRouter()


class AskRequest(BaseModel):
    """Model for ask requests."""
    text: str
    lang: Optional[str] = "en"
    ctx: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Model for health check responses."""
    status: str
    version: str
    uptime: float
    timestamp: str


class StatsResponse(BaseModel):
    """Model for statistics responses."""
    total_requests: int
    rule_based_responses: int
    rag_responses: int
    intent_distribution: Dict[str, int]
    avg_response_time: float


def update_stats(
    intent: str, 
    is_rule_based: bool, 
    response_time: float
) -> None:
    """
    Update system statistics.
    
    Args:
        intent: The classified intent
        is_rule_based: Whether the response was rule-based
        response_time: Response time in milliseconds
    """
    STATS["total_requests"] += 1
    
    if is_rule_based:
        STATS["rule_based_responses"] += 1
    else:
        STATS["rag_responses"] += 1
    
    # Update intent distribution
    if intent in STATS["intent_distribution"]:
        STATS["intent_distribution"][intent] += 1
    else:
        STATS["intent_distribution"][intent] = 1
    
    # Update response times
    STATS["response_times"].append(response_time)
    if len(STATS["response_times"]) > 1000:
        STATS["response_times"].pop(0)  # Keep only the last 1000 times
    
    # Update average response time
    STATS["avg_response_time"] = sum(STATS["response_times"]) / len(STATS["response_times"])


async def process_rule_answer(
    rule_answer_dict: Dict[str, Any], 
    query: str,
    session: AsyncSession
) -> AnswerContract:
    """
    Process a rule-based answer with guards and convert to standard contract.
    
    Args:
        rule_answer_dict: Dictionary representation of rule answer
        query: Original user query
        session: Database session
        
    Returns:
        Standardized AnswerContract
    """
    # Apply guards to rule-based answer
    guards_to_apply = ["citation", "temporal"]
    
    passed, reasons, details = await apply_guards(
        answer_contract=rule_answer_dict,
        session=session,
        guards_to_apply=guards_to_apply,
        query=query
    )
    
    # Create guard results
    guard_results = GuardResults()
    
    if "citation" in details:
        guard_results.citation = GuardResult(
            passed=details["citation"]["passed"],
            message=details["citation"]["message"],
            details=details["citation"].get("details")
        )
    
    if "temporal" in details:
        guard_results.temporal = GuardResult(
            passed=details["temporal"]["passed"],
            message=details["temporal"]["message"],
            details=details["temporal"].get("details")
        )
    
    if "overall" in details:
        guard_results.overall = GuardResult(
            passed=details["overall"]["passed"],
            message="; ".join(reasons),
            details=details["overall"]
        )
    
    # Prepare disambiguation options if available
    disambiguation_options = None
    if "disambiguation" in details and details["disambiguation"].get("disambiguation_options"):
        disambiguation_options = details["disambiguation"]["disambiguation_options"]
    
    # Create standardized sources
    sources = []
    for source in rule_answer_dict.get("sources", []):
        sources.append(SourceInfo(
            policy_id=source.get("policy_id"),
            procedure_id=source.get("procedure_id"),
            url=source.get("url", ""),
            name=source.get("name"),
            page=source.get("page"),
            section=source.get("section")
        ))
    
    # Create the standardized answer contract
    answer_contract = AnswerContract(
        text=rule_answer_dict["text"],
        sources=sources,
        intent=rule_answer_dict["intent"],
        slots=rule_answer_dict["slots"],
        confidence=rule_answer_dict["confidence"],
        updated_date=rule_answer_dict.get("updated_date", ""),
        guard_results=guard_results,
        disambiguation_options=disambiguation_options
    )
    
    return answer_contract


async def compose_rag_answer(
    query: str,
    retrieved_docs: List[Dict[str, Any]],
    slots: Optional[Dict[str, str]] = None,
    session: AsyncSession = None
) -> AnswerContract:
    """
    Compose an answer using RAG from retrieved documents.
    
    Uses the compose_answer function with an LLM to generate a structured response.
    Falls back to deterministic fetch for certain query types.
    
    Args:
        query: The user's query
        retrieved_docs: The retrieved documents
        slots: Any extracted slots
        session: Database session
        
    Returns:
        AnswerContract object
    """
    # First check if we can use deterministic fetch for structured answer
    if session and slots and "program" in slots:
        try:
            # Try deterministic fetch with program info
            result = await deterministic_fetch(
                session=session,
                query_type="program_info",
                params={"program": slots["program"], "term": slots.get("semester")}
            )
            
            if result and result.get("answer") and result.get("source", {}).get("url"):
                # Create sources list
                sources = []
                if result.get("source"):
                    source = result["source"]
                    if source.get("url"):
                        sources.append(SourceInfo(
                            policy_id=result.get("policy", {}).get("id"),
                            url=source.get("url"),
                            page=source.get("page"),
                            name=source.get("title"),
                            updated_at=source.get("updated_at")
                        ))
                
                # Create answer contract dict for guards
                answer_dict = {
                    "text": result["answer"],
                    "sources": [s.dict() for s in sources],
                    "intent": "freeform",
                    "slots": slots or {},
                    "confidence": 0.8,
                    "updated_date": result.get("source", {}).get("updated_at")
                }
                
                # Apply guards
                guards_to_apply = ["citation", "numeric", "disambiguation"]
                evidence_texts = [result.get("evidence", "")]
                
                passed, reasons, details = await apply_guards(
                    answer_contract=answer_dict,
                    evidence_texts=evidence_texts,
                    session=session,
                    guards_to_apply=guards_to_apply,
                    query=query
                )
                
                # Create guard results
                guard_results = GuardResults()
                
                if "citation" in details:
                    guard_results.citation = GuardResult(
                        passed=details["citation"]["passed"],
                        message=details["citation"]["message"],
                        details=details["citation"].get("details")
                    )
                
                if "numeric" in details:
                    guard_results.numeric = GuardResult(
                        passed=details["numeric"]["passed"],
                        message=details["numeric"]["message"],
                        details=details["numeric"].get("details")
                    )
                
                if "disambiguation" in details:
                    guard_results.disambiguation = GuardResult(
                        passed=details["disambiguation"]["passed"],
                        message=details["disambiguation"]["message"],
                        details=details["disambiguation"].get("details")
                    )
                
                if "overall" in details:
                    guard_results.overall = GuardResult(
                        passed=details["overall"]["passed"],
                        message="; ".join(reasons),
                        details=details["overall"]
                    )
                
                # Prepare disambiguation options if available
                disambiguation_options = None
                if "disambiguation" in details and details["disambiguation"].get("disambiguation_options"):
                    disambiguation_options = details["disambiguation"]["disambiguation_options"]
                
                return AnswerContract(
                    text=result["answer"],
                    sources=sources,
                    intent="freeform",
                    slots=slots or {},
                    confidence=0.8,
                    updated_date=result.get("source", {}).get("updated_at"),
                    guard_results=guard_results,
                    disambiguation_options=disambiguation_options
                )
        except Exception as e:
            logger.error(f"Error in deterministic fetch during compose_rag_answer: {str(e)}")
    
    # Fall back to simple document-based answer
    if not retrieved_docs:
        return AnswerContract(
            text="I'm sorry, I couldn't find any relevant information for your query.",
            sources=[],
            intent="freeform",
            slots=slots or {},
            confidence=0.0
        )
    
    # Create evidence list for LLM
    evidence = []
    for doc in retrieved_docs:
        evidence.append({
            "text": doc.get("content", ""),
            "metadata": {
                "policy_id": doc.get("policy_id"),
                "url": doc.get("url", f"/documents/{doc.get('id')}"),
                "name": doc.get("source_name", "Document"),
                "page": doc.get("page_number"),
                "section": doc.get("section"),
                "updated_at": doc.get("updated_date")
            }
        })
    
    # Use LLM to compose answer
    try:
        answer_result = compose_answer(query, evidence)
        
        # Extract the answer text
        answer_text = answer_result.get("answer", answer_result.get("text", ""))
        
        # Create sources list
        sources = []
        
        # First add sources from LLM result
        if "sources" in answer_result:
            for source in answer_result["sources"]:
                sources.append(SourceInfo(
                    policy_id=source.get("policy_id"),
                    url=source.get("url", ""),
                    page=source.get("page"),
                    name=source.get("name", "Document"),
                    updated_at=source.get("updated_at")
                ))
        
        # Add missing sources from retrieved docs
        if len(sources) < 3 and retrieved_docs:
            for doc in retrieved_docs[:3-len(sources)]:
                sources.append(SourceInfo(
                    policy_id=doc.get("policy_id"),
                    url=doc.get("url", f"/documents/{doc.get('id')}"),
                    name=doc.get("source_name", "Document"),
                    page=doc.get("page_number"),
                    section=doc.get("section"),
                    updated_at=doc.get("updated_date")
                ))
    
    except Exception as e:
        logger.error(f"Error in LLM answer composition: {str(e)}")
        # Fallback to simpler answer
        answer_text = retrieved_docs[0].get("content", "")
        if len(answer_text) > 300:
            answer_text = answer_text[:300] + "..."
        
        # Create sources list from retrieved docs
        sources = []
        for doc in retrieved_docs[:3]:  # Include top 3 sources
            sources.append(SourceInfo(
                policy_id=doc.get("policy_id"),
                url=doc.get("url", f"/documents/{doc.get('id')}"),
                name=doc.get("source_name", "Document"),
                page=doc.get("page_number"),
                section=doc.get("section"),
                updated_at=doc.get("updated_date")
            ))
    
    # Compute confidence based on answer quality and source scores
    confidence = min(0.9, retrieved_docs[0].get("score", 0.5) * 1.2) if retrieved_docs else 0.0
    
    # Create answer contract dict for guards
    answer_dict = {
        "text": answer_text,
        "sources": [s.dict() for s in sources],
        "intent": "freeform",
        "slots": slots or {},
        "confidence": confidence,
        "updated_date": retrieved_docs[0].get("updated_date") if retrieved_docs else None
    }
    
    # Apply guards
    guards_to_apply = ["citation", "numeric", "temporal", "disambiguation"]
    evidence_texts = [doc.get("content", "") for doc in retrieved_docs]
    
    passed, reasons, details = await apply_guards(
        answer_contract=answer_dict,
        evidence_texts=evidence_texts,
        session=session,
        guards_to_apply=guards_to_apply,
        query=query
    )
    
    # Create guard results
    guard_results = GuardResults()
    
    if "citation" in details:
        guard_results.citation = GuardResult(
            passed=details["citation"]["passed"],
            message=details["citation"]["message"],
            details=details["citation"].get("details")
        )
    
    if "numeric" in details:
        guard_results.numeric = GuardResult(
            passed=details["numeric"]["passed"],
            message=details["numeric"]["message"],
            details=details["numeric"].get("details")
        )
    
    if "temporal" in details:
        guard_results.temporal = GuardResult(
            passed=details["temporal"]["passed"],
            message=details["temporal"]["message"],
            details=details["temporal"].get("details")
        )
    
    if "disambiguation" in details:
        guard_results.disambiguation = GuardResult(
            passed=details["disambiguation"]["passed"],
            message=details["disambiguation"]["message"],
            details=details["disambiguation"].get("details")
        )
    
    if "overall" in details:
        guard_results.overall = GuardResult(
            passed=details["overall"]["passed"],
            message="; ".join(reasons),
            details=details["overall"]
        )
    
    # Prepare disambiguation options if available
    disambiguation_options = None
    if "disambiguation" in details and details["disambiguation"].get("disambiguation_options"):
        disambiguation_options = details["disambiguation"]["disambiguation_options"]
    
    # Modify answer text if guards failed
    if not passed:
        if "numeric" in details and not details["numeric"].get("passed", True):
            answer_text = "⚠️ Warning: This answer may contain numeric inconsistencies.\n\n" + answer_text
        
        if "temporal" in details and not details["temporal"].get("passed", True):
            answer_text = "⚠️ Warning: This answer may use outdated information.\n\n" + answer_text
    
    return AnswerContract(
        text=answer_text,
        sources=sources,
        intent="freeform",
        slots=slots or {},
        confidence=confidence,
        updated_date=retrieved_docs[0].get("updated_date") if retrieved_docs else None,
        guard_results=guard_results,
        disambiguation_options=disambiguation_options
    )


@ask_router.post("/ask", response_model=AnswerContract)
async def ask(
    request: AskRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """
    Ask endpoint for handling both rule-based and RAG-based queries.
    
    Steps:
    1. Classify intent and extract slots
    2. If rule-based intent with sufficient slots, use rule-based answer
    3. Otherwise, use RAG pipeline: retrieve → rerank → compose
    
    Args:
        request: The ask request
        background_tasks: Background tasks for stats updating
        session: Database session
        
    Returns:
        Answer response
    """
    start_time = time.time()
    
    # Validate query
    validation_result = validate_query(request.text)
    if not validation_result["valid"]:
        raise HTTPException(status_code=400, detail=validation_result["message"])
    
    # 1. Classify intent and extract slots
    intent, slots, confidence = classify_intent_and_slots(request.text)
    
    # 2. Rule-based answer if applicable
    is_rule_based = False
    if intent in RULE_INTENTS and confidence >= 0.6:
        try:
            rule_answer = await answer_from_rules(intent, slots, session)
            if rule_answer:
                # Convert to standardized answer contract
                rule_answer_dict = rule_answer.to_dict()
                
                # Process with guards
                response = await process_rule_answer(
                    rule_answer_dict=rule_answer_dict,
                    query=request.text,
                    session=session
                )
                
                # Add processing time
                response.processing_time = round((time.time() - start_time) * 1000, 2)
                
                is_rule_based = True
                
                # Update stats in background
                background_tasks.add_task(
                    update_stats, 
                    intent, 
                    is_rule_based, 
                    (time.time() - start_time) * 1000
                )
                
                return response
        except Exception as e:
            logger.error(f"Error in rule-based answer: {str(e)}")
            # Fall back to RAG pipeline
    
    # 3. RAG pipeline
    try:
        # Retrieve documents
        retrieval_results = await retrieve_documents(
            query=request.text,
            limit=10
        )
        
        # Rerank if we have enough documents
        if len(retrieval_results) > 1:
            # First pass with simple reranker
            reranked_results = rerank_documents(
                query=request.text,
                documents=retrieval_results
            )
            
            # Second pass with cross-encoder
            if len(reranked_results) > 0:
                final_results = cross_encode_rerank(
                    query=request.text,
                    candidates=reranked_results,
                    top_n=5
                )
            else:
                final_results = reranked_results
        else:
            final_results = retrieval_results
        
        # Compose answer
        response = await compose_rag_answer(
            query=request.text,
            retrieved_docs=final_results,
            slots=slots,
            session=session
        )
        
        # Add processing time
        response.processing_time = round((time.time() - start_time) * 1000, 2)
        
        # Update stats in background
        background_tasks.add_task(
            update_stats, 
            intent, 
            is_rule_based, 
            (time.time() - start_time) * 1000
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in RAG pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


@ask_router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Health status information
    """
    import datetime
    import time
    import os
    from src.core.config import settings
    
    # Calculate uptime
    start_time = time.time() - 3600  # Placeholder - in a real app, track actual start time
    uptime = time.time() - start_time
    
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        uptime=round(uptime, 2),
        timestamp=datetime.datetime.now().isoformat()
    )


@ask_router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get system statistics.
    
    Returns:
        System statistics
    """
    return StatsResponse(
        total_requests=STATS["total_requests"],
        rule_based_responses=STATS["rule_based_responses"],
        rag_responses=STATS["rag_responses"],
        intent_distribution=STATS["intent_distribution"],
        avg_response_time=STATS["avg_response_time"]
    )
