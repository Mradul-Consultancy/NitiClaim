"""
Enterprise Hybrid Retriever:
Combines Dense Semantic Vectors (ChromaDB) with BM25 Lexical Keyword Search.
Solves the problem of missing specific insurance clause codes, numbers, and disease names.
"""
import os
import re
from typing import List, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi

from core.config import settings

# ChromaDB import with defensive fallback
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None


def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer for BM25 search"""
    return re.findall(r'\b\w+\b', text.lower())


class HybridRetriever:
    """Production Hybrid Retriever marrying Dense Vector search and Sparse BM25"""

    def __init__(self, persist_directory: Optional[str] = None):
        self.persist_dir = persist_directory or settings.CHROMA_PERSIST_DIR
        self._init_chromadb()
        # In-memory BM25 indices keyed by document_id
        self._bm25_indices: Dict[int, Dict[str, Any]] = {}

    def _init_chromadb(self):
        if CHROMADB_AVAILABLE:
            os.makedirs(self.persist_dir, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        else:
            self.chroma_client = None

    def index_document_clauses(self, document_id: int, clauses: List[Dict[str, Any]]) -> None:
        """Indexes clauses into both ChromaDB and BM25 index"""
        if not clauses:
            return

        # 1. Build & cache BM25 Index
        corpus = [f"{c['title']} {c['text']}" for c in clauses]
        tokenized_corpus = [tokenize(doc) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        
        self._bm25_indices[document_id] = {
            "bm25": bm25,
            "clauses": clauses
        }

        # 2. Store in ChromaDB if available
        if self.chroma_client:
            collection_name = f"doc_{document_id}_clauses"
            try:
                # Delete if exists to recreate clean
                self.chroma_client.delete_collection(name=collection_name)
            except Exception:
                pass

            collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            ids = [f"{document_id}_{c.get('id', idx)}" for idx, c in enumerate(clauses)]
            documents = [f"{c['title']}\n{c['text']}" for c in clauses]
            metadatas = [{
                "clause_index": c.get("clause_index", idx),
                "title": c.get("title", "")[:100],
                "page_number": c.get("page_number", 1),
                "section_type": c.get("section_type", "general"),
                "db_clause_id": c.get("id", idx)
            } for idx, c in enumerate(clauses)]

            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

    def search(
        self,
        document_id: int,
        query: str,
        top_k: int = 5,
        alpha: Optional[float] = None,
        cached_clauses: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid search with reciprocal or weighted score fusion.
        Score = alpha * DenseScore + (1 - alpha) * BM25Score
        """
        alpha = alpha if alpha is not None else settings.HYBRID_SEARCH_ALPHA

        # Ensure BM25 is available
        if document_id not in self._bm25_indices:
            if cached_clauses:
                self.index_document_clauses(document_id, cached_clauses)
            else:
                return []

        bm25_data = self._bm25_indices[document_id]
        clauses = bm25_data["clauses"]
        bm25_model = bm25_data["bm25"]

        num_clauses = len(clauses)
        if num_clauses == 0:
            return []

        # 1. Compute BM25 scores
        query_tokens = tokenize(query)
        bm25_scores = np.array(bm25_model.get_scores(query_tokens))
        
        # Normalize BM25 scores to [0, 1]
        bm25_max = np.max(bm25_scores) if len(bm25_scores) > 0 and np.max(bm25_scores) > 0 else 1.0
        norm_bm25_scores = bm25_scores / bm25_max

        # 2. Compute Dense Vector scores
        dense_scores = np.zeros(num_clauses)
        if self.chroma_client:
            try:
                collection_name = f"doc_{document_id}_clauses"
                collection = self.chroma_client.get_collection(name=collection_name)
                res = collection.query(query_texts=[query], n_results=min(top_k * 3, num_clauses))
                
                if res and res["ids"] and len(res["ids"][0]) > 0:
                    for idx_str, distance in zip(res["ids"][0], res["distances"][0]):
                        # Convert cosine distance to similarity
                        sim = max(0.0, 1.0 - distance)
                        # Match to clause index in the cached array
                        for c_idx, c in enumerate(clauses):
                            if f"{document_id}_{c.get('id', c_idx)}" == idx_str:
                                dense_scores[c_idx] = sim
                                break
            except Exception:
                # If Chroma query fails, fall back to pure BM25
                alpha = 0.0

        # 3. Fuse Scores
        combined_scores = alpha * dense_scores + (1.0 - alpha) * norm_bm25_scores

        # Rank indices descending
        ranked_indices = np.argsort(combined_scores)[::-1][:top_k]

        results = []
        for idx in ranked_indices:
            clause = clauses[idx].copy()
            clause["similarity_score"] = float(round(combined_scores[idx], 4))
            results.append(clause)

        return results

# Singleton retriever instance
retriever = HybridRetriever()
