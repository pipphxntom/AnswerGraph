from pydantic import BaseModel, HttpUrl, Field
from typing import List, Dict, Any, Optional

class SourceRef(BaseModel):
    url: HttpUrl
    page: Optional[int] = None
    title: Optional[str] = None
    updated_at: Optional[str] = None  # ISO date
    policy_id: Optional[str] = None
    section: Optional[str] = None

class AnswerContract(BaseModel):
    mode: str              # "rules" | "rag"
    intent: str
    answer: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    sources: List[SourceRef]
    evidence_texts: List[str] = Field(default_factory=list)
    ctx: Dict[str, Any] = Field(default_factory=dict)

class GuardDecision(BaseModel):
    ok: bool
    reasons: List[str] = Field(default_factory=list)
    confidence: float = 0.0
