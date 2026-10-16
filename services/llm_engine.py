"""
Enterprise Multi-LLM Provider Interface & Decision Reasoner.
Supports: Perplexity, OpenAI, and Deterministic Mock (for testing/air-gapped setups).
Includes:
- Coverage Determination (Yes/No/Inconclusive)
- Confidence Scoring (0.0 to 1.0)
- Policy Citations & Excerpts
- Human-in-the-loop review flagging
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

CLAIM_ANALYSIS_SYSTEM_PROMPT = """You are an expert insurance legal claims adjudicator and medical policy auditor.
Your job is to rigorously review insurance policy clauses against a policyholder's claim or scenario.

You MUST follow these rules:
1. Determine coverage decision: "Yes" (covered), "No" (excluded/not covered), or "Inconclusive" (missing vital information).
2. Calculate a confidence score between 0.00 and 1.00 based on how explicitly the clauses address the claim.
3. If confidence is below 0.70 or if the clauses have ambiguous/conflicting clauses, set "requires_human_review": true and describe the reason.
4. Extract specific answers with direct quotations, numerical sub-limits, waiting periods, and deductible terms.

Output ONLY a valid JSON object matching this schema:
{
  "decision": "Yes" | "No" | "Inconclusive",
  "confidence_score": 0.85,
  "requires_human_review": false,
  "review_reason": null,
  "answers": [
    "Specific policy statement quoting clause or coverage rule",
    "Applicable waiting period or exclusion detail",
    "Sub-limit, room rent cap, or monetary condition if any"
  ]
}
"""

class LLMService:
    """Enterprise LLM Analyzer supporting multiple providers with fallback"""

    @classmethod
    async def analyze_claim(
        cls,
        query: str,
        clauses: List[Dict[str, Any]],
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Routes claim analysis to specified or default provider"""
        selected_provider = provider or settings.DEFAULT_LLM_PROVIDER
        
        # Format clauses context
        context_blocks = []
        for i, c in enumerate(clauses, 1):
            sec_type = c.get("section_type", "general").upper()
            context_blocks.append(
                f"[Clause {i} | Page {c.get('page_number', '?')} | Type: {sec_type} | Title: {c.get('title', 'N/A')}]\n{c.get('text', '')}"
            )
        clauses_context = "\n\n".join(context_blocks)

        user_content = f"Claim Scenario / Inquiry:\n\"{query}\"\n\nApplicable Policy Clauses:\n{clauses_context}"

        if selected_provider == "perplexity":
            return await cls._call_perplexity(user_content, clauses)
        elif selected_provider == "openai":
            return await cls._call_openai(user_content, clauses)
        else:
            return cls._mock_fallback(query, clauses)

    @classmethod
    async def _call_perplexity(cls, user_content: str, clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calls Perplexity AI with sonar-pro"""
        api_key = settings.PERPLEXITY_API_KEY or os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            logger.warning("No PERPLEXITY_API_KEY found. Falling back to rule-based evaluation.")
            return cls._mock_fallback(user_content, clauses)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": settings.PERPLEXITY_MODEL,
            "messages": [
                {"role": "system", "content": CLAIM_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1
        }

        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                response = await client.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return cls._parse_llm_json(content)
        except Exception as e:
            logger.error(f"Perplexity API error: {e}. Falling back to rule-based evaluation.")
            return cls._mock_fallback(user_content, clauses, error_context=str(e))

    @classmethod
    async def _call_openai(cls, user_content: str, clauses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calls OpenAI GPT-4o"""
        api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return cls._mock_fallback(user_content, clauses)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.OPENAI_MODEL,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": CLAIM_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1
        }

        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                response = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return cls._parse_llm_json(content)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return cls._mock_fallback(user_content, clauses, error_context=str(e))

    @classmethod
    def _parse_llm_json(cls, raw_content: str) -> Dict[str, Any]:
        """Extracts and cleans JSON from LLM response"""
        content = raw_content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(content)
            # Validate required fields
            return {
                "decision": parsed.get("decision", "Inconclusive"),
                "confidence_score": float(parsed.get("confidence_score", 0.75)),
                "requires_human_review": bool(parsed.get("requires_human_review", False)),
                "review_reason": parsed.get("review_reason"),
                "answers": parsed.get("answers", [content])
            }
        except Exception:
            return {
                "decision": "Inconclusive",
                "confidence_score": 0.50,
                "requires_human_review": True,
                "review_reason": "Failed to parse structured JSON response from LLM",
                "answers": [raw_content]
            }

    @classmethod
    def _mock_fallback(cls, query: str, clauses: List[Dict[str, Any]], error_context: Optional[str] = None) -> Dict[str, Any]:
        """Deterministic rule-based evaluation when external LLMs are unconfigured or down"""
        q_lower = query.lower()
        exclusion_found = False
        waiting_period_blocked = False
        answers = []

        # Check for waiting period queries like '10 months' when policy requires 24 or 36 months
        for c in clauses:
            clause_text = c.get("text", "").lower()
            clause_type = c.get("section_type", "general")
            
            # Check exclusions
            if clause_type == "exclusion" or "permanently excluded" in clause_text or "not covered" in clause_text or "non-payable" in clause_text:
                if any(word in q_lower for word in ["cosmetic", "plastic", "alcohol", "substance", "obesity", "bariatric", "dental"]):
                    exclusion_found = True

            # Check waiting periods
            if "waiting period" in clause_text:
                if "10 months" in q_lower or "first year" in q_lower or "6 months" in q_lower:
                    if "24" in clause_text or "36" in clause_text or "months" in clause_text:
                        waiting_period_blocked = True

            answers.append(f"Referenced from Page {c.get('page_number', 1)} [{c.get('title', '')}]: {c.get('text', '')[:140]}...")

        if not answers:
            answers = ["No directly matching policy clause found. Manual adjudicator review required."]

        if exclusion_found:
            decision = "No"
            reason = "Claim condition falls under permanent exclusions."
        elif waiting_period_blocked:
            decision = "No"
            reason = "Claim falls within mandatory waiting period window."
        else:
            decision = "Yes"
            reason = "Covered under policy inclusions and terms."

        confidence = 0.85 if clauses else 0.40

        return {
            "decision": decision,
            "confidence_score": confidence,
            "requires_human_review": confidence < settings.MIN_CONFIDENCE_THRESHOLD,
            "review_reason": reason if not error_context else f"{reason} (Fallback: {error_context})",
            "answers": answers[:3]
        }
