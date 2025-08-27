"""Procedure model for the A2G RAG system."""
from typing import Dict, Any, List, Optional

from sqlalchemy import String, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base


class Procedure(Base):
    """
    Procedure model representing standard operating procedures.
    
    A procedure is a detailed set of instructions or steps that implement
    or fulfill the requirements of a policy.
    """
    
    __tablename__ = "procedures"
    
    # Primary key using text ID (e.g., "PROC-2023-001")
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    # Foreign key to policy
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # JSON fields for structured data
    applies_to: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=lambda: {}
    )
    deadlines: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=lambda: {}
    )
    fees: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=lambda: {}
    )
    contacts: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=lambda: {}
    )
    
    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="procedures")
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="procedure", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Procedure(id='{self.id}', name='{self.name}')>"
    
    @property
    def deadline_summary(self) -> str:
        """Return a summary of deadlines as human-readable text."""
        if not self.deadlines:
            return "No specific deadlines"
        
        try:
            # Format depends on your JSON structure
            parts = []
            for key, value in self.deadlines.items():
                if isinstance(value, str):
                    parts.append(f"{key}: {value}")
                elif isinstance(value, dict) and "date" in value:
                    parts.append(f"{key}: {value['date']}")
            
            return "; ".join(parts) or "No specific deadlines"
        except Exception:
            return str(self.deadlines)
    
    @property
    def contact_summary(self) -> str:
        """Return a summary of contacts as human-readable text."""
        if not self.contacts:
            return "No specific contacts"
        
        try:
            # Format depends on your JSON structure
            parts = []
            for role, contact in self.contacts.items():
                if isinstance(contact, str):
                    parts.append(f"{role}: {contact}")
                elif isinstance(contact, dict) and "name" in contact:
                    parts.append(f"{role}: {contact['name']}")
            
            return "; ".join(parts) or "No specific contacts"
        except Exception:
            return str(self.contacts)
