"""
PII Redaction Engine.

Detects and masks Personally Identifiable Information (PII) before AI processing.
"""
import re
from typing import List, Dict, Tuple
import time
from sqlalchemy.orm import Session

from models import PIIMatch, RedactionResult, WorkflowState
from database.utils import get_workflow


# PII Detection Patterns
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_PATTERN = r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'
SSN_PATTERN = r'\b\d{3}-\d{2}-\d{4}\b'

# Address patterns (simplified)
ADDRESS_PATTERN = r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir)\b'

# Name patterns (capitalized words, 2-4 words)
NAME_PATTERN = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b'


def identify_pii_patterns(text: str) -> List[PIIMatch]:
    """
    Identify all PII patterns in text.
    
    Args:
        text: Input text to scan for PII
        
    Returns:
        List of PIIMatch objects with detected PII
    """
    pii_matches = []
    
    # Detect emails
    for match in re.finditer(EMAIL_PATTERN, text):
        pii_matches.append(PIIMatch(
            pii_type="email",
            original_value=match.group(),
            masked_token=f"[EMAIL_{len([m for m in pii_matches if m.pii_type == 'email']) + 1}]",
            start_pos=match.start(),
            end_pos=match.end()
        ))
    
    # Detect phone numbers
    for match in re.finditer(PHONE_PATTERN, text):
        pii_matches.append(PIIMatch(
            pii_type="phone",
            original_value=match.group(),
            masked_token=f"[PHONE_{len([m for m in pii_matches if m.pii_type == 'phone']) + 1}]",
            start_pos=match.start(),
            end_pos=match.end()
        ))
    
    # Detect SSNs
    for match in re.finditer(SSN_PATTERN, text):
        pii_matches.append(PIIMatch(
            pii_type="ssn",
            original_value=match.group(),
            masked_token=f"[SSN_{len([m for m in pii_matches if m.pii_type == 'ssn']) + 1}]",
            start_pos=match.start(),
            end_pos=match.end()
        ))
    
    # Detect addresses
    for match in re.finditer(ADDRESS_PATTERN, text, re.IGNORECASE):
        pii_matches.append(PIIMatch(
            pii_type="address",
            original_value=match.group(),
            masked_token=f"[ADDRESS_{len([m for m in pii_matches if m.pii_type == 'address']) + 1}]",
            start_pos=match.start(),
            end_pos=match.end()
        ))
    
    # Detect names (more conservative - only if not already matched)
    # Skip names that overlap with other PII
    existing_ranges = [(m.start_pos, m.end_pos) for m in pii_matches]
    
    for match in re.finditer(NAME_PATTERN, text):
        start, end = match.start(), match.end()
        
        # Check if this range overlaps with existing PII
        overlaps = any(
            (start >= existing_start and start < existing_end) or
            (end > existing_start and end <= existing_end)
            for existing_start, existing_end in existing_ranges
        )
        
        if not overlaps:
            # Additional validation: name should be 2-4 words
            name = match.group()
            word_count = len(name.split())
            if 2 <= word_count <= 4:
                pii_matches.append(PIIMatch(
                    pii_type="name",
                    original_value=name,
                    masked_token=f"[NAME_{len([m for m in pii_matches if m.pii_type == 'name']) + 1}]",
                    start_pos=start,
                    end_pos=end
                ))
    
    # Sort by position (important for replacement)
    pii_matches.sort(key=lambda x: x.start_pos)
    
    return pii_matches


def redact_pii(text: str) -> RedactionResult:
    """
    Redact PII from text and create token mapping.
    
    Args:
        text: Original text content
        
    Returns:
        RedactionResult with redacted text and token mapping
    """
    start_time = time.time()
    
    # Identify all PII
    pii_matches = identify_pii_patterns(text)
    
    # Create redacted text by replacing PII with tokens
    redacted_text = text
    token_map = {}
    
    # Replace from end to start to maintain positions
    for match in reversed(pii_matches):
        redacted_text = (
            redacted_text[:match.start_pos] +
            match.masked_token +
            redacted_text[match.end_pos:]
        )
        token_map[match.masked_token] = match.original_value
    
    redaction_time = time.time() - start_time
    
    # Create a dummy workflow_id for now (will be set by caller)
    result = RedactionResult(
        workflow_id="",  # Will be set by caller
        original_text=text,
        redacted_text=redacted_text,
        token_map=token_map,
        pii_matches=pii_matches,
        redaction_time=redaction_time
    )
    
    return result


def restore_pii(redacted_text: str, token_map: Dict[str, str]) -> str:
    """
    Restore original PII from redacted text using token mapping.
    
    Args:
        redacted_text: Text with masked tokens
        token_map: Mapping from tokens to original values
        
    Returns:
        Original text with PII restored
    """
    restored_text = redacted_text
    
    # Replace tokens with original values
    for token, original_value in token_map.items():
        restored_text = restored_text.replace(token, original_value)
    
    return restored_text


async def redact_workflow_document(
    workflow_id: str,
    db: Session
) -> RedactionResult:
    """
    Redact PII from workflow document and update workflow state.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        RedactionResult with redacted text and token mapping
        
    Raises:
        ValueError: If workflow not found or has no document text
    """
    # Get workflow
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")
    
    if not workflow.document_text:
        raise ValueError(f"Workflow {workflow_id} has no document text to redact")
    
    # Redact PII
    result = redact_pii(workflow.document_text)
    result.workflow_id = workflow_id
    
    # Update workflow with redacted text and token map
    workflow.redacted_text = result.redacted_text
    workflow.token_map = result.token_map
    workflow.state = WorkflowState.REDACTED.value
    
    # Commit changes
    db.commit()
    db.refresh(workflow)
    
    # Log audit entry
    from database.utils import log_audit_entry
    log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="state_transition",
        actor="system",
        details={
            "from_state": "Ingested",
            "to_state": "Redacted",
            "reason": f"PII redaction complete. Found {len(result.pii_matches)} PII instances."
        }
    )
    
    return result
