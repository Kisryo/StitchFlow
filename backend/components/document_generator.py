"""
Document Generator Component.

Uses Z.AI GLM to generate structured output documents from workflow analysis.
Produces summary documents, draft emails, and notification content —
no external APIs required, only GLM.
Also generates downloadable PDF reports.
"""
import time
from typing import Dict, Any, List, Optional

from fpdf import FPDF
from models import Classification, Entity, Ambiguity, Conflict, Recommendation
from components.glm_client import glm_client


async def generate_summary_document(
    workflow_id: str,
    classification: Classification,
    entities: List[Entity],
    ambiguities: List[Ambiguity],
    conflicts: List[Conflict],
    recommendations: List[Recommendation],
    clarifications: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Generate a structured summary document from workflow analysis.

    Uses GLM to compile all analysis results into a clean, human-readable
    structured document.

    Returns:
        Dict with document sections and formatted content.
    """
    start_time = time.time()

    entities_text = "\n".join([f"- {e.entity_type}: {e.value}" for e in entities[:8]])
    ambiguities_text = "\n".join([f"- {a.description}" for a in ambiguities[:5]]) if ambiguities else "None"
    conflicts_text = "\n".join([f"- {c.description}" for c in conflicts[:5]]) if conflicts else "None"
    recommendations_text = "\n".join([f"- [{r.action_type}] {r.description}" for r in recommendations[:5]])

    clarifications_text = ""
    if clarifications:
        clarifications_text = "\n\nUser Clarifications Provided:\n" + "\n".join([
            f"- {c.get('ambiguity_id', 'N/A')}: {c.get('answer', 'N/A')}" for c in clarifications[:5]
        ])

    prompt = f"""Based on the following AI analysis of a document, generate a comprehensive structured summary document.

Document Classification:
- Type: {classification.document_type}
- Intent: {classification.intent}
- Confidence: {classification.confidence:.0%}

Extracted Entities:
{entities_text}

Ambiguities Found:
{ambiguities_text}

Conflicts Detected:
{conflicts_text}
{clarifications_text}

Recommendations:
{recommendations_text}

Generate a structured document with these sections:
1. "title" - A clear title for this document analysis
2. "executive_summary" - 2-3 sentence summary of what was analyzed and the key findings
3. "classification" - The document type and intent
4. "key_findings" - List of the most important extracted information (max 8 items, each as a short sentence)
5. "issues_resolved" - List of ambiguities/conflicts and how they were resolved (or flagged as needing attention)
6. "recommendations_summary" - List of recommended actions with brief justification
7. "draft_email" - A ready-to-send email draft summarizing this analysis for a stakeholder, with subject line and body
8. "next_steps" - 2-3 concrete next steps

Respond with JSON in this exact format:
{{
    "title": "...",
    "executive_summary": "...",
    "classification": "...",
    "key_findings": ["...", "..."],
    "issues_resolved": ["...", "..."],
    "recommendations_summary": ["...", "..."],
    "draft_email": {{"subject": "...", "body": "..."}},
    "next_steps": ["...", "..."]
}}"""

    try:
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "executive_summary": {"type": "string"},
                "classification": {"type": "string"},
                "key_findings": {"type": "array", "items": {"type": "string"}},
                "issues_resolved": {"type": "array", "items": {"type": "string"}},
                "recommendations_summary": {"type": "array", "items": {"type": "string"}},
                "draft_email": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "body": {"type": "string"}
                    },
                    "required": ["subject", "body"]
                },
                "next_steps": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["title", "executive_summary", "classification", "key_findings", "recommendations_summary", "draft_email", "next_steps"]
        }

        result = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            temperature=0.5,
        )

        generation_time = time.time() - start_time
        print(f"[Document Generator] Summary document generated in {generation_time:.2f}s")

        return {
            "success": True,
            "document": result,
            "generation_time": generation_time,
        }

    except Exception as e:
        generation_time = time.time() - start_time
        print(f"[Document Generator] Failed to generate document: {str(e)}")

        return {
            "success": False,
            "document": {
                "title": f"Analysis Summary - {classification.document_type}",
                "executive_summary": f"Document classified as {classification.document_type} with intent: {classification.intent}. {len(entities)} entities extracted, {len(recommendations)} recommendations generated.",
                "classification": f"{classification.document_type} - {classification.intent}",
                "key_findings": [f"{e.entity_type}: {e.value}" for e in entities[:8]],
                "issues_resolved": [a.description for a in ambiguities[:5]],
                "recommendations_summary": [f"[{r.action_type}] {r.description}" for r in recommendations[:5]],
                "draft_email": {
                    "subject": f"Document Analysis: {classification.document_type}",
                    "body": f"Analysis of {classification.document_type} document completed. {len(entities)} entities extracted, {len(recommendations)} recommendations generated. Please review the full analysis for details.",
                },
                "next_steps": ["Review the full analysis", "Approve or modify recommendations", "Proceed with execution"],
            },
            "generation_time": generation_time,
            "error": str(e),
        }


def generate_pdf(document: Dict[str, Any]) -> bytes:
    """
    Generate a PDF report from a structured document.

    Args:
        document: Structured document dict with title, executive_summary, etc.

    Returns:
        PDF file content as bytes
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, text=document.get("title", "Analysis Report"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Executive Summary
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, text="Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, text=document.get("executive_summary", ""))
    pdf.ln(4)

    # Classification
    if document.get("classification"):
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, text="Classification", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, text=document["classification"])
        pdf.ln(4)

    # Key Findings
    findings = document.get("key_findings", [])
    if findings:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, text="Key Findings", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for finding in findings:
            pdf.cell(6, 6, text=chr(8226))
            pdf.multi_cell(0, 6, text=f" {finding}")
        pdf.ln(4)

    # Issues Resolved
    issues = document.get("issues_resolved", [])
    if issues:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, text="Issues Resolved", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for issue in issues:
            pdf.cell(6, 6, text=chr(8226))
            pdf.multi_cell(0, 6, text=f" {issue}")
        pdf.ln(4)

    # Recommendations
    recs = document.get("recommendations_summary", [])
    if recs:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, text="Recommendations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for rec in recs:
            pdf.cell(6, 6, text=chr(8226))
            pdf.multi_cell(0, 6, text=f" {rec}")
        pdf.ln(4)

    # Draft Email
    draft = document.get("draft_email")
    if draft:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, text="Draft Email", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, text=f"Subject: {draft.get('subject', '')}")
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)
        pdf.multi_cell(0, 6, text=draft.get("body", ""))
        pdf.ln(4)

    # Next Steps
    steps = document.get("next_steps", [])
    if steps:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, text="Next Steps", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for i, step in enumerate(steps, 1):
            pdf.multi_cell(0, 6, text=f"{i}. {step}")

    return pdf.output()
