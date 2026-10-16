# NitiClaim - Production Deployment Guide
> *Adjudication guided by policy truth*

## Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │    Modern Web Frontend (Vite/React)   │
                      │    Port: 5173                         │
                      └──────────────────┬────────────────────┘
                                         │ REST API
                                         ▼
┌───────────────────────┐     ┌───────────────────────────────────────┐
│ Streamlit App (Legacy)│────▶│    FastAPI Enterprise Backend Server  │
│ Port: 8501            │     │    Port: 8000 (OpenAPI /docs)         │
└───────────────────────┘     └──────────────────┬────────────────────┘
                                                 │
                  ┌──────────────────────────────┴──────────────────────────────┐
                  ▼                                                             ▼
     ┌────────────────────────┐                                    ┌────────────────────────┐
     │   SQLite / PostgreSQL   │                                    │   ChromaDB + BM25      │
     │   Structured Metadata  │                                    │   Hybrid Search Fusion │
     └────────────────────────┘                                    └────────────────────────┘
```

---

## 1. Quick Start Locally

### Step 1: Install Dependencies
```bash
# In the project root
pip install -r requirements.txt
pip install fastapi uvicorn pydantic-settings sqlmodel rank-bm25 pytest httpx python-multipart pymupdf
```

### Step 2: Set Environment Variables (Optional)
Create a `.env` file in the root directory:
```env
PERPLEXITY_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
DATABASE_URL=sqlite:///./insurance_claims.db
```

### Step 3: Run the Test Suite
```bash
python -m pytest tests/test_enterprise.py -v
```

### Step 4: Run the Backend API
```bash
python -m uvicorn api:app --reload --port 8000
```
- Interactive API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Step 5: Run the Modern React UI
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### Step 6: (Alternative) Run the Hardened Streamlit Portal
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501).

---

## 2. Key Production Upgrades Added

1. **Hybrid Retrieval**: Dense embeddings (ChromaDB) + Sparse Lexical matching (BM25) prevents hallucinations and matches exact numerical sub-limits or condition clauses.
2. **Confidence Metric & Review Flagging**: Computes confidence (0–100%) and automatically flags borderline claims for underwriter human review.
3. **Multi-LLM Provider Support**: Easily switch between Perplexity (`sonar-pro`), OpenAI (`gpt-4o`), or offline heuristic models.
4. **Relational Database & Audit Trail**: Full SQLModel ORM tracking every policy document, clause index, and historical claim adjudication for compliance.
5. **Decoupled Architecture**: High-throughput FastAPI REST API with modern React frontend alongside a backward-compatible Streamlit dashboard.
