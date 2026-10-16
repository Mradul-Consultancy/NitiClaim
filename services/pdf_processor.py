"""
Enterprise RAG: PDF Ingestion & Hierarchical Clause Parsing.
Extracts structured clauses with section typing (inclusions, exclusions, waiting periods, limits).
"""
import re
import hashlib
from typing import List, Dict, Any, Tuple
import fitz  # PyMuPDF

class EnterprisePDFProcessor:
    """Production-grade layout-aware PDF parser for insurance policies"""

    SECTION_PATTERNS = {
        "exclusion": [
            r"exclusions?", r"what is not covered", r"not payable", r"permanent exclusions",
            r"general exclusions", r"non-payable items", r"specific exclusions"
        ],
        "waiting_period": [
            r"waiting periods?", r"initial waiting period", r"time bound exclusions?",
            r"pre-existing diseases?", r"ped waiting period", r"specific illness waiting period"
        ],
        "limit": [
            r"sub-limits?", r"coverage limits?", r"room rent limits?", r"deductible",
            r"co-payment", r"sum insured", r"maximum payable"
        ],
        "inclusion": [
            r"scope of cover", r"benefits covered", r"inclusions?", r"what is covered",
            r"basic covers?", r"hospitalization expenses?"
        ],
        "condition": [
            r"claim procedure", r"terms and conditions?", r"general conditions?",
            r"notice of claim", r"cancellation", r"renewal"
        ]
    }

    CLAUSE_SPLIT_REGEX = re.compile(
        r'(?=(?:^|\n)(?:'
        r'(?:Section|Clause|Article|Condition|Item)\s*(?:\d+(?:\.\d+)*|[A-Z])|'
        r'\d+\.\s+[A-Z]|'
        r'\d+\.\d+\s+[A-Z]|'
        r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*:\s*\n|'
        r'[A-Z\s]{4,}:'
        r'))',
        re.MULTILINE
    )

    @classmethod
    def compute_file_hash(cls, file_bytes: bytes) -> str:
        """Returns sha256 hash of file content"""
        return hashlib.sha256(file_bytes).hexdigest()

    @classmethod
    def detect_section_type(cls, text: str, title: str) -> str:
        """Classify clause into an insurance semantic section type"""
        search_target = f"{title.lower()} {text[:200].lower()}"
        for section_type, patterns in cls.SECTION_PATTERNS.items():
            for pat in patterns:
                if re.search(r'\b' + pat + r'\b', search_target):
                    return section_type
        return "general"

    @classmethod
    def process_pdf_bytes(cls, pdf_bytes: bytes, filename: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Parses PDF bytes and outputs:
        1. Document metadata (page count, hash, size)
        2. Extracted clauses with layout metadata
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        file_hash = cls.compute_file_hash(pdf_bytes)
        
        extracted_clauses: List[Dict[str, Any]] = []
        clause_index = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if not text.strip():
                continue

            # Split text into logical clause blocks
            raw_blocks = cls.CLAUSE_SPLIT_REGEX.split(text)
            
            for block in raw_blocks:
                cleaned_block = block.strip()
                if len(cleaned_block) < 40:
                    # Filter out short headers/footers
                    continue

                lines = [line.strip() for line in cleaned_block.split('\n') if line.strip()]
                if not lines:
                    continue

                title = lines[0]
                if len(title) > 90:
                    title = title[:90] + "..."

                body = "\n".join(lines[1:]) if len(lines) > 1 else lines[0]
                section_type = cls.detect_section_type(body, title)

                clause_index += 1
                extracted_clauses.append({
                    "clause_index": clause_index,
                    "title": title,
                    "text": cleaned_block,
                    "page_number": page_num + 1,
                    "section_type": section_type
                })

        doc_meta = {
            "filename": filename,
            "file_hash": file_hash,
            "file_size": len(pdf_bytes),
            "total_clauses": len(extracted_clauses),
            "total_pages": len(doc)
        }
        
        doc.close()
        return doc_meta, extracted_clauses
