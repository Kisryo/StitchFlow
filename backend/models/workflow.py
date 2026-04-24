"""
Workflow state management models.

Defines the core workflow state machine and workflow data structures.
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime
from enum import Enum


class WorkflowState(str, Enum):
    """
    Workflow state machine states.
    
    State transitions follow the state machine defined in design.md:
    New → Ingested → Redacted → Parsed → [Needs Clarification | Policy Review Required | Ready for Review]
    → Draft Ready → Approved → Executed → [Retrying | Completed]
    
    Terminal states: Completed, Failed, Escalated
    """
    NEW = "New"
    INGESTED = "Ingested"
    REDACTED = "Redacted"
    PARSED = "Parsed"
    NEEDS_CLARIFICATION = "NeedsClarification"
    POLICY_REVIEW_REQUIRED = "PolicyReviewRequired"
    READY_FOR_REVIEW = "ReadyForReview"
    DRAFT_READY = "DraftReady"
    APPROVED = "Approved"
    EXECUTED = "Executed"
    RETRYING = "Retrying"
    FAILED = "Failed"
    ESCALATED = "Escalated"
    COMPLETED = "Completed"
    
    @classmethod
    def is_terminal(cls, state: "WorkflowState") -> bool:
        """Check if a state is terminal (no further transitions allowed)."""
        return state in {cls.COMPLETED, cls.FAILED, cls.ESCALATED}
    
    @classmethod
    def requires_human_action(cls, state: "WorkflowState") -> bool:
        """Check if a state requires human intervention."""
        return state in {
            cls.NEEDS_CLARIFICATION,
            cls.POLICY_REVIEW_REQUIRED,
            cls.READY_FOR_REVIEW,
            cls.DRAFT_READY
        }


class Workflow(BaseModel):
    """
    Core workflow entity representing a single workflow instance.
    
    Tracks the complete lifecycle of a document through the StitchFlow system,
    from ingestion through processing to completion.
    """
    workflow_id: str = Field(..., description="Unique workflow identifier (UUID)")
    state: WorkflowState = Field(default=WorkflowState.NEW, description="Current workflow state")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Workflow creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    created_by: str = Field(..., description="User who created the workflow")
    
    # Document content
    document_path: Optional[str] = Field(None, description="Path to original uploaded document")
    document_text: Optional[str] = Field(None, description="Extracted text from document")
    redacted_text: Optional[str] = Field(None, description="PII-redacted text for AI processing")
    
    # PII redaction mapping
    token_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping between masked tokens and original PII values"
    )
    
    # Additional metadata
    metadata: Dict = Field(
        default_factory=dict,
        description="Additional workflow metadata (file type, size, etc.)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "state": "New",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "created_by": "user@example.com",
                "document_path": "/uploads/document.pdf",
                "document_text": None,
                "redacted_text": None,
                "token_map": {},
                "metadata": {
                    "file_type": "pdf",
                    "file_size": 1024000
                }
            }
        }


class WorkflowStateTransition(BaseModel):
    """
    Represents a state transition in the workflow.
    
    Used for validation and audit logging of state changes.
    """
    workflow_id: str
    from_state: WorkflowState
    to_state: WorkflowState
    reason: str = Field(..., description="Reason for state transition")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str = Field(default="system", description="Who/what triggered the transition")
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "from_state": "New",
                "to_state": "Ingested",
                "reason": "Document uploaded and text extracted successfully",
                "timestamp": "2024-01-01T00:01:00Z",
                "actor": "system"
            }
        }


# Valid state transitions (state machine rules)
VALID_TRANSITIONS: Dict[WorkflowState, list[WorkflowState]] = {
    WorkflowState.NEW: [WorkflowState.INGESTED, WorkflowState.FAILED],
    WorkflowState.INGESTED: [WorkflowState.REDACTED, WorkflowState.FAILED],
    WorkflowState.REDACTED: [WorkflowState.PARSED, WorkflowState.FAILED],
    WorkflowState.PARSED: [
        WorkflowState.NEEDS_CLARIFICATION,
        WorkflowState.POLICY_REVIEW_REQUIRED,
        WorkflowState.READY_FOR_REVIEW,
        WorkflowState.FAILED
    ],
    WorkflowState.NEEDS_CLARIFICATION: [WorkflowState.PARSED, WorkflowState.FAILED],
    WorkflowState.POLICY_REVIEW_REQUIRED: [WorkflowState.READY_FOR_REVIEW, WorkflowState.FAILED],
    WorkflowState.READY_FOR_REVIEW: [
        WorkflowState.DRAFT_READY,
        WorkflowState.APPROVED,
        WorkflowState.FAILED
    ],
    WorkflowState.DRAFT_READY: [
        WorkflowState.APPROVED,
        WorkflowState.READY_FOR_REVIEW,
        WorkflowState.FAILED
    ],
    WorkflowState.APPROVED: [WorkflowState.EXECUTED, WorkflowState.FAILED],
    WorkflowState.EXECUTED: [
        WorkflowState.COMPLETED,
        WorkflowState.RETRYING,
        WorkflowState.FAILED
    ],
    WorkflowState.RETRYING: [
        WorkflowState.EXECUTED,
        WorkflowState.ESCALATED,
        WorkflowState.FAILED
    ],
    # Terminal states have no valid transitions
    WorkflowState.COMPLETED: [],
    WorkflowState.FAILED: [],
    WorkflowState.ESCALATED: []
}


def is_valid_transition(from_state: WorkflowState, to_state: WorkflowState) -> bool:
    """
    Validate if a state transition is allowed.
    
    Args:
        from_state: Current workflow state
        to_state: Desired next state
        
    Returns:
        True if transition is valid, False otherwise
    """
    return to_state in VALID_TRANSITIONS.get(from_state, [])
