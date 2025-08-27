"""Source model for the A2G RAG system."""
from typing import Dict, Any, Optional

from sqlalchemy import String, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base


class Source(Base):
    """
    Source model representing document sources.
    
    A source tracks the origin of policy or procedure content,
    such as a specific document, page, or clause.
    """
    
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
    
    @property
    def location_text(self) -> str:
        """Return a human-readable location description."""
        parts = []
        
        # Add URL
        parts.append(f"URL: {self.url}")
        
        # Add page if available
        if self.page:
            parts.append(f"Page: {self.page}")
        
        # Add clause if available
        if self.clause:
            parts.append(f"Clause: {self.clause}")
        
        return ", ".join(parts)
