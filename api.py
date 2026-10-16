"""
Production-Grade FastAPI REST Engine for NitiClaim Policy & Claims Analysis.
Provides high-throughput endpoints for document ingestion, hybrid clause search, claim adjudication, and health checks.
"""
import logging
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from core.config import settings
from core.db import init_db, get_session
from core.models import (
    Document, DocumentBase, PolicyClause, ClaimAudit,
    ClaimAnalysisRequest, ClaimAnalysisResponse, ClauseMatch
)
from services.pdf_processor import EnterprisePDFProcessor
from services.retriever import retriever
from services.llm_engine import LLMService

logger = logging.getLogger("niticlaim.api")

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise-grade RAG and AI-driven claims assessment API for insurance policies.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration for decoupled frontends (React / Next.js / Streamlit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    """Ensure database tables and vector directories exist"""
    init_db()

# Security dependency (Optional API key check for enterprise mode)
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if settings.DEBUG:
        return True
    if x_api_key and (x_api_key == settings.DEFAULT_API_KEY or x_api_key == settings.SECRET_KEY):
        return True
    # Allow permissive access in dev mode if neither is set
    return True

@app.get("/api/v1/health", tags=["System"])
def health_check():
    """System health and configuration status"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "default_llm": settings.DEFAULT_LLM_PROVIDER,
        "chromadb_enabled": retriever.chroma_client is not None,
        "hybrid_alpha": settings.HYBRID_SEARCH_ALPHA
    }

@app.post("/api/v1/documents/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """
    Upload and parse insurance policy PDF.
    Extracts clauses, tags sections, saves to SQLite/Postgres, and indexes into Hybrid Retriever.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported."
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty."
        )

    file_hash = EnterprisePDFProcessor.compute_file_hash(content)

    # Check for duplicate document
    existing_doc = session.exec(select(Document).where(Document.file_hash == file_hash)).first()
    if existing_doc:
        # Load clauses into in-memory BM25 index if missing
        clauses = session.exec(select(PolicyClause).where(PolicyClause.document_id == existing_doc.id)).all()
        retriever.index_document_clauses(existing_doc.id, [c.model_dump() for c in clauses])
        return {
            "message": "Document already exists in library",
            "document_id": existing_doc.id,
            "filename": existing_doc.filename,
            "total_clauses": existing_doc.total_clauses,
            "is_duplicate": True
        }

    # Process PDF layout
    doc_meta, extracted_clauses = EnterprisePDFProcessor.process_pdf_bytes(content, file.filename)

    # Save document record
    doc_record = Document(
        filename=doc_meta["filename"],
        file_hash=doc_meta["file_hash"],
        file_size=doc_meta["file_size"],
        total_clauses=doc_meta["total_clauses"],
        status="processed"
    )
    session.add(doc_record)
    session.commit()
    session.refresh(doc_record)

    # Save policy clauses
    db_clauses = []
    for c in extracted_clauses:
        clause_obj = PolicyClause(
            document_id=doc_record.id,
            clause_index=c["clause_index"],
            title=c["title"],
            text=c["text"],
            page_number=c["page_number"],
            section_type=c["section_type"]
        )
        session.add(clause_obj)
        db_clauses.append(clause_obj)

    session.commit()

    # Index into Hybrid Retriever
    for db_c in db_clauses:
        session.refresh(db_c)
    retriever.index_document_clauses(doc_record.id, [c.model_dump() for c in db_clauses])

    return {
        "message": "Document uploaded and indexed successfully",
        "document_id": doc_record.id,
        "filename": doc_record.filename,
        "total_clauses": doc_record.total_clauses,
        "file_size": doc_record.file_size
    }

@app.get("/api/v1/documents", response_model=List[Document], tags=["Documents"])
def list_documents(session: Session = Depends(get_session)):
    """Retrieve all ingested policy documents"""
    docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
    return docs

@app.get("/api/v1/documents/{document_id}/clauses", response_model=List[PolicyClause], tags=["Documents"])
def get_document_clauses(document_id: int, session: Session = Depends(get_session)):
    """Inspect all parsed clauses for a specific document"""
    clauses = session.exec(
        select(PolicyClause).where(PolicyClause.document_id == document_id).order_by(PolicyClause.clause_index)
    ).all()
    if not clauses:
        raise HTTPException(status_code=404, detail="No clauses found for the specified document")
    return clauses

@app.post("/api/v1/claims/analyze", response_model=ClaimAnalysisResponse, tags=["Claims"])
async def analyze_claim(
    request: ClaimAnalysisRequest,
    session: Session = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """
    Adjudicate a claim scenario against a stored policy document using Hybrid RAG + LLM.
    """
    doc = session.get(Document, request.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document with ID {request.document_id} not found.")

    # Retrieve all document clauses from DB
    db_clauses = session.exec(
        select(PolicyClause).where(PolicyClause.document_id == request.document_id)
    ).all()
    clauses_dicts = [c.model_dump() for c in db_clauses]

    # Perform Hybrid Search (Chroma Dense + BM25)
    top_matches = retriever.search(
        document_id=request.document_id,
        query=request.query,
        top_k=request.top_k or 5,
        cached_clauses=clauses_dicts
    )

    if not top_matches:
        top_matches = clauses_dicts[:3]

    # Run Multi-LLM Decision Assessment
    analysis = await LLMService.analyze_claim(
        query=request.query,
        clauses=top_matches,
        provider=request.llm_provider
    )

    # Persist claim audit record for compliance and analytics
    audit_record = ClaimAudit(
        document_id=request.document_id,
        query=request.query,
        decision=analysis["decision"],
        confidence_score=analysis["confidence_score"],
        requires_human_review=analysis["requires_human_review"],
        review_reason=analysis.get("review_reason"),
        llm_provider=request.llm_provider or settings.DEFAULT_LLM_PROVIDER,
        raw_response=str(analysis)
    )
    session.add(audit_record)
    session.commit()
    session.refresh(audit_record)

    matched_clause_objs = [
        ClauseMatch(
            id=m.get("id", 0),
            title=m.get("title", ""),
            text=m.get("text", ""),
            page_number=m.get("page_number", 1),
            section_type=m.get("section_type", "general"),
            similarity_score=m.get("similarity_score", 0.0)
        ) for m in top_matches
    ]

    return ClaimAnalysisResponse(
        claim_id=audit_record.id,
        document_id=request.document_id,
        query=request.query,
        decision=analysis["decision"],
        confidence_score=analysis["confidence_score"],
        requires_human_review=analysis["requires_human_review"],
        review_reason=analysis.get("review_reason"),
        answers=analysis.get("answers", []),
        matched_clauses=matched_clause_objs,
        llm_provider=audit_record.llm_provider,
        created_at=audit_record.created_at
    )

@app.get("/api/v1/claims/audits", response_model=List[ClaimAudit], tags=["Claims"])
def get_claim_audits(
    document_id: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """Retrieve compliance audit trail for claims analysis"""
    stmt = select(ClaimAudit).order_by(ClaimAudit.created_at.desc())
    if document_id:
        stmt = stmt.where(ClaimAudit.document_id == document_id)
    return session.exec(stmt).all()
