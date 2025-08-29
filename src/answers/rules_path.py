"""
Rules-based answer module for deterministic queries.

This module handles intent-specific deterministic answers from the database
for common structured queries where exact, factual answers are available.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, join
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from pydantic import HttpUrl

from src.models.policy import Policy
from src.models.procedure import Procedure
from src.models.source import Source
from src.schemas.answer import AnswerContract, SourceRef

# Configure logging
logger = logging.getLogger(__name__)

class NoAnswer(Exception):
    """Exception raised when no answer can be provided for a rule-based query."""
    pass


async def fetch_clause_text(url: str, page: Optional[int], session: AsyncSession) -> List[str]:
    """
    Fetch the text of a policy clause by URL and page.
    
    Args:
        url: The URL of the source document
        page: The page number in the document
        session: Database session
        
    Returns:
        List of relevant text chunks from the source
    """
    try:
        # Build the query to find source and associated chunks
        stmt = select(Source).where(Source.url == str(url))
        
        if page is not None:
            stmt = stmt.where(Source.page_count >= page)
            
        result = await session.execute(stmt)
        source = result.scalars().first()
        
        if not source:
            logger.warning(f"No source found for URL: {url}")
            return ["No source document found for this reference."]
        
        # Get policy_id and then fetch chunks
        policy_id = source.policy_id
        
        if policy_id:
            from src.models.chunk import Chunk
            
            # First try exact page match
            chunk_stmt = select(Chunk).where(
                Chunk.policy_id == policy_id
            )
            
            if page is not None:
                chunk_stmt = chunk_stmt.where(Chunk.page_number == page)
                
            chunk_stmt = chunk_stmt.limit(2)  # Get 1-2 most relevant chunks
            
            chunk_result = await session.execute(chunk_stmt)
            chunks = chunk_result.scalars().all()
            
            if chunks:
                return [chunk.content for chunk in chunks]
            
            # If no chunks found for the exact page, try adjacent pages
            if page is not None:
                # Try page-1
                prev_page_stmt = select(Chunk).where(
                    Chunk.policy_id == policy_id,
                    Chunk.page_number == (page - 1 if page > 1 else 1)
                ).limit(1)
                
                prev_result = await session.execute(prev_page_stmt)
                prev_chunk = prev_result.scalars().first()
                
                # Try page+1
                next_page_stmt = select(Chunk).where(
                    Chunk.policy_id == policy_id,
                    Chunk.page_number == (page + 1)
                ).limit(1)
                
                next_result = await session.execute(next_page_stmt)
                next_chunk = next_result.scalars().first()
                
                evidence = []
                if prev_chunk:
                    evidence.append(f"[From previous page] {prev_chunk.content}")
                if next_chunk:
                    evidence.append(f"[From next page] {next_chunk.content}")
                
                if evidence:
                    return evidence
            
            # Last resort: get any chunk from this policy
            fallback_stmt = select(Chunk).where(
                Chunk.policy_id == policy_id
            ).limit(1)
            
            fallback_result = await session.execute(fallback_stmt)
            fallback_chunk = fallback_result.scalars().first()
            
            if fallback_chunk:
                return [f"[Related content] {fallback_chunk.content}"]
            
        # If we reach here, we couldn't find any chunks
        return ["No specific content found for this reference. Please refer to the source document."]
    except Exception as e:
        logger.error(f"Error fetching clause text: {str(e)}")
        return ["Error retrieving content. Please refer to the source document."]


async def answer_from_rules(
    intent: str, 
    slots: Dict[str, Any], 
    session: AsyncSession
) -> AnswerContract:
    """
    Retrieve deterministic answers from the database based on intent and slots.
    
    Args:
        intent: The classified intent of the query
        slots: Extracted slots/entities from the query
        session: Database session
        
    Returns:
        AnswerContract with answer, fields, and source information
        
    Raises:
        NoAnswer: If required fields are missing or no matching data found
    """
    # Map intents to handler functions
    intent_handlers = {
        "fee_deadline": handle_fee_deadline,
        "scholarship_form_deadline": handle_scholarship_deadline,
        "timetable_release": handle_timetable_release,
        "hostel_fee_due": handle_hostel_fee,
        "exam_form_deadline": handle_exam_deadline
    }
    
    # Check if we have a handler for this intent
    if intent not in intent_handlers:
        logger.warning(f"No rule handler found for intent: {intent}")
        raise NoAnswer(f"No rule handler available for intent: {intent}")
    
    # Call the appropriate handler and get the legacy answer contract
    legacy_contract = await intent_handlers[intent](slots, session)
    
    # Convert to the new AnswerContract format
    source = legacy_contract.source
    source_ref = SourceRef(
        url=source["url"],
        page=source.get("page"),
        title=source.get("title"),
        updated_at=source.get("updated_at"),
        policy_id=source.get("policy_id"),
        section=source.get("section")
    )
    
    # Fetch evidence texts for the source
    evidence_texts = await fetch_clause_text(
        url=source["url"],
        page=source.get("page"),
        session=session
    )
    
    # Apply PII redaction to answer
    from src.rag.guards import ensure_sensitive_data_protection
    redacted_answer = ensure_sensitive_data_protection(legacy_contract.answer)
    
    # Create the new contract
    return AnswerContract(
        mode="rules",
        intent=intent,
        answer=redacted_answer,
        fields=legacy_contract.fields,
        sources=[source_ref],
        evidence_texts=evidence_texts,
        ctx=slots
    )


async def handle_fee_deadline(
    slots: Dict[str, Any], 
    session: AsyncSession
) -> AnswerContract:
    """Handle fee deadline queries."""
    try:
        # Extract relevant slots
        program = slots.get("program")
        semester = slots.get("semester")
        year = slots.get("year", datetime.now().year)
        
        # Validate required slots
        if not program:
            raise NoAnswer("Program information is required")
        
        # Build the query
        query = (
            select(
                Policy.title,
                Policy.effective_from,
                Procedure.details,
                Procedure.deadline,
                Source.url,
                Source.title.label("source_title"),
                Source.page_count
            )
            .select_from(
                join(Policy, Procedure, Policy.id == Procedure.policy_id)
                .join(Source, Policy.id == Source.policy_id)
            )
            .where(
                Policy.category == "fees",
                Policy.status == "active"
            )
        )
        
        # Add program filter if provided
        if program:
            query = query.where(Procedure.details.contains(program))
            
        # Add semester filter if provided
        if semester:
            query = query.where(Procedure.details.contains(f"semester {semester}"))
            
        # Execute query
        result = await session.execute(query)
        row = result.fetchone()
        
        if not row:
            raise NoAnswer(f"No fee deadline information found for {program}")
        
        # Format the answer
        deadline = row.deadline.strftime("%B %d, %Y") if row.deadline else "not specified"
        
        answer = f"The fee deadline for {program}"
        if semester:
            answer += f" semester {semester}"
        answer += f" is {deadline}."
        
        # Extract the page number from details if available
        page = 1  # Default page
        if row.details and "page" in row.details:
            import re
            page_match = re.search(r"page\s+(\d+)", row.details, re.IGNORECASE)
            if page_match:
                page = int(page_match.group(1))
        
        # Construct the response
        return AnswerContract(
            answer=answer,
            fields={
                "deadline": deadline,
                "program": program,
                "semester": semester,
                "year": year
            },
            source={
                "url": row.url,
                "page": page,
                "title": row.source_title or row.title,
                "updated_at": row.effective_from.strftime("%Y-%m-%d") if row.effective_from else None,
                "policy_id": row.policy_id if hasattr(row, "policy_id") else None
            }
        )
    
    except NoAnswer:
        raise
    except Exception as e:
        logger.error(f"Error handling fee deadline query: {str(e)}")
        raise NoAnswer(f"Error retrieving fee deadline information: {str(e)}")


async def handle_scholarship_deadline(
    slots: Dict[str, Any], 
    session: AsyncSession
) -> AnswerContract:
    """Handle scholarship form deadline queries."""
    try:
        # Extract relevant slots
        scholarship_type = slots.get("scholarship_type")
        year = slots.get("year", datetime.now().year)
        
        # Build the query
        query = (
            select(
                Policy.title,
                Policy.effective_from,
                Policy.id.label("policy_id"),
                Procedure.details,
                Procedure.deadline,
                Source.url,
                Source.title.label("source_title"),
                Source.page_count
            )
            .select_from(
                join(Policy, Procedure, Policy.id == Procedure.policy_id)
                .join(Source, Policy.id == Source.policy_id)
            )
            .where(
                Policy.category == "scholarship",
                Policy.status == "active"
            )
        )
        
        # Add scholarship type filter if provided
        if scholarship_type:
            query = query.where(Procedure.details.contains(scholarship_type))
            
        # Execute query
        result = await session.execute(query)
        row = result.fetchone()
        
        if not row:
            scholarship_desc = f"'{scholarship_type}' " if scholarship_type else ""
            raise NoAnswer(f"No scholarship {scholarship_desc}form deadline information found")
        
        # Format the answer
        deadline = row.deadline.strftime("%B %d, %Y") if row.deadline else "not specified"
        
        answer = "The "
        if scholarship_type:
            answer += f"{scholarship_type} "
        answer += f"scholarship form deadline is {deadline}."
        
        # Extract the page number from details if available
        page = 1  # Default page
        if row.details and "page" in row.details:
            import re
            page_match = re.search(r"page\s+(\d+)", row.details, re.IGNORECASE)
            if page_match:
                page = int(page_match.group(1))
        
        # Construct the response
        return AnswerContract(
            answer=answer,
            fields={
                "deadline": deadline,
                "scholarship_type": scholarship_type,
                "year": year
            },
            source={
                "url": row.url,
                "page": page,
                "title": row.source_title or row.title,
                "updated_at": row.effective_from.strftime("%Y-%m-%d") if row.effective_from else None,
                "policy_id": row.policy_id
            }
        )
    
    except NoAnswer:
        raise
    except Exception as e:
        logger.error(f"Error handling scholarship deadline query: {str(e)}")
        raise NoAnswer(f"Error retrieving scholarship deadline information: {str(e)}")


async def handle_timetable_release(
    slots: Dict[str, Any], 
    session: AsyncSession
) -> AnswerContract:
    """Handle timetable release queries."""
    try:
        # Extract relevant slots
        program = slots.get("program")
        semester = slots.get("semester")
        year = slots.get("year", datetime.now().year)
        
        # Build the query
        query = (
            select(
                Policy.title,
                Policy.effective_from,
                Procedure.details,
                Procedure.deadline.label("release_date"),
                Source.url,
                Source.title.label("source_title"),
                Source.page_count
            )
            .select_from(
                join(Policy, Procedure, Policy.id == Procedure.policy_id)
                .join(Source, Policy.id == Source.policy_id)
            )
            .where(
                Policy.category == "academic",
                Procedure.type == "timetable",
                Policy.status == "active"
            )
        )
        
        # Add program filter if provided
        if program:
            query = query.where(Procedure.details.contains(program))
            
        # Add semester filter if provided
        if semester:
            query = query.where(Procedure.details.contains(f"semester {semester}"))
            
        # Execute query
        result = await session.execute(query)
        row = result.fetchone()
        
        if not row:
            raise NoAnswer(f"No timetable release information found")
        
        # Format the answer
        release_date = row.release_date.strftime("%B %d, %Y") if row.release_date else "not specified"
        
        answer = "The timetable"
        if program:
            answer += f" for {program}"
        if semester:
            answer += f" semester {semester}"
        answer += f" will be released on {release_date}."
        
        # Extract the page number from details if available
        page = 1  # Default page
        if row.details and "page" in row.details:
            import re
            page_match = re.search(r"page\s+(\d+)", row.details, re.IGNORECASE)
            if page_match:
                page = int(page_match.group(1))
        
        # Construct the response
        return AnswerContract(
            answer=answer,
            fields={
                "release_date": release_date,
                "program": program,
                "semester": semester,
                "year": year
            },
            source={
                "url": row.url,
                "page": page,
                "title": row.source_title or row.title,
                "updated_at": row.effective_from.strftime("%Y-%m-%d") if row.effective_from else None
            }
        )
    
    except NoAnswer:
        raise
    except Exception as e:
        logger.error(f"Error handling timetable release query: {str(e)}")
        raise NoAnswer(f"Error retrieving timetable release information: {str(e)}")


async def handle_hostel_fee(
    slots: Dict[str, Any], 
    session: AsyncSession
) -> AnswerContract:
    """Handle hostel fee due queries."""
    try:
        # Extract relevant slots
        hostel_name = slots.get("hostel_name")
        year = slots.get("year", datetime.now().year)
        
        # Build the query
        query = (
            select(
                Policy.title,
                Policy.effective_from,
                Procedure.details,
                Procedure.deadline,
                Source.url,
                Source.title.label("source_title"),
                Source.page_count
            )
            .select_from(
                join(Policy, Procedure, Policy.id == Procedure.policy_id)
                .join(Source, Policy.id == Source.policy_id)
            )
            .where(
                Policy.category == "hostel",
                Procedure.type == "fee",
                Policy.status == "active"
            )
        )
        
        # Add hostel name filter if provided
        if hostel_name:
            query = query.where(Procedure.details.contains(hostel_name))
            
        # Execute query
        result = await session.execute(query)
        row = result.fetchone()
        
        if not row:
            hostel_desc = f"for {hostel_name} " if hostel_name else ""
            raise NoAnswer(f"No hostel fee information {hostel_desc}found")
        
        # Format the answer
        deadline = row.deadline.strftime("%B %d, %Y") if row.deadline else "not specified"
        
        answer = "The hostel fee"
        if hostel_name:
            answer += f" for {hostel_name}"
        answer += f" is due on {deadline}."
        
        # Extract the page number from details if available
        page = 1  # Default page
        if row.details and "page" in row.details:
            import re
            page_match = re.search(r"page\s+(\d+)", row.details, re.IGNORECASE)
            if page_match:
                page = int(page_match.group(1))
        
        # Construct the response
        return AnswerContract(
            answer=answer,
            fields={
                "deadline": deadline,
                "hostel_name": hostel_name,
                "year": year
            },
            source={
                "url": row.url,
                "page": page,
                "title": row.source_title or row.title,
                "updated_at": row.effective_from.strftime("%Y-%m-%d") if row.effective_from else None
            }
        )
    
    except NoAnswer:
        raise
    except Exception as e:
        logger.error(f"Error handling hostel fee query: {str(e)}")
        raise NoAnswer(f"Error retrieving hostel fee information: {str(e)}")


async def handle_exam_deadline(
    slots: Dict[str, Any], 
    session: AsyncSession
) -> AnswerContract:
    """Handle exam form deadline queries."""
    try:
        # Extract relevant slots
        exam_type = slots.get("exam_type")
        program = slots.get("program")
        semester = slots.get("semester")
        year = slots.get("year", datetime.now().year)
        
        # Build the query
        query = (
            select(
                Policy.title,
                Policy.effective_from,
                Procedure.details,
                Procedure.deadline,
                Source.url,
                Source.title.label("source_title"),
                Source.page_count
            )
            .select_from(
                join(Policy, Procedure, Policy.id == Procedure.policy_id)
                .join(Source, Policy.id == Source.policy_id)
            )
            .where(
                Policy.category == "examination",
                Policy.status == "active"
            )
        )
        
        # Add exam type filter if provided
        if exam_type:
            query = query.where(Procedure.type == exam_type)
            
        # Add program filter if provided
        if program:
            query = query.where(Procedure.details.contains(program))
            
        # Add semester filter if provided
        if semester:
            query = query.where(Procedure.details.contains(f"semester {semester}"))
            
        # Execute query
        result = await session.execute(query)
        row = result.fetchone()
        
        if not row:
            raise NoAnswer(f"No exam form deadline information found")
        
        # Format the answer
        deadline = row.deadline.strftime("%B %d, %Y") if row.deadline else "not specified"
        
        answer = "The "
        if exam_type:
            answer += f"{exam_type} "
        answer += "exam form deadline"
        if program:
            answer += f" for {program}"
        if semester:
            answer += f" semester {semester}"
        answer += f" is {deadline}."
        
        # Extract the page number from details if available
        page = 1  # Default page
        if row.details and "page" in row.details:
            import re
            page_match = re.search(r"page\s+(\d+)", row.details, re.IGNORECASE)
            if page_match:
                page = int(page_match.group(1))
        
        # Construct the response
        return AnswerContract(
            answer=answer,
            fields={
                "deadline": deadline,
                "exam_type": exam_type,
                "program": program,
                "semester": semester,
                "year": year
            },
            source={
                "url": row.url,
                "page": page,
                "title": row.source_title or row.title,
                "updated_at": row.effective_from.strftime("%Y-%m-%d") if row.effective_from else None
            }
        )
    
    except NoAnswer:
        raise
    except Exception as e:
        logger.error(f"Error handling exam deadline query: {str(e)}")
        raise NoAnswer(f"Error retrieving exam deadline information: {str(e)}")
