"""
Enterprise Data Models using SQLModel (compatible with SQLAlchemy 2.0 & Pydantic).
Supports SQLite (local dev) and PostgreSQL (production).
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
import json

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

class DocumentBase(SQLModel):
    filename: str = Field(index=True)
    file_hash: str = Field(unique=True, index=True)
    file_size: int
    total_clauses: int = 0
    policy_holder: Optional[str] = None
    policy_number: Optional[str] = None
    status: str = Field(default="processed", index=True)  # pending, processed, failed

class Document(DocumentBase, table=True):
    __tablename__ = "documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    
    clauses: List["PolicyClause"] = Relationship(back_populates="document", cascade_delete=True)
    claims: List["ClaimAudit"] = Relationship(back_populates="document", cascade_delete=True)

class PolicyClauseBase(SQLModel):
    clause_index: int
    title: str = Field(index=True)
    text: str
    page_number: int = Field(index=True)
    section_type: str = Field(default="general", index=True)  # inclusion, exclusion, waiting_period, limit, condition

class PolicyClause(PolicyClauseBase, table=True):
    __tablename__ = "clauses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    
    document: Optional[Document] = Relationship(back_populates="clauses")

class ClaimAuditBase(SQLModel):
    query: str
    decision: str  # Yes, No, Inconclusive
    confidence_score: float = Field(default=0.0)  # 0.0 to 1.0
    requires_human_review: bool = Field(default=False, index=True)
    review_reason: Optional[str] = None
    llm_provider: str = Field(default="perplexity")
    raw_response: Optional[str] = None  # JSON string

class ClaimAudit(ClaimAuditBase, table=True):
    __tablename__ = "claim_audits"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    created_at: datetime = Field(default_factory=get_utc_now)
    
    document: Optional[Document] = Relationship(back_populates="claims")

# Pydantic Schemas for API Requests/Responses
class ClaimAnalysisRequest(SQLModel):
    document_id: int
    query: str
    top_k: Optional[int] = 5
    llm_provider: Optional[str] = None

class ClauseMatch(SQLModel):
    id: int
    title: str
    text: str
    page_number: int
    section_type: str
    similarity_score: float

class ClaimAnalysisResponse(SQLModel):
    claim_id: Optional[int] = None
    document_id: int
    query: str
    decision: str  # Yes/No/Inconclusive
    confidence_score: float
    requires_human_review: bool
    review_reason: Optional[str] = None
    answers: List[str]
    matched_clauses: List[ClauseMatch]
    llm_provider: str
    created_at: datetime = Field(default_factory=get_utc_now)
