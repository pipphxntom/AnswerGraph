"""
API routes for the ask endpoint and related functionality.
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
from src.nlp.lang import detect_lang, normalize_hinglish
from src.answers.rules_path import answer_from_rules, NoAnswer
from src.rag.retriever import retrieve_documents
from src.rag.reranker import rerank_documents, cross_encode_rerank
from src.rag.guards import apply_guards, validate_query
from src.rag.composer import compose_rag_answer
from src.schemas.answer import AnswerContract, GuardDecision

# Configure logging
logger = logging.getLogger(__name__)

# Create router
ask_router = APIRouter()


class AskRequest(BaseModel):
    """Model for ask requests."""
    text: str
    lang: Optional[str] = "en"
    ctx: Optional[Dict[str, Any]] = None


class SourceInfo(BaseModel):
    """Model for source information."""
    policy_id: Optional[str] = None
    procedure_id: Optional[str] = None
    url: Optional[str] = None
    name: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None


class AskResponse(BaseModel):
    """Model for ask responses."""
    mode: str  # "rules" | "rag" | "fallback" | "disambiguation"
    intent: Optional[str] = None
    text: Optional[str] = None
    answer: Optional[str] = None  # New field for standardized output
    sources: List[SourceInfo] = []
    confidence: Optional[float] = None
    processing_time: Optional[float] = None
    updated_date: Optional[str] = None
    reasons: Optional[List[str]] = None
    ticket_id: Optional[str] = None
    chips: Optional[Dict[str, List[Any]]] = None


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


async def get_newest_policy_date(sources: List[Dict[str, Any]], session: AsyncSession) -> Optional[str]:
    """
    Get the date of the newest policy mentioned in the sources.
    
    Args:
        sources: List of sources referenced in the answer
        session: Database session
        
    Returns:
        ISO format date string of the newest policy, or None if no dates found
    """
    if not sources or not session:
        return None
    
    try:
        from sqlalchemy import select, func
        from src.models.policy import Policy
        
        # Extract policy IDs from sources
        policy_ids = []
        for source in sources:
            if source.get("policy_id"):
                policy_ids.append(source["policy_id"])
        
        if not policy_ids:
            return None
        
        # Query for the newest effective_from date
        stmt = select(func.max(Policy.effective_from)).where(
            Policy.id.in_(policy_ids)
        )
        
        result = await session.execute(stmt)
        newest_date = result.scalar_one_or_none()
        
        if newest_date:
            return newest_date.isoformat()
        return None
        
    except Exception as e:
        logger.error(f"Error getting newest policy date: {str(e)}")
        return None


def slots_complete(slots: Dict[str, Any], required_slots: List[str] = None) -> bool:
    """
    Check if all required slots are present in the extracted slots.
    
    Args:
        slots: Extracted slots from query
        required_slots: List of slot names that must be present
        
    Returns:
        True if all required slots are present
    """
    if not required_slots:
        # Different intents have different required slots
        return True
        
    return all(slot in slots and slots[slot] for slot in required_slots)


async def create_ticket_if_enabled(
    contract: AnswerContract, 
    reasons: List[str],
    session: Optional[AsyncSession] = None
) -> Optional[str]:
    """
    Create a ticket for failed guard checks if the feature is enabled.
    
    Args:
        contract: The answer contract that failed validation
        reasons: List of reasons why validation failed
        session: Database session
        
    Returns:
        Ticket ID if created, None otherwise
    """
    # This is a placeholder - in a real system, you would implement
    # ticket creation in your preferred ticketing system.
    
    logger.warning(f"Answer failed guard checks: {reasons}")
    
    try:
        # Set a timeout for ticket creation to ensure non-blocking
        async with asyncio.timeout(2.0):  # 2 second timeout
            # Generate a simple ticket ID for demonstration
            import uuid
            import datetime
            
            ticket_prefix = "A2G"
            date_part = datetime.datetime.now().strftime("%Y%m%d")
            unique_part = str(uuid.uuid4())[:8]
            
            ticket_id = f"{ticket_prefix}-{date_part}-{unique_part}"
            
            # In a real implementation, you would store the ticket in a database
            # or call an external ticketing API here
            
            logger.info(f"Created ticket {ticket_id} for failed guard checks: {reasons}")
            return ticket_id
    except asyncio.TimeoutError:
        logger.error("Ticket creation timed out after 2 seconds")
        return "TIMEOUT-TICKET"
    except Exception as e:
        logger.error(f"Failed to create ticket: {str(e)}")
        return None


@ask_router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """
    Ask endpoint for handling both rule-based and RAG-based queries.
    
    Steps:
    1. Language detection and normalization
    2. Classify intent and extract slots
    3. If rule-based intent with sufficient slots, use rule-based answer
    4. Otherwise, use RAG pipeline: retrieve → rerank → compose
    5. Apply guards to validate the answer
    6. Return answer or fallback response
    
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
    
    # 1. Language detection and normalization
    lang = detect_lang(request.text)
    normalized_query = normalize_hinglish(request.text) if lang == "hi-en" else request.text
    
    # 2. Classify intent and extract slots
    intent, slots, intent_confidence = classify_intent_and_slots(normalized_query)
    
    # Check if disambiguation is needed
    slot_coverage = len(slots) / 3.0  # Example metric - adjust based on your needs
    if slot_coverage < 0.5 and intent in RULE_INTENTS:
        # Return disambiguation response
        chips = {}
        if "program" not in slots:
            chips["program"] = ["BTech", "BBA", "MBA", "MTech"]
        if "semester" not in slots:
            chips["semester"] = [1, 2, 3, 4, 5, 6, 7, 8]
            
        return AskResponse(
            mode="disambiguation",
            intent=intent,
            text="Could you please provide more details?",
            confidence=intent_confidence,
            processing_time=round((time.time() - start_time) * 1000, 2),
            chips=chips
        )
    
    # 3. Rule-based answer if applicable
    contract = None
    if intent in RULE_INTENTS and intent_confidence >= 0.6 and slots_complete(slots):
        try:
            contract = await answer_from_rules(intent, slots, session)
        except NoAnswer as e:
            logger.info(f"No rule-based answer available: {str(e)}")
            # Fall back to RAG pipeline
        except Exception as e:
            logger.error(f"Error in rule-based answer: {str(e)}")
            # Fall back to RAG pipeline
    
    # 4. RAG pipeline if no rule-based answer
    if not contract:
        try:
            # Retrieve documents
            retrieval_results = await retrieve_documents(
                query=normalized_query,
                limit=10
            )
            
            # Rerank if we have enough documents
            if len(retrieval_results) > 1:
                # First pass with simple reranker
                reranked_results = rerank_documents(
                    query=normalized_query,
                    documents=retrieval_results
                )
                
                # Second pass with cross-encoder
                if len(reranked_results) > 0:
                    final_results = cross_encode_rerank(
                        query=normalized_query,
                        candidates=reranked_results,
                        top_n=5
                    )
                else:
                    final_results = reranked_results
            else:
                final_results = retrieval_results
            
            # Compose answer
            contract = await compose_rag_answer(
                query=normalized_query,
                retrieved_docs=final_results,
                slots=slots,
                session=session
            )
        except Exception as e:
            logger.error(f"Error in RAG pipeline: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
    
    # 5. Apply guards to validate the answer
    sources = [s.model_dump() for s in contract.sources]
    newest_date = await get_newest_policy_date(sources, session)
    lang_ok = lang in ["en", "hi", "hi-en"]
    
    decision = apply_guards(
        contract=contract,
        newest_policy_date=newest_date,
        lang_ok=lang_ok
    )
    
    # 6. Return answer or fallback response
    processing_time = round((time.time() - start_time) * 1000, 2)
    
    # Update stats in background
    background_tasks.add_task(
        update_stats, 
        intent, 
        contract.mode == "rules", 
        processing_time
    )
    
    if decision.ok:
        # Return successful answer
        sources_list = []
        for source in contract.sources:
            sources_list.append(SourceInfo(
                policy_id=source.policy_id,
                url=str(source.url),
                name=source.title,
                page=source.page,
                section=source.section
            ))
            
        return AskResponse(
            mode=contract.mode,
            intent=contract.intent,
            text=contract.answer,  # For backward compatibility
            answer=contract.answer,
            sources=sources_list,
            confidence=decision.confidence,
            processing_time=processing_time,
            updated_date=newest_date
        )
    else:
        # Create ticket if enabled
        ticket_id = await create_ticket_if_enabled(
            contract=contract, 
            reasons=decision.reasons,
            session=session
        )
        
        # Return fallback response
        return AskResponse(
            mode="fallback",
            intent=contract.intent,
            text="I'm sorry, I couldn't find a reliable answer to your question.",
            reasons=decision.reasons,
            ticket_id=ticket_id,
            confidence=decision.confidence,
            processing_time=processing_time
        )


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
