"""
T&C Comparison Component.

Extracts clauses from Terms & Conditions documents and compares them
using GLM for semantic similarity analysis.
"""
import re
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from components.glm_client import glm_client


# Clause-splitting patterns
CLAUSE_PATTERNS = [
    re.compile(r'(?:^|\n)\s*(\d+(?:\.\d+)*)\s+[\.\)]\s*(.*?)(?=(?:\n\s*\d+(?:\.\d+)*\s+[\.\)])|$)', re.DOTALL),
    re.compile(r'(?:^|\n)\s*(Section\s+\d+[A-Za-z]*\.?)\s*(.*?)(?=(?:\n\s*Section\s+\d+[A-Za-z]*\.?)|$)', re.DOTALL | re.IGNORECASE),
    re.compile(r'(?:^|\n)\s*(Article\s+[IVXLC]+\.?)\s*(.*?)(?=(?:\n\s*Article\s+[IVXLC]+\.?)|$)', re.DOTALL | re.IGNORECASE),
]


def extract_clauses(text: str) -> List[Dict[str, str]]:
    """
    Extract individual clauses from a T&C document.

    Tries numbered clause patterns first, then falls back to
    paragraph-based splitting.

    Args:
        text: Full document text

    Returns:
        List of dicts with 'clause_id' and 'content' keys
    """
    clauses = []

    for pattern in CLAUSE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            for match in matches:
                if isinstance(match, tuple):
                    clause_id, content = match
                else:
                    clause_id = f"clause_{len(clauses) + 1}"
                    content = match
                content = content.strip()
                if content and len(content) > 20:
                    clauses.append({
                        "clause_id": clause_id.strip(),
                        "content": content,
                    })
            if clauses:
                return clauses

    # Fallback: split by double newlines (paragraph-based)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 20]
    for i, para in enumerate(paragraphs):
        clauses.append({
            "clause_id": f"paragraph_{i + 1}",
            "content": para,
        })

    return clauses


async def compare_clauses(
    clauses_a: List[Dict[str, str]],
    clauses_b: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Compare clauses from two T&C documents using GLM.

    For each clause in document A, find the most similar clause in document B
    and classify the relationship.

    Args:
        clauses_a: Clauses from document A
        clauses_b: Clauses from document B

    Returns:
        List of comparison results with similarity classification
    """
    if not clauses_a or not clauses_b:
        return []

    # Build comparison context (limit to avoid token overflow)
    max_clauses = 15
    a_text = "\n".join([f"[{c['clause_id']}] {c['content'][:200]}" for c in clauses_a[:max_clauses]])
    b_text = "\n".join([f"[{c['clause_id']}] {c['content'][:200]}" for c in clauses_b[:max_clauses]])

    prompt = f"""Compare these two sets of Terms & Conditions clauses.

Document A clauses:
{a_text}

Document B clauses:
{b_text}

For each clause in Document A, find the best matching clause in Document B (if any).
Classify each match as one of:
- "precedent": Same meaning, Document A clause is a prior version
- "ai_generated": Clause appears to be AI-generated or significantly rephrased
- "needs_review": Meaningful differences that need human review
- "identical": Same clause in both documents
- "unique_a": No matching clause in Document B
- "unique_b": Clause in Document B with no match in Document A

Respond with JSON array:
[
  {{
    "clause_a_id": "id from doc A",
    "clause_b_id": "id from doc B or null",
    "classification": "precedent|ai_generated|needs_review|identical|unique_a|unique_b",
    "similarity_score": 0.85,
    "summary": "Brief summary of the difference or similarity"
  }}
]"""

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "clause_a_id": {"type": "string"},
                "clause_b_id": {"type": ["string", "null"]},
                "classification": {"type": "string"},
                "similarity_score": {"type": "number"},
                "summary": {"type": "string"},
            },
            "required": ["clause_a_id", "classification", "similarity_score", "summary"],
        },
    }

    try:
        response = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            temperature=0.3,
        )
        return response
    except Exception as e:
        # Fallback: simple keyword-based comparison
        results = []
        for ca in clauses_a[:max_clauses]:
            best_match = None
            best_score = 0.0
            for cb in clauses_b:
                words_a = set(ca["content"].lower().split())
                words_b = set(cb["content"].lower().split())
                if not words_a or not words_b:
                    continue
                overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                if overlap > best_score:
                    best_score = overlap
                    best_match = cb

            if best_match and best_score > 0.3:
                classification = "identical" if best_score > 0.8 else "needs_review"
                results.append({
                    "clause_a_id": ca["clause_id"],
                    "clause_b_id": best_match["clause_id"],
                    "classification": classification,
                    "similarity_score": round(best_score, 2),
                    "summary": f"{'Similar' if best_score > 0.5 else 'Different'} clauses",
                })
            else:
                results.append({
                    "clause_a_id": ca["clause_id"],
                    "clause_b_id": None,
                    "classification": "unique_a",
                    "similarity_score": 0.0,
                    "summary": "No matching clause found in Document B",
                })

        return results
