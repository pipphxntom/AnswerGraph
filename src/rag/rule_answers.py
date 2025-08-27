"""
Rule-based answer generation for structured intents.
"""
from typing import Dict, Any, Optional, List
import logging
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from src.models.procedure import Procedure
from src.models.policy import Policy
from src.models.source import Source
from src.rag.deterministic_fetch import deterministic_fetch

logger = logging.getLogger(__name__)


class AnswerContract:
    """
    Contract for structured answers.
    """
    def __init__(
        self,
        text: str,
        sources: List[Dict[str, Any]],
        intent: str,
        slots: Dict[str, str],
        confidence: float
    ):
        self.text = text
        self.sources = sources
        self.intent = intent
        self.slots = slots
        self.confidence = confidence
        self.updated_date = datetime.datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "text": self.text,
            "sources": self.sources,
            "intent": self.intent,
            "slots": self.slots,
            "confidence": self.confidence,
            "updated_date": self.updated_date
        }


async def get_procedures_by_slots(
    session: AsyncSession, 
    slots: Dict[str, str]
) -> List[Procedure]:
    """
    Get procedures matching the given slots.
    
    Args:
        session: Database session
        slots: Slot values extracted from query
        
    Returns:
        List of matching procedures
    """
    # Build query conditions
    conditions = []
    
    if "program" in slots:
        # Search in name and applies_to
        program = slots["program"]
        conditions.append(Procedure.name.ilike(f"%{program}%"))
        # JSON containment operator would be ideal here but using LIKE for simplicity
        conditions.append(Procedure.applies_to.cast(str).ilike(f"%{program}%"))
    
    # If no specific conditions, return empty list to avoid returning everything
    if not conditions:
        return []
    
    # Execute query with loading related data
    stmt = (
        select(Procedure)
        .options(selectinload(Procedure.policy))
        .where(or_(*conditions))
    )
    
    result = await session.execute(stmt)
    procedures = result.scalars().all()
    
    return procedures


async def answer_from_rules(
    intent: str,
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """
    Generate an answer from rules based on intent and slots.
    
    Args:
        intent: The classified intent
        slots: The extracted slots
        session: Database session
        
    Returns:
        AnswerContract with answer or None if no answer could be generated
    """
    # Map intents to query types for deterministic fetch
    query_type_map = {
        "deadline_inquiry": "deadline_info",
        "fee_inquiry": "fee_info",
        "program_info": "program_info",
        "application_process": "procedure",
        "registration_process": "procedure",
        "contact_info": "procedure",
        "campus_services": "program_info"
    }
    
    # Prepare parameters for deterministic fetch
    fetch_params = {}
    if "program" in slots:
        fetch_params["program"] = slots["program"]
    if "semester" in slots:
        fetch_params["term"] = slots["semester"]
    if "campus" in slots:
        fetch_params["campus"] = slots["campus"]
    
    # Get query type for this intent
    query_type = query_type_map.get(intent)
    if not query_type:
        return None
    
    # Execute deterministic fetch
    try:
        result = await deterministic_fetch(session, query_type, fetch_params)
        
        if result and result.get("answer"):
            # Create sources list
            sources = []
            if result.get("source"):
                source = result["source"]
                if source.get("url"):
                    sources.append({
                        "policy_id": result.get("policy", {}).get("id"),
                        "url": source.get("url"),
                        "page": source.get("page"),
                        "section": source.get("title")
                    })
            
            # Create answer contract
            return AnswerContract(
                text=result["answer"],
                sources=sources,
                intent=intent,
                slots=slots,
                confidence=0.9 if sources else 0.7
            )
    except Exception as e:
        logger.error(f"Error in answer_from_rules: {str(e)}")
    
    # Try specific handlers if deterministic fetch didn't work
    if intent == "deadline_inquiry":
        return await answer_deadline_inquiry(slots, session)
    elif intent == "fee_inquiry":
        return await answer_fee_inquiry(slots, session)
    elif intent == "program_info":
        return await answer_program_info(slots, session)
    elif intent == "application_process":
        return await answer_application_process(slots, session)
    elif intent == "registration_process":
        return await answer_registration_process(slots, session)
    elif intent == "contact_info":
        return await answer_contact_info(slots, session)
    elif intent == "campus_services":
        return await answer_campus_services(slots, session)
    
    return None


async def answer_deadline_inquiry(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """
    Answer deadline inquiry based on slots.
    
    Args:
        slots: The extracted slots
        session: Database session
        
    Returns:
        AnswerContract with answer or None
    """
    if "program" not in slots:
        return None
    
    procedures = await get_procedures_by_slots(session, slots)
    
    if not procedures:
        return None
    
    # Extract deadline information
    deadline_texts = []
    sources = []
    
    for procedure in procedures:
        if procedure.deadlines:
            # Get deadline information
            deadline_text = procedure.deadline_summary
            
            # Create text entry
            program_text = slots.get("program", "the program")
            semester_text = f" for {slots['semester']}" if "semester" in slots else ""
            campus_text = f" at {slots['campus']}" if "campus" in slots else ""
            
            entry = f"For {program_text}{semester_text}{campus_text}, {deadline_text}."
            deadline_texts.append(entry)
            
            # Add source
            sources.append({
                "policy_id": procedure.policy_id,
                "procedure_id": procedure.id,
                "url": f"/policies/{procedure.policy_id}",
                "name": procedure.name,
                "page": None  # Could be populated if we had page information
            })
    
    if not deadline_texts:
        return None
    
    # Combine all deadline information
    answer_text = " ".join(deadline_texts)
    
    return AnswerContract(
        text=answer_text,
        sources=sources,
        intent="deadline_inquiry",
        slots=slots,
        confidence=0.9 if len(sources) > 0 else 0.7
    )


async def answer_fee_inquiry(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """
    Answer fee inquiry based on slots.
    
    Args:
        slots: The extracted slots
        session: Database session
        
    Returns:
        AnswerContract with answer or None
    """
    if "program" not in slots:
        return None
    
    procedures = await get_procedures_by_slots(session, slots)
    
    if not procedures:
        return None
    
    # Extract fee information
    fee_texts = []
    sources = []
    
    for procedure in procedures:
        if procedure.fees:
            # Format depends on your JSON structure
            fee_text = ""
            try:
                if isinstance(procedure.fees, dict):
                    parts = []
                    for fee_type, amount in procedure.fees.items():
                        if isinstance(amount, (int, float, str)):
                            parts.append(f"{fee_type}: {amount}")
                        elif isinstance(amount, dict) and "amount" in amount:
                            parts.append(f"{fee_type}: {amount['amount']}")
                    
                    fee_text = "; ".join(parts)
                else:
                    fee_text = str(procedure.fees)
            except Exception:
                fee_text = str(procedure.fees)
            
            # Create text entry
            program_text = slots.get("program", "the program")
            semester_text = f" for {slots['semester']}" if "semester" in slots else ""
            campus_text = f" at {slots['campus']}" if "campus" in slots else ""
            
            entry = f"For {program_text}{semester_text}{campus_text}, the fees are: {fee_text}."
            fee_texts.append(entry)
            
            # Add source
            sources.append({
                "policy_id": procedure.policy_id,
                "procedure_id": procedure.id,
                "url": f"/policies/{procedure.policy_id}",
                "name": procedure.name,
                "page": None
            })
    
    if not fee_texts:
        return None
    
    # Combine all fee information
    answer_text = " ".join(fee_texts)
    
    return AnswerContract(
        text=answer_text,
        sources=sources,
        intent="fee_inquiry",
        slots=slots,
        confidence=0.9 if len(sources) > 0 else 0.7
    )


async def answer_program_info(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """Placeholder for program info answers."""
    # This would be implemented similar to the above methods
    return None


async def answer_application_process(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """Placeholder for application process answers."""
    return None


async def answer_registration_process(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """Placeholder for registration process answers."""
    return None


async def answer_contact_info(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """Placeholder for contact info answers."""
    return None


async def answer_campus_services(
    slots: Dict[str, str],
    session: AsyncSession
) -> Optional[AnswerContract]:
    """Placeholder for campus services answers."""
    return None
