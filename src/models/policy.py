"""Policy model for the A2G RAG system."""
from datetime import date
from typing import Dict, Any, List, Optional

from sqlalchemy import String, Date, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base


class Policy(Base):
    """
    Policy model representing organizational policies.
    
    A policy is a high-level document that establishes rules, guidelines,
    or principles that govern organizational behavior.
    """
    
    __tablename__ = "policies"
    
    # Primary key using text ID (e.g., "POL-2023-001")
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    # Core fields
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    issuer: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Scope as JSON (departments, regions, roles, etc.)
    scope: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default=lambda: {}
    )
    
    # Full text content
    text_full: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Tracking fields
    last_updated: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, default=date.today
    )
    
    # Relationships
    procedures: Mapped[List["Procedure"]] = relationship(
        "Procedure", back_populates="policy", cascade="all, delete-orphan"
    )
    sources: Mapped[List["Source"]] = relationship(
        "Source", back_populates="policy", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="policy", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Policy(id='{self.id}', title='{self.title}')>"
    
    @property
    def scope_text(self) -> str:
        """Return a human-readable version of the scope JSON."""
        if not self.scope:
            return "All departments"
        
        try:
            # Customize based on your actual JSON structure
            parts = []
            if self.scope.get("departments"):
                parts.append(f"Departments: {', '.join(self.scope['departments'])}")
            if self.scope.get("regions"):
                parts.append(f"Regions: {', '.join(self.scope['regions'])}")
            
            return "; ".join(parts) or "All departments"
        except Exception:
            return str(self.scope)
    
    @property
    def is_active(self) -> bool:
        """Check if the policy is currently active."""
        today = date.today()
        if self.effective_from and self.effective_from > today:
            return False
        if self.expires_on and self.expires_on < today:
            return False
        return True
