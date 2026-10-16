import React, { useState, useEffect } from 'react';
import { 
  FileText, ShieldCheck, AlertTriangle, Upload, Search, 
  CheckCircle2, XCircle, HelpCircle, Activity, ChevronRight,
  Database, Cpu, Clock, RefreshCw
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [clauses, setClauses] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('adjudicate'); // adjudicate | clauses | audit
  const [audits, setAudits] = useState([]);

  useEffect(() => {
    fetchHealth();
    fetchDocuments();
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        setSystemHealth(data);
      }
    } catch (err) {
      console.warn("Backend API not reachable yet on port 8000");
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
        if (data.length > 0 && !selectedDoc) {
          selectDocument(data[0]);
        }
      }
    } catch (err) {
      console.error("Error fetching docs", err);
    }
  };

  const selectDocument = async (doc) => {
    setSelectedDoc(doc);
    setAnalysisResult(null);
    try {
      const res = await fetch(`${API_BASE}/documents/${doc.id}/clauses`);
      if (res.ok) {
        const data = await res.json();
        setClauses(data);
      }
      fetchAudits(doc.id);
    } catch (err) {
      console.error("Failed to load clauses", err);
    }
  };

  const fetchAudits = async (docId) => {
    try {
      const res = await fetch(`${API_BASE}/claims/audits?document_id=${docId}`);
      if (res.ok) {
        const data = await res.json();
        setAudits(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const result = await res.json();
        await fetchDocuments();
        alert(`Successfully uploaded & indexed: ${file.name}`);
      } else {
        const err = await res.json();
        alert(`Upload error: ${err.detail || 'Failed to parse PDF'}`);
      }
    } catch (err) {
      alert("Error contacting API server");
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyzeClaim = async (e) => {
    e.preventDefault();
    if (!selectedDoc || !query.trim()) return;

    setLoading(true);
    setAnalysisResult(null);

    try {
      const res = await fetch(`${API_BASE}/claims/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: selectedDoc.id,
          query: query.trim(),
          top_k: 5
        })
      });

      if (res.ok) {
        const data = await res.json();
        setAnalysisResult(data);
        fetchAudits(selectedDoc.id);
      } else {
        const err = await res.json();
        alert(`Analysis Error: ${err.detail || 'Failed to adjudicate claim'}`);
      }
    } catch (err) {
      alert("Error communicating with adjudication engine");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'radial-gradient(ellipse at top, #1e1b4b 0%, #0b0f19 70%)' }}>
      {/* Top Navigation */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 32px', borderBottom: '1px solid var(--border-color)', backdropFilter: 'blur(10px)', zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'var(--gradient-brand)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShieldCheck size={24} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: '700', letterSpacing: '-0.02em', background: 'var(--gradient-brand)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              NitiClaim
            </h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Adjudication guided by policy truth</p>
          </div>
        </div>

        {/* System Health Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', background: 'var(--bg-glass)', borderRadius: '20px', border: '1px solid var(--border-color)', fontSize: '0.8rem' }}>
            <Activity size={14} color={systemHealth ? '#10b981' : '#f59e0b'} />
            <span style={{ color: 'var(--text-muted)' }}>Engine:</span>
            <span style={{ color: '#fff', fontWeight: '600' }}>{systemHealth?.status === 'healthy' ? 'Active (FastAPI)' : 'Connecting...'}</span>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', background: 'var(--accent-primary)', color: '#fff', borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: '500' }}>
            <Upload size={16} />
            <span>{uploading ? 'Processing PDF...' : 'Ingest Policy PDF'}</span>
            <input type="file" accept=".pdf" onChange={handleFileUpload} style={{ display: 'none' }} disabled={uploading} />
          </label>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', flex: 1, padding: '24px', gap: '24px' }}>
        
        {/* Left Sidebar: Document Library */}
        <aside className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Policy Documents ({documents.length})
            </h2>
            <button onClick={fetchDocuments} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
              <RefreshCw size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', maxHeight: 'calc(100vh - 220px)' }}>
            {documents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 10px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                <FileText size={32} style={{ margin: '0 auto 10px', opacity: 0.3 }} />
                No policies uploaded yet.<br/>Upload an insurance policy PDF to start.
              </div>
            ) : (
              documents.map((doc) => {
                const isSelected = selectedDoc?.id === doc.id;
                return (
                  <div
                    key={doc.id}
                    onClick={() => selectDocument(doc)}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      border: isSelected ? '1px solid var(--accent-primary)' : '1px solid transparent',
                      background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <FileText size={18} color={isSelected ? '#818cf8' : '#9ca3af'} />
                      <div style={{ overflow: 'hidden' }}>
                        <div style={{ fontSize: '0.85rem', fontWeight: '600', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                          {doc.filename}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', gap: '8px', marginTop: '4px' }}>
                          <span>{doc.total_clauses} clauses</span>
                          <span>•</span>
                          <span>{(doc.file_size / 1024).toFixed(0)} KB</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* Right Main Stage */}
        <main style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Tab Selector */}
          <div style={{ display: 'flex', gap: '12px', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
            <button
              onClick={() => setActiveTab('adjudicate')}
              style={{
                background: activeTab === 'adjudicate' ? 'var(--accent-primary)' : 'transparent',
                color: activeTab === 'adjudicate' ? '#fff' : 'var(--text-muted)',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '0.85rem'
              }}
            >
              Adjudicate Claim
            </button>
            <button
              onClick={() => setActiveTab('clauses')}
              style={{
                background: activeTab === 'clauses' ? 'var(--accent-primary)' : 'transparent',
                color: activeTab === 'clauses' ? '#fff' : 'var(--text-muted)',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '0.85rem'
              }}
            >
              Policy Clauses ({clauses.length})
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              style={{
                background: activeTab === 'audit' ? 'var(--accent-primary)' : 'transparent',
                color: activeTab === 'audit' ? '#fff' : 'var(--text-muted)',
                border: 'none',
                padding: '8px 18px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '0.85rem'
              }}
            >
              Audit Trail ({audits.length})
            </button>
          </div>

          {/* Active Tab Content */}
          {activeTab === 'adjudicate' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* Query Input Card */}
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '1rem', marginBottom: '8px', fontWeight: '600' }}>
                  Analyze Claim Scenario
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                  Active Policy: <span style={{ color: '#fff', fontWeight: '600' }}>{selectedDoc ? selectedDoc.filename : 'None selected'}</span>
                </p>

                <form onSubmit={handleAnalyzeClaim} style={{ display: 'flex', gap: '12px' }}>
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="e.g. Is Cataract surgery covered within the first 24 months of policy inception?"
                    style={{
                      flex: 1,
                      padding: '14px 18px',
                      background: 'rgba(0, 0, 0, 0.4)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '0.9rem',
                      outline: 'none'
                    }}
                  />
                  <button
                    type="submit"
                    disabled={loading || !selectedDoc}
                    style={{
                      padding: '14px 24px',
                      background: 'var(--gradient-brand)',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      fontWeight: '600',
                      cursor: loading || !selectedDoc ? 'not-allowed' : 'pointer',
                      opacity: loading || !selectedDoc ? 0.6 : 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <Search size={18} />
                    <span>{loading ? 'Evaluating...' : 'Run Adjudication'}</span>
                  </button>
                </form>
              </div>

              {/* Decision Result Card */}
              {analysisResult && (
                <div className="glass-panel animate-fade-in" style={{ padding: '24px', borderLeft: analysisResult.decision === 'Yes' ? '4px solid var(--accent-emerald)' : analysisResult.decision === 'No' ? '4px solid var(--accent-rose)' : '4px solid var(--accent-amber)' }}>
                  
                  {/* Decision Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                      {analysisResult.decision === 'Yes' ? (
                        <CheckCircle2 size={36} color="var(--accent-emerald)" />
                      ) : analysisResult.decision === 'No' ? (
                        <XCircle size={36} color="var(--accent-rose)" />
                      ) : (
                        <HelpCircle size={36} color="var(--accent-amber)" />
                      )}
                      <div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Adjudication Decision
                        </div>
                        <div style={{ fontSize: '1.6rem', fontWeight: '800' }}>
                          {analysisResult.decision === 'Yes' ? 'Claim Covered' : analysisResult.decision === 'No' ? 'Claim Excluded / Not Covered' : 'Inconclusive Review Required'}
                        </div>
                      </div>
                    </div>

                    {/* Confidence Score Meter */}
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Confidence Metric</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: '700', color: analysisResult.confidence_score >= 0.7 ? '#10b981' : '#f59e0b' }}>
                        {(analysisResult.confidence_score * 100).toFixed(0)}%
                      </div>
                      {analysisResult.requires_human_review && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: '#f59e0b', marginTop: '4px' }}>
                          <AlertTriangle size={12} /> Flagged for Human Review
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Answers & Justifications */}
                  <div style={{ marginBottom: '24px' }}>
                    <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '10px' }}>Policy Findings & Excerpts</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {analysisResult.answers.map((ans, i) => (
                        <div key={i} style={{ padding: '12px 16px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px', fontSize: '0.85rem', lineHeight: '1.5' }}>
                          • {ans}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Matched Clauses Citation Accordion */}
                  <div>
                    <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
                      Retrieved Policy Clauses (Hybrid Dense + BM25 Fusion)
                    </h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {analysisResult.matched_clauses.map((clause, idx) => (
                        <div key={idx} style={{ padding: '14px', background: 'rgba(0,0,0,0.25)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                            <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>{clause.title}</span>
                            <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>Page {clause.page_number} • Match Score: {(clause.similarity_score * 100).toFixed(0)}%</span>
                          </div>
                          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}>
                            {clause.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              )}

            </div>
          )}

          {/* Clauses Tab */}
          {activeTab === 'clauses' && (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '16px' }}>Extracted Clauses Catalog</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: 'calc(100vh - 250px)', overflowY: 'auto' }}>
                {clauses.map((c) => (
                  <div key={c.id} style={{ padding: '16px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: '600', color: '#fff' }}>#{c.clause_index} - {c.title}</span>
                      <span style={{ fontSize: '0.75rem', padding: '3px 8px', borderRadius: '4px', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
                        {c.section_type.toUpperCase()} • Page {c.page_number}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap' }}>{c.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Audit Tab */}
          {activeTab === 'audit' && (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1rem', marginBottom: '16px' }}>Audit & Adjudication Logs</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {audits.map((a) => (
                  <div key={a.id} style={{ padding: '14px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontWeight: '600', fontSize: '0.9rem' }}>"{a.query}"</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                        {new Date(a.created_at).toLocaleString()} • Model: {a.llm_provider}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontWeight: '700', color: a.decision === 'Yes' ? '#10b981' : '#f43f5e' }}>
                        {a.decision}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Conf: {(a.confidence_score * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </main>

      </div>
    </div>
  );
}
