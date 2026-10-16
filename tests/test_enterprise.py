"""
Enterprise Test Suite for NitiClaim Policy & Claims Adjudication Platform
Covers:
- PDF Ingestion & Semantic Section Classification
- Hybrid Retriever (BM25 + Dense Score Fusion)
- LLM Output JSON parser & Confidence Evaluation
- FastAPI REST endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from core.db import get_session
from core.models import Document, PolicyClause
from services.pdf_processor import EnterprisePDFProcessor
from services.retriever import HybridRetriever, tokenize
from services.llm_engine import LLMService
from api import app

# Create in-memory SQLite engine for tests
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

# --- Unit Tests ---

def test_semantic_section_detection():
    """Verify regex classifier detects policy clauses accurately"""
    title = "Exclusions and Non-Payable Treatments"
    text = "The company shall not be liable for cosmetic surgery or routine dental examination."
    section_type = EnterprisePDFProcessor.detect_section_type(text, title)
    assert section_type == "exclusion"

    waiting_text = "A waiting period of 24 consecutive months applies to Cataract and Hernia treatments."
    waiting_type = EnterprisePDFProcessor.detect_section_type(waiting_text, "Specific Illness Waiting Period")
    assert waiting_type == "waiting_period"

def test_hybrid_retriever_bm25_ranking():
    """Verify BM25 keyword matching correctly ranks specific conditions"""
    retriever = HybridRetriever(persist_directory="./test_chroma")
    sample_clauses = [
        {
            "id": 1,
            "clause_index": 1,
            "title": "General Hospitalization Cover",
            "text": "Expenses for room rent, nursing, and ICU are covered up to sum insured.",
            "page_number": 2,
            "section_type": "inclusion"
        },
        {
            "id": 2,
            "clause_index": 2,
            "title": "Cataract & Eye Treatment Sub-limits",
            "text": "Cataract surgery expenses are subject to a maximum sub-limit of Rs. 40,000 per eye.",
            "page_number": 5,
            "section_type": "limit"
        }
    ]

    retriever.index_document_clauses(document_id=99, clauses=sample_clauses)
    
    # Query for cataract specifically
    results = retriever.search(document_id=99, query="What is the limit on Cataract surgery?", top_k=1, alpha=0.0)
    assert len(results) == 1
    assert results[0]["id"] == 2
    assert "Cataract" in results[0]["title"]

def test_llm_json_cleaner():
    """Verify markdown-wrapped JSON responses parse safely into structured dicts"""
    raw_markdown = """```json
    {
        "decision": "No",
        "confidence_score": 0.95,
        "requires_human_review": false,
        "review_reason": null,
        "answers": ["Clause 4.1 excludes dental surgery unless caused by accidental bodily injury."]
    }
    ```"""
    result = LLMService._parse_llm_json(raw_markdown)
    assert result["decision"] == "No"
    assert result["confidence_score"] == 0.95
    assert result["requires_human_review"] is False
    assert len(result["answers"]) == 1

# --- API Integration Tests ---

def test_health_check_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "hybrid_alpha" in data

def test_document_and_claim_flow(client: TestClient, session: Session):
    # Setup mock document in test DB
    doc = Document(
        filename="TestPolicy.pdf",
        file_hash="mockhash123",
        file_size=1024,
        total_clauses=1,
        status="processed"
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    clause = PolicyClause(
        document_id=doc.id,
        clause_index=1,
        title="Accidental Emergency Care",
        text="All emergency outpatient accidental injuries are covered without waiting period.",
        page_number=1,
        section_type="inclusion"
    )
    session.add(clause)
    session.commit()

    # List documents
    docs_resp = client.get("/api/v1/documents")
    assert docs_resp.status_code == 200
    assert len(docs_resp.json()) == 1

    # Adjudicate claim
    claim_resp = client.post("/api/v1/claims/analyze", json={
        "document_id": doc.id,
        "query": "Is accidental emergency treatment covered immediately?",
        "top_k": 1,
        "llm_provider": "mock"
    })
    assert claim_resp.status_code == 200
    claim_data = claim_resp.json()
    assert claim_data["decision"] in ["Yes", "No"]
    assert claim_data["confidence_score"] > 0
    assert len(claim_data["matched_clauses"]) >= 1
