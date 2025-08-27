"""Chunk model for the A2G RAG system."""
from typing import Dict, Any, Optional

from sqlalchemy import String, Integer, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base


class Chunk(Base):
    """
    Chunk model representing document text chunks for RAG.
    
    Chunks are segments of text from policies or procedures that are
    embedded and indexed in a vector database for retrieval.
    """
    
    __tablename__ = "chunks"
    
    # Primary key using text ID (e.g., "CHK-2023-001")
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    
    # Foreign key to policy
    policy_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    
    # Content metadata
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    
    # Source location
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Bounding box for PDF sources (x, y, width, height)
    bbox: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    
    # The actual text content
    text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Relationships
    policy: Mapped[Optional["Policy"]] = relationship("Policy", back_populates="chunks")
    procedure: Mapped[Optional["Procedure"]] = relationship("Procedure", back_populates="chunks")
    
    def __repr__(self) -> str:
        return f"<Chunk(id='{self.id}', policy_id='{self.policy_id}')>"
    
    @property
    def text_preview(self) -> str:
        """Return a preview of the text content."""
        if not self.text:
            return ""
        
        # Return first 100 characters
        preview = self.text[:100]
        if len(self.text) > 100:
            preview += "..."
        
        return preview
    
    @property
    def location_text(self) -> str:
        """Return a human-readable location description."""
        parts = []
        
        # Add URL
        if self.url:
            parts.append(f"URL: {self.url}")
        
        # Add page if available
        if self.page:
            parts.append(f"Page: {self.page}")
        
        # Add section if available
        if self.section:
            parts.append(f"Section: {self.section}")
        
        return ", ".join(parts) if parts else "Unknown location"
