"""
Deterministic fetch module for structured data retrieval.

This module provides functions to fetch and join data from Procedure, Policy, and Source
models in a deterministic way, returning formatted results that can be used directly 
in API responses.
"""
from typing import Dict, Any, List, Optional, Union, Set
import logging
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload

from src.models.procedure import Procedure
from src.models.policy import Policy
from src.models.source import Source

logger = logging.getLogger(__name__)


async def fetch_procedure_with_related(
    session: AsyncSession,
    procedure_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch procedure data along with related policy and source information.
    
    Args:
        session: Database session
        procedure_id: Optional procedure ID to filter by
        policy_id: Optional policy ID to filter by
        filters: Additional filters to apply
        
    Returns:
        List of formatted procedure data with related information
    """
    # Build the query
    stmt = (
        select(Procedure)
        .options(
            joinedload(Procedure.policy),
            selectinload(Procedure.policy).selectinload(Policy.sources)
        )
    )
    
    # Apply filters
    conditions = []
    if procedure_id:
        conditions.append(Procedure.id == procedure_id)
    if policy_id:
        conditions.append(Procedure.policy_id == policy_id)
    
    # Apply additional filters if provided
    if filters:
        if "name" in filters:
            conditions.append(Procedure.name.ilike(f"%{filters['name']}%"))
        if "applies_to" in filters:
            # JSON containment operator would be ideal here but using LIKE for simplicity
            conditions.append(Procedure.applies_to.cast(str).ilike(f"%{filters['applies_to']}%"))
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    # Execute query
    result = await session.execute(stmt)
    procedures = result.scalars().all()
    
    # Format results
    formatted_results = []
    for procedure in procedures:
        # Get the primary source for the policy
        primary_source = None
        if procedure.policy and procedure.policy.sources:
            primary_source = procedure.policy.sources[0]
        
        # Format the result
        formatted_result = format_procedure_result(procedure, primary_source)
        formatted_results.append(formatted_result)
    
    return formatted_results


def format_procedure_result(
    procedure: Procedure, 
    primary_source: Optional[Source] = None
) -> Dict[str, Any]:
    """
    Format procedure data into a standardized structure.
    
    Args:
        procedure: Procedure model instance
        primary_source: Optional primary source for the policy
        
    Returns:
        Formatted procedure data
    """
    # Format deadlines
    deadline_fields = {}
    if procedure.deadlines:
        for key, value in procedure.deadlines.items():
            if isinstance(value, dict) and "date" in value:
                deadline_fields[key] = value["date"]
            elif isinstance(value, str):
                deadline_fields[key] = value
    
    # Format fees
    fee_fields = {}
    if procedure.fees:
        for key, value in procedure.fees.items():
            if isinstance(value, dict) and "amount" in value:
                fee_fields[key] = value["amount"]
            elif isinstance(value, (int, float, str)):
                fee_fields[key] = value
    
    # Format policy information
    policy_info = {}
    if procedure.policy:
        policy_info = {
            "id": procedure.policy.id,
            "name": procedure.policy.name,
            "effective_from": procedure.policy.effective_from.isoformat() if procedure.policy.effective_from else None,
            "effective_to": procedure.policy.effective_to.isoformat() if procedure.policy.effective_to else None
        }
    
    # Format source information
    source_info = {}
    if primary_source:
        source_info = {
            "url": primary_source.url,
            "page": primary_source.page,
            "title": primary_source.title or procedure.policy.name if procedure.policy else None,
            "updated_at": primary_source.updated_at.isoformat() if primary_source.updated_at else 
                         (procedure.policy.updated_at.isoformat() if procedure.policy and procedure.policy.updated_at else None)
        }
    
    # Create the final formatted result
    formatted_result = {
        "answer": procedure.name,
        "fields": {
            "id": procedure.id,
            "name": procedure.name,
            "policy_id": procedure.policy_id,
            "deadlines": deadline_fields,
            "fees": fee_fields,
            "contacts": procedure.contacts,
            "applies_to": procedure.applies_to
        },
        "source": source_info,
        "policy": policy_info
    }
    
    return formatted_result


async def fetch_by_program_and_term(
    session: AsyncSession,
    program: str,
    term: Optional[str] = None,
    campus: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch procedure data related to a specific program and term.
    
    Args:
        session: Database session
        program: Program name or identifier
        term: Optional term or semester
        campus: Optional campus location
        
    Returns:
        List of formatted procedure data
    """
    # Build search filters based on program, term, and campus
    filters = {}
    
    # If program is provided, search in applies_to and name
    if program:
        filters["applies_to"] = program
    
    # Execute the query with filters
    procedures = await fetch_procedure_with_related(
        session=session,
        filters=filters
    )
    
    # Post-filter results for term and campus if provided
    if term or campus:
        filtered_procedures = []
        for proc in procedures:
            include = True
            
            # Check if term is in deadlines or applies_to
            if term and include:
                term_found = False
                # Check in deadlines
                for deadline_key in proc["fields"].get("deadlines", {}):
                    if term.lower() in deadline_key.lower():
                        term_found = True
                        break
                
                # Check in applies_to
                if not term_found and "applies_to" in proc["fields"]:
                    applies_to = proc["fields"]["applies_to"]
                    if isinstance(applies_to, dict):
                        for key, value in applies_to.items():
                            if term.lower() in key.lower() or (isinstance(value, str) and term.lower() in value.lower()):
                                term_found = True
                                break
                    elif isinstance(applies_to, str) and term.lower() in applies_to.lower():
                        term_found = True
                
                include = term_found
            
            # Check if campus is in applies_to
            if campus and include:
                campus_found = False
                if "applies_to" in proc["fields"]:
                    applies_to = proc["fields"]["applies_to"]
                    if isinstance(applies_to, dict):
                        for key, value in applies_to.items():
                            if campus.lower() in key.lower() or (isinstance(value, str) and campus.lower() in value.lower()):
                                campus_found = True
                                break
                    elif isinstance(applies_to, str) and campus.lower() in applies_to.lower():
                        campus_found = True
                
                include = campus_found
            
            if include:
                filtered_procedures.append(proc)
        
        return filtered_procedures
    
    return procedures


async def deterministic_fetch(
    session: AsyncSession,
    query_type: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Perform a deterministic fetch based on query type and parameters.
    
    This function provides a unified interface for different types of structured queries,
    ensuring consistent and deterministic results.
    
    Args:
        session: Database session
        query_type: Type of query to perform (procedure, deadline, fee, etc.)
        params: Parameters for the query
        
    Returns:
        Structured result containing answer, fields, and source information
    """
    result = {
        "answer": "",
        "fields": {},
        "source": {
            "url": None,
            "page": None,
            "title": None,
            "updated_at": None
        }
    }
    
    try:
        if query_type == "procedure":
            # Fetch procedure by ID
            if "procedure_id" in params:
                procedures = await fetch_procedure_with_related(
                    session=session,
                    procedure_id=params["procedure_id"]
                )
                if procedures:
                    return procedures[0]
            
            # Fetch procedure by policy ID
            elif "policy_id" in params:
                procedures = await fetch_procedure_with_related(
                    session=session,
                    policy_id=params["policy_id"]
                )
                if procedures:
                    return procedures[0]
        
        elif query_type == "program_info":
            # Fetch information about a program
            if "program" in params:
                procedures = await fetch_by_program_and_term(
                    session=session,
                    program=params["program"],
                    term=params.get("term"),
                    campus=params.get("campus")
                )
                
                if procedures:
                    # Combine relevant information from all matching procedures
                    program = params["program"]
                    fields = {}
                    sources = []
                    
                    for proc in procedures:
                        # Collect fields
                        for field_key, field_value in proc["fields"].items():
                            if field_key not in fields:
                                fields[field_key] = field_value
                        
                        # Collect sources
                        if proc["source"] and proc["source"]["url"]:
                            sources.append(proc["source"])
                    
                    # Use the most recent source
                    primary_source = None
                    latest_date = None
                    for source in sources:
                        if source.get("updated_at"):
                            try:
                                source_date = datetime.datetime.fromisoformat(source["updated_at"])
                                if not latest_date or source_date > latest_date:
                                    latest_date = source_date
                                    primary_source = source
                            except (ValueError, TypeError):
                                pass
                    
                    if not primary_source and sources:
                        primary_source = sources[0]
                    
                    result = {
                        "answer": f"Information for {program}",
                        "fields": fields,
                        "source": primary_source or result["source"]
                    }
                    
                    return result
        
        elif query_type == "deadline_info":
            # Fetch deadline information
            if "program" in params:
                procedures = await fetch_by_program_and_term(
                    session=session,
                    program=params["program"],
                    term=params.get("term"),
                    campus=params.get("campus")
                )
                
                if procedures:
                    # Combine deadline information
                    program = params["program"]
                    term = params.get("term", "")
                    deadline_fields = {}
                    source = None
                    
                    # Find the most relevant procedure with deadline information
                    for proc in procedures:
                        if "deadlines" in proc["fields"] and proc["fields"]["deadlines"]:
                            deadline_fields = proc["fields"]["deadlines"]
                            source = proc["source"]
                            break
                    
                    if deadline_fields:
                        # Format answer text
                        term_text = f" for {term}" if term else ""
                        answer = f"Deadlines for {program}{term_text}:"
                        for key, value in deadline_fields.items():
                            answer += f"\n- {key}: {value}"
                        
                        result = {
                            "answer": answer.strip(),
                            "fields": {"deadlines": deadline_fields},
                            "source": source or result["source"]
                        }
                        
                        return result
        
        elif query_type == "fee_info":
            # Fetch fee information
            if "program" in params:
                procedures = await fetch_by_program_and_term(
                    session=session,
                    program=params["program"],
                    term=params.get("term"),
                    campus=params.get("campus")
                )
                
                if procedures:
                    # Combine fee information
                    program = params["program"]
                    term = params.get("term", "")
                    fee_fields = {}
                    source = None
                    
                    # Find the most relevant procedure with fee information
                    for proc in procedures:
                        if "fees" in proc["fields"] and proc["fields"]["fees"]:
                            fee_fields = proc["fields"]["fees"]
                            source = proc["source"]
                            break
                    
                    if fee_fields:
                        # Format answer text
                        term_text = f" for {term}" if term else ""
                        answer = f"Fees for {program}{term_text}:"
                        for key, value in fee_fields.items():
                            answer += f"\n- {key}: {value}"
                        
                        result = {
                            "answer": answer.strip(),
                            "fields": {"fees": fee_fields},
                            "source": source or result["source"]
                        }
                        
                        return result
        
    except Exception as e:
        logger.error(f"Error in deterministic_fetch: {str(e)}")
        # Return empty result on error
    
    return result
