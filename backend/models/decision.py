"""
Human decision and task execution models.

Models for human decisions, task results, and orchestration outcomes.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from datetime import datetime


class Decision(BaseModel):
    """
    Human decision in the workflow.
    
    Captures user approval, rejection, clarification, or modification.
    """
    decision_id: str = Field(..., description="Unique decision identifier")
    workflow_id: str = Field(..., description="Associated workflow ID")
    decision_type: Literal["approval", "rejection", "clarification", "modification"] = Field(
        ...,
        description="Type of decision made"
    )
    user_id: str = Field(..., description="User who made the decision")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When decision was made"
    )
    reasoning: Optional[str] = Field(None, description="User's reasoning for decision")
    modifications: Dict = Field(
        default_factory=dict,
        description="Modifications made by user (if any)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "dec_001",
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "decision_type": "approval",
                "user_id": "user@example.com",
                "timestamp": "2024-01-01T00:10:00Z",
                "reasoning": "All details look correct, approved for execution",
                "modifications": {}
            }
        }


class TaskResult(BaseModel):
    """
    Result of a single task execution.
    
    Represents outcome of executing one recommendation/action.
    """
    task_id: str = Field(..., description="Unique task identifier")
    task_type: str = Field(..., description="Type of task executed")
    success: bool = Field(..., description="Whether task succeeded")
    result_data: Dict = Field(
        default_factory=dict,
        description="Task-specific result data"
    )
    error: Optional[str] = Field(None, description="Error message if task failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_001",
                "task_type": "sync_sheets",
                "success": True,
                "result_data": {
                    "sheet_id": "abc123",
                    "rows_updated": 1,
                    "range": "A2:E2"
                },
                "error": None,
                "execution_time": 0.8,
                "retry_count": 0
            }
        }


class OrchestrationResult(BaseModel):
    """
    Result of orchestrating multiple tasks.
    
    Contains outcomes of all tasks executed for a workflow.
    """
    workflow_id: str = Field(..., description="Associated workflow ID")
    task_results: List[TaskResult] = Field(..., description="Results of all tasks")
    overall_success: bool = Field(..., description="Whether all tasks succeeded")
    failed_tasks: List[str] = Field(
        default_factory=list,
        description="IDs of tasks that failed"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "task_results": [
                    {
                        "task_id": "task_001",
                        "task_type": "sync_sheets",
                        "success": True,
                        "result_data": {},
                        "error": None,
                        "execution_time": 0.8,
                        "retry_count": 0
                    }
                ],
                "overall_success": True,
                "failed_tasks": []
            }
        }


class AuditEntry(BaseModel):
    """
    Audit log entry for workflow actions.
    
    Immutable record of all workflow activities.
    """
    entry_id: str = Field(..., description="Unique audit entry identifier")
    workflow_id: str = Field(..., description="Associated workflow ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When action occurred"
    )
    action_type: str = Field(
        ...,
        description="Type of action (state_transition, glm_decision, human_decision, policy_check, task_execution)"
    )
    actor: str = Field(..., description="Who/what performed the action (user_id or 'system' or 'glm')")
    details: Dict = Field(..., description="Action-specific details")
    hash: str = Field(..., description="Hash of entry for tamper detection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entry_id": "audit_001",
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-01T00:00:00Z",
                "action_type": "state_transition",
                "actor": "system",
                "details": {
                    "from_state": "New",
                    "to_state": "Ingested",
                    "reason": "Document uploaded successfully"
                },
                "hash": "a1b2c3d4e5f6..."
            }
        }
