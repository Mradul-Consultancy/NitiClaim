"""
Hardened, Enterprise-Grade Streamlit Application for Beetals Claims Analysis.
Operates seamlessly with the Enterprise Hybrid RAG and Decision Engine.
"""
import streamlit as st
import asyncio
from sqlmodel import Session, select

from core.db import init_db, engine
from core.models import Document, PolicyClause, ClaimAudit
from services.pdf_processor import EnterprisePDFProcessor
from services.retriever import retriever
from services.llm_engine import LLMService

st.set_page_config(
    page_title="NitiClaim - Claims Adjudicator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise Dark CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1rem;
    }
    .badge-covered {
        background-color: #065f46;
        color: #34d399;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
    }
    .badge-excluded {
        background-color: #881337;
        color: #f43f5e;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
init_db()

def get_db_session():
    return Session(engine)

def main():
    st.markdown('<div class="main-header">NitiClaim Enterprise RAG</div>', unsafe_allow_html=True)
    st.caption("Adjudication guided by policy truth • AI-Powered Insurance Policy Clause Analysis")

    # Sidebar: Document Management
    with st.sidebar:
        st.subheader("📁 Policy Library")
        uploaded_file = st.file_uploader("Upload Insurance Policy (PDF)", type=["pdf"])

        if uploaded_file is not None:
            if st.button("Ingest & Index Policy", type="primary", use_container_width=True):
                with st.spinner("Parsing layout, extracting clauses, and indexing..."):
                    pdf_bytes = uploaded_file.read()
                    doc_meta, extracted_clauses = EnterprisePDFProcessor.process_pdf_bytes(
                        pdf_bytes, uploaded_file.name
                    )

                    with get_db_session() as session:
                        # Check duplicate
                        existing = session.exec(select(Document).where(Document.file_hash == doc_meta["file_hash"])).first()
                        if not existing:
                            doc_obj = Document(
                                filename=doc_meta["filename"],
                                file_hash=doc_meta["file_hash"],
                                file_size=doc_meta["file_size"],
                                total_clauses=doc_meta["total_clauses"],
                                status="processed"
                            )
                            session.add(doc_obj)
                            session.commit()
                            session.refresh(doc_obj)

                            for c in extracted_clauses:
                                clause_obj = PolicyClause(
                                    document_id=doc_obj.id,
                                    clause_index=c["clause_index"],
                                    title=c["title"],
                                    text=c["text"],
                                    page_number=c["page_number"],
                                    section_type=c["section_type"]
                                )
                                session.add(clause_obj)
                            session.commit()
                            target_doc_id = doc_obj.id
                        else:
                            target_doc_id = existing.id

                        # Index into Hybrid Retriever
                        all_clauses = session.exec(select(PolicyClause).where(PolicyClause.document_id == target_doc_id)).all()
                        retriever.index_document_clauses(target_doc_id, [c.model_dump() for c in all_clauses])
                        st.success(f"Successfully indexed {len(all_clauses)} clauses from {uploaded_file.name}!")

        # Load Documents
        with get_db_session() as session:
            documents = session.exec(select(Document).order_by(Document.created_at.desc())).all()

        if not documents:
            st.info("No policy documents found. Upload a policy above.")
            return

        doc_options = {doc.id: f"{doc.filename} ({doc.total_clauses} clauses)" for doc in documents}
        selected_doc_id = st.selectbox(
            "Select Active Policy:",
            options=list(doc_options.keys()),
            format_func=lambda x: doc_options[x]
        )

        selected_doc = next(d for d in documents if d.id == selected_doc_id)

    # Main Area Tabs
    tab_adjudicate, tab_clauses, tab_audits = st.tabs(["⚡ Adjudicate Claim", "📜 Policy Clauses", "📊 Compliance Audit Log"])

    with tab_adjudicate:
        st.subheader(f"Adjudicate against: {selected_doc.filename}")
        
        query = st.text_input(
            "Enter Claim Scenario / Query:",
            placeholder="e.g. Is Cataract surgery covered within the first 24 months of policy inception?"
        )

        col1, col2 = st.columns([1, 3])
        with col1:
            provider = st.selectbox("LLM Reasoner:", ["perplexity", "openai", "mock"], index=0)
        with col2:
            top_k = st.slider("Retrieved Clauses (K):", min_value=1, max_value=10, value=5)

        if st.button("Run Claim Assessment", type="primary", disabled=not query):
            with st.spinner("Executing Hybrid Retrieval (Dense Vector + BM25) and reasoning..."):
                with get_db_session() as session:
                    db_clauses = session.exec(
                        select(PolicyClause).where(PolicyClause.document_id == selected_doc_id)
                    ).all()
                    clauses_dicts = [c.model_dump() for c in db_clauses]

                matches = retriever.search(
                    document_id=selected_doc_id,
                    query=query,
                    top_k=top_k,
                    cached_clauses=clauses_dicts
                )

                # Async analysis call
                analysis = asyncio.run(LLMService.analyze_claim(
                    query=query,
                    clauses=matches,
                    provider=provider
                ))

                # Store audit record
                with get_db_session() as session:
                    audit = ClaimAudit(
                        document_id=selected_doc_id,
                        query=query,
                        decision=analysis["decision"],
                        confidence_score=analysis["confidence_score"],
                        requires_human_review=analysis["requires_human_review"],
                        review_reason=analysis.get("review_reason"),
                        llm_provider=provider,
                        raw_response=str(analysis)
                    )
                    session.add(audit)
                    session.commit()

                # Display Results
                st.divider()
                res_col1, res_col2 = st.columns([2, 1])
                
                with res_col1:
                    decision = analysis["decision"]
                    if decision == "Yes":
                        st.markdown('<span class="badge-covered">COVERAGE APPROVED (YES)</span>', unsafe_allow_html=True)
                    elif decision == "No":
                        st.markdown('<span class="badge-excluded">COVERAGE DENIED / EXCLUDED (NO)</span>', unsafe_allow_html=True)
                    else:
                        st.warning("INCONCLUSIVE: FURTHER EVIDENCE REQUIRED")

                    st.markdown("### Findings & Policy Terms")
                    for ans in analysis.get("answers", []):
                        st.write(f"- {ans}")

                with res_col2:
                    st.metric("Confidence Score", f"{analysis['confidence_score'] * 100:.0f}%")
                    if analysis.get("requires_human_review"):
                        st.error(f"⚠️ Flagged for Underwriter Review: {analysis.get('review_reason')}")

                # Display retrieved citations
                st.subheader("Retrieved Clause References (Hybrid Match)")
                for idx, m in enumerate(matches, 1):
                    with st.expander(f"Clause {idx}: {m['title']} (Page {m['page_number']}) - Match Score: {m.get('similarity_score', 0):.2f}"):
                        st.caption(f"Section Type: {m.get('section_type', 'general').upper()}")
                        st.write(m["text"])

    with tab_clauses:
        with get_db_session() as session:
            clauses = session.exec(
                select(PolicyClause).where(PolicyClause.document_id == selected_doc_id).order_by(PolicyClause.clause_index)
            ).all()

        st.info(f"Displaying {len(clauses)} parsed policy clauses.")
        for c in clauses:
            with st.expander(f"#{c.clause_index} - {c.title} (Page {c.page_number})"):
                st.caption(f"Tag: {c.section_type.upper()}")
                st.write(c.text)

    with tab_audits:
        with get_db_session() as session:
            audits = session.exec(
                select(ClaimAudit).where(ClaimAudit.document_id == selected_doc_id).order_by(ClaimAudit.created_at.desc())
            ).all()

        if not audits:
            st.info("No claim evaluations recorded yet.")
        else:
            for a in audits:
                st.write(f"**Query**: {a.query}")
                st.write(f"**Decision**: {a.decision} | **Confidence**: {a.confidence_score * 100:.0f}% | **Time**: {a.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                st.divider()

if __name__ == "__main__":
    main()
