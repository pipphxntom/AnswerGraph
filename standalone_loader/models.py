"""
Database models for standalone policy loader.
"""
from datetime import date
from typing import Dict, Any, List, Optional

from sqlalchemy import String, Date, JSON, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class Policy(Base):
    """Policy model representing organizational policies."""
    
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
    
    def __repr__(self) -> str:
        return f"<Policy(id='{self.id}', title='{self.title}')>"


class Procedure(Base):
    """Procedure model representing standard operating procedures."""
    
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
    
    def __repr__(self) -> str:
        return f"<Procedure(id='{self.id}', name='{self.name}')>"


class Source(Base):
    """Source model representing document sources."""
    
    __tablename__ = "sources"
    
    # Primary key using text ID (e.g., "SRC-2023-001")
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    # Foreign key to policy
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Source location
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clause: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Bounding box for PDF sources (x, y, width, height)
    bbox: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    
    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="sources")
    
    def __repr__(self) -> str:
        return f"<Source(id='{self.id}', url='{self.url}', page={self.page})>"
