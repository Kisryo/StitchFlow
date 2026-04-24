"""
Workflow API endpoints.

Handles workflow creation, file uploads, and workflow management.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid
import os
from datetime import datetime

from database.base import get_db
from database.utils import create_workflow, get_workflow, list_workflows
from models import Workflow, WorkflowState, DocumentMetadata
from config.settings import settings
from components.ingestion import ingest_document
from components.redaction import redact_workflow_document
from components.reasoning import run_reasoning_chain
from components.policy_screening import screen_policy

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


# Request/Response models for API
class CreateWorkflowRequest(BaseModel):
    """Request body for creating a new workflow."""
    name: str
    description: str = "string"


@router.post("/", status_code=201)
async def create_new_workflow(
    request: CreateWorkflowRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new workflow.
    
    Args:
        request: Workflow creation request with name and description
        db: Database session
        
    Returns:
        Created workflow details
    """
    workflow_id = str(uuid.uuid4())
    
    workflow = Workflow(
        workflow_id=workflow_id,
        state=WorkflowState.NEW,
        created_by=request.name,  # Using name as created_by for now
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db_workflow = create_workflow(db, workflow)
    
    # Ensure workflow_id is explicitly returned
    response = {
        "workflow_id": workflow_id,  # Use the generated ID directly
        "name": request.name,
        "status": db_workflow.state,
        "document_type": "string",
        "created_at": db_workflow.created_at.isoformat() + "Z"
    }
    
    print(f"[API] Created workflow: {workflow_id}")  # Debug log
    
    return response


@router.post("/{workflow_id}/upload")
async def upload_document(
    workflow_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload document to workflow.
    
    Args:
        workflow_id: Workflow identifier
        file: Uploaded file
        db: Database session
        
    Returns:
        Ingestion result with extracted text
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
    supported_types = {'pdf', 'docx', 'txt', 'eml', 'email'}
    if file_ext not in supported_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: {supported_types}"
        )
    
    # Validate file size
    max_size = settings.max_upload_size_mb * 1024 * 1024  # Convert MB to bytes
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum {settings.max_upload_size_mb}MB"
        )
    
    # Save file to upload directory
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, f"{workflow_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Ingest document (extract text)
    try:
        ingestion_result = await ingest_document(
            workflow_id=workflow_id,
            file_path=file_path,
            file_type=file_ext,
            db=db
        )
        
        return {
            "workflow_id": ingestion_result.workflow_id,
            "state": "Ingested",
            "extraction_result": {
                "extracted_text": ingestion_result.extracted_text[:500] + "..." if len(ingestion_result.extracted_text) > 500 else ingestion_result.extracted_text,
                "file_type": ingestion_result.file_type,
                "file_size": ingestion_result.file_size,
                "success": ingestion_result.success
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")


@router.get("/{workflow_id}")
async def get_workflow_details(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get workflow details.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Complete workflow information
    """
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    return {
        "workflow_id": workflow.workflow_id,
        "state": workflow.state,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
        "created_by": workflow.created_by,
        "document_path": workflow.document_path,
        "metadata": workflow.workflow_metadata
    }


@router.get("/")
async def list_all_workflows(
    state: Optional[str] = Query(None, description="Filter by workflow state"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    List workflows with optional filtering.
    
    Args:
        state: Filter by workflow state
        created_by: Filter by creator
        limit: Maximum results (1-100)
        offset: Pagination offset
        db: Database session
        
    Returns:
        List of workflows
    """
    # Convert state string to enum if provided
    state_enum = None
    if state:
        try:
            state_enum = WorkflowState(state)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    
    workflows = list_workflows(
        db=db,
        state=state_enum,
        created_by=created_by,
        limit=limit,
        offset=offset
    )
    
    return {
        "workflows": [
            {
                "workflow_id": w.workflow_id,
                "state": w.state,
                "created_at": w.created_at,
                "created_by": w.created_by
            }
            for w in workflows
        ],
        "total": len(workflows),
        "limit": limit,
        "offset": offset
    }


@router.post("/{workflow_id}/redact")
async def redact_pii(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Redact PII from workflow document.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Redaction result with PII statistics
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if not workflow.document_text:
        raise HTTPException(
            status_code=400,
            detail="Workflow has no document text to redact. Upload a document first."
        )
    
    try:
        result = await redact_workflow_document(workflow_id, db)
        
        # Group PII by type for statistics
        pii_by_type = {}
        for match in result.pii_matches:
            pii_by_type[match.pii_type] = pii_by_type.get(match.pii_type, 0) + 1
        
        return {
            "workflow_id": result.workflow_id,
            "state": "Redacted",
            "pii_found": len(result.pii_matches),
            "pii_by_type": pii_by_type,
            "redaction_time": result.redaction_time,
            "redacted_text_preview": result.redacted_text[:500] + "..." if len(result.redacted_text) > 500 else result.redacted_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PII redaction failed: {str(e)}")


@router.post("/{workflow_id}/reason")
async def run_reasoning(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Run GLM reasoning chain on workflow document.
    
    This is where the AI agent analyzes the document and makes intelligent decisions.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Reasoning result with classification, entities, ambiguities, and recommendations
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if not workflow.redacted_text:
        raise HTTPException(
            status_code=400,
            detail="Workflow has no redacted text. Upload and redact document first."
        )
    
    try:
        result = await run_reasoning_chain(workflow_id, db)
        
        return {
            "workflow_id": result.workflow_id,
            "state": "Parsed" if not result.ambiguities else "NeedsClarification",
            "classification": {
                "document_type": result.classification.document_type,
                "intent": result.classification.intent,
                "confidence": result.classification.confidence
            },
            "entities_found": len(result.entities),
            "entities": [
                {
                    "type": e.entity_type,
                    "value": e.value,
                    "confidence": e.confidence
                }
                for e in result.entities[:10]  # Show first 10
            ],
            "ambiguities_found": len(result.ambiguities),
            "ambiguities": [
                {
                    "type": a.ambiguity_type,
                    "description": a.description,
                    "question": a.clarification_question
                }
                for a in result.ambiguities
            ],
            "recommendations_generated": len(result.recommendations),
            "recommendations": [
                {
                    "id": r.recommendation_id,
                    "action": r.action_type,
                    "description": r.description,
                    "confidence": r.confidence
                }
                for r in result.recommendations
            ],
            "reasoning_time": result.reasoning_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reasoning failed: {str(e)}")


@router.get("/{workflow_id}/reason")
async def get_reasoning_results(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get existing reasoning results for a workflow.
    
    This endpoint retrieves previously computed reasoning results
    without re-running the reasoning chain.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Reasoning result if it exists
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Get reasoning result from database
    from database.models import ReasoningResultDB
    from models import ReasoningResult, Classification, Entity, Ambiguity, Conflict, Recommendation
    
    db_reasoning = (
        db.query(ReasoningResultDB)
        .filter(ReasoningResultDB.workflow_id == workflow_id)
        .order_by(ReasoningResultDB.created_at.desc())
        .first()
    )
    
    if not db_reasoning:
        raise HTTPException(
            status_code=404,
            detail="No reasoning results found for this workflow"
        )
    
    # Convert to Pydantic model
    # Handle conflicts - ensure conflicting_entities are dicts, not Entity objects
    conflicts_data = []
    for conflict in db_reasoning.conflicts:
        conflict_dict = dict(conflict) if not isinstance(conflict, dict) else conflict
        # Ensure conflicting_entities is a list of dicts
        if 'conflicting_entities' in conflict_dict and conflict_dict['conflicting_entities']:
            conflict_dict['conflicting_entities'] = [
                dict(e) if hasattr(e, '__dict__') else e
                for e in conflict_dict['conflicting_entities']
            ]
        conflicts_data.append(conflict_dict)
    
    reasoning_result = ReasoningResult(
        workflow_id=db_reasoning.workflow_id,
        classification=Classification(**db_reasoning.classification),
        entities=[Entity(**e) for e in db_reasoning.entities],
        ambiguities=[Ambiguity(**a) for a in db_reasoning.ambiguities],
        conflicts=[Conflict(**c) for c in conflicts_data],
        recommendations=[Recommendation(**r) for r in db_reasoning.recommendations],
        reasoning_time=db_reasoning.reasoning_time
    )
    
    return {
        "workflow_id": reasoning_result.workflow_id,
        "state": "Parsed" if not reasoning_result.ambiguities else "NeedsClarification",
        "classification": {
            "document_type": reasoning_result.classification.document_type,
            "intent": reasoning_result.classification.intent,
            "confidence": reasoning_result.classification.confidence
        },
        "entities_found": len(reasoning_result.entities),
        "entities": [
            {
                "type": e.entity_type,
                "value": e.value,
                "confidence": e.confidence
            }
            for e in reasoning_result.entities
        ],
        "ambiguities_found": len(reasoning_result.ambiguities),
        "ambiguities": [
            {
                "type": a.ambiguity_type,
                "description": a.description,
                "question": a.clarification_question,
                "possible_interpretations": a.possible_interpretations
            }
            for a in reasoning_result.ambiguities
        ],
        "recommendations_generated": len(reasoning_result.recommendations),
        "recommendations": [
            {
                "id": r.recommendation_id,
                "action": r.action_type,
                "description": r.description,
                "confidence": r.confidence
            }
            for r in reasoning_result.recommendations
        ],
        "reasoning_time": reasoning_result.reasoning_time
    }



@router.post("/{workflow_id}/screen")
async def screen_policy_violations(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Screen workflow recommendations against policy rules.
    
    This checks recommendations for compliance violations and calculates risk scores.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Policy screening result with violations and risk assessment
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Get reasoning result from database
    from database.models import ReasoningResultDB
    from models import ReasoningResult, Classification, Entity, Ambiguity, Conflict, Recommendation
    
    db_reasoning = (
        db.query(ReasoningResultDB)
        .filter(ReasoningResultDB.workflow_id == workflow_id)
        .order_by(ReasoningResultDB.created_at.desc())
        .first()
    )
    
    if not db_reasoning:
        raise HTTPException(
            status_code=400,
            detail="Workflow has no reasoning results. Run reasoning first."
        )
    
    # Convert database model to Pydantic model
    # Handle conflicts - ensure conflicting_entities are dicts, not Entity objects
    conflicts_data = []
    for conflict in db_reasoning.conflicts:
        conflict_dict = dict(conflict) if not isinstance(conflict, dict) else conflict
        # Ensure conflicting_entities is a list of dicts
        if 'conflicting_entities' in conflict_dict and conflict_dict['conflicting_entities']:
            conflict_dict['conflicting_entities'] = [
                dict(e) if hasattr(e, '__dict__') else e
                for e in conflict_dict['conflicting_entities']
            ]
        conflicts_data.append(conflict_dict)
    
    reasoning_result = ReasoningResult(
        workflow_id=db_reasoning.workflow_id,
        classification=Classification(**db_reasoning.classification),
        entities=[Entity(**e) for e in db_reasoning.entities],
        ambiguities=[Ambiguity(**a) for a in db_reasoning.ambiguities],
        conflicts=[Conflict(**c) for c in conflicts_data],
        recommendations=[Recommendation(**r) for r in db_reasoning.recommendations],
        reasoning_time=db_reasoning.reasoning_time
    )
    
    try:
        result = await screen_policy(workflow_id, reasoning_result, db)
        
        return {
            "workflow_id": result.workflow_id,
            "state": "PolicyReviewRequired" if result.requires_human_review else "ReadyForReview",
            "violations_found": len(result.violations),
            "violations": [
                {
                    "rule_name": v.rule_name,
                    "severity": v.severity,
                    "description": v.description,
                    "evidence": v.evidence,
                    "affected_recommendations": v.affected_recommendations
                }
                for v in result.violations
            ],
            "risk_score": result.risk_score,
            "requires_human_review": result.requires_human_review,
            "screening_time": result.screening_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy screening failed: {str(e)}")


@router.get("/{workflow_id}/screen")
async def get_policy_screening_results(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get existing policy screening results for a workflow.
    
    This endpoint retrieves previously computed policy screening results
    without re-running the screening.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Policy screening result if it exists
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Get policy screening result from database
    from database.models import PolicyScreeningResultDB
    from models import PolicyScreeningResult, Violation
    
    db_policy = (
        db.query(PolicyScreeningResultDB)
        .filter(PolicyScreeningResultDB.workflow_id == workflow_id)
        .order_by(PolicyScreeningResultDB.created_at.desc())
        .first()
    )
    
    if not db_policy:
        raise HTTPException(
            status_code=404,
            detail="No policy screening results found for this workflow"
        )
    
    # Convert to Pydantic model
    policy_result = PolicyScreeningResult(
        workflow_id=db_policy.workflow_id,
        violations=[Violation(**v) for v in db_policy.violations],
        risk_score=db_policy.risk_score,
        requires_human_review=db_policy.requires_human_review,
        screening_time=db_policy.screening_time
    )
    
    return {
        "workflow_id": policy_result.workflow_id,
        "state": "PolicyReviewRequired" if policy_result.requires_human_review else "ReadyForReview",
        "violations_found": len(policy_result.violations),
        "violations": [
            {
                "rule_name": v.rule_name,
                "severity": v.severity,
                "description": v.description,
                "evidence": v.evidence,
                "affected_recommendations": v.affected_recommendations
            }
            for v in policy_result.violations
        ],
        "risk_score": policy_result.risk_score,
        "requires_human_review": policy_result.requires_human_review,
        "screening_time": policy_result.screening_time
    }



@router.post("/{workflow_id}/run")
async def run_automated_workflow(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Run the complete automated workflow using LangGraph.
    
    This orchestrates all steps: ingest → redact → reason → screen_policy
    and pauses for human input when needed.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Workflow execution result
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if not workflow.document_path:
        raise HTTPException(
            status_code=400,
            detail="Workflow has no document. Upload a document first."
        )
    
    # Extract file type from document path
    import os
    file_ext = os.path.splitext(workflow.document_path)[1].lower().lstrip('.')
    
    try:
        from workflows.workflow_engine import run_workflow
        
        result = await run_workflow(
            workflow_id=workflow_id,
            document_path=workflow.document_path,
            file_type=file_ext,
            db=db
        )
        
        return {
            "workflow_id": result["workflow_id"],
            "final_state": result["final_state"],
            "requires_human_input": result["requires_human_input"],
            "human_input_type": result.get("human_input_type"),
            "error": result.get("error"),
            "execution_log": result.get("messages", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


# ============================================================================
# Human Decision Endpoints (Human-in-the-Loop)
# ============================================================================

class ClarificationRequest(BaseModel):
    """Request body for providing clarifications."""
    user_id: str
    clarifications: List[dict]  # List of {ambiguity_id, answer}
    reasoning: Optional[str] = None


@router.post("/{workflow_id}/clarify")
async def provide_clarification(
    workflow_id: str,
    request: ClarificationRequest,
    db: Session = Depends(get_db)
):
    """
    Provide clarification for ambiguous information.
    
    This endpoint allows users to answer clarification questions
    identified by the AI agent.
    
    Args:
        workflow_id: Workflow identifier
        request: Clarification data
        db: Database session
        
    Returns:
        Updated workflow state
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Verify workflow is in correct state
    if workflow.state != WorkflowState.NEEDS_CLARIFICATION.value:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not in 'NeedsClarification' state. Current state: {workflow.state}"
        )
    
    try:
        # Log human decision
        from database.utils import log_human_decision, save_decision
        from models import Decision
        log_human_decision(
            db=db,
            workflow_id=workflow_id,
            decision_type="clarification",
            user_id=request.user_id,
            decision_data={
                "clarifications": request.clarifications,
                "clarifications_count": len(request.clarifications)
            },
            reasoning=request.reasoning
        )

        # Save decision to decisions table for conflict resolution recording
        decision = Decision(
            decision_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            decision_type="clarification",
            user_id=request.user_id,
            timestamp=datetime.utcnow(),
            reasoning=request.reasoning,
            modifications={"clarifications": request.clarifications}
        )
        save_decision(db, decision)
        
        # Store clarifications in workflow metadata
        if not workflow.workflow_metadata:
            workflow.workflow_metadata = {}
        
        workflow.workflow_metadata["clarifications"] = request.clarifications
        workflow.workflow_metadata["clarified_by"] = request.user_id
        workflow.workflow_metadata["clarified_at"] = datetime.utcnow().isoformat()
        
        # Update workflow state to trigger re-reasoning
        workflow.state = WorkflowState.REDACTED.value  # Go back to redacted to re-run reasoning
        workflow.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(workflow)
        
        return {
            "workflow_id": workflow_id,
            "status": "clarification_received",
            "message": "Clarifications stored. Re-run reasoning to incorporate clarifications.",
            "clarifications_count": len(request.clarifications),
            "next_action": "POST /api/v1/workflows/{workflow_id}/reason"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clarification failed: {str(e)}")


class ApprovalRequest(BaseModel):
    """Request body for approving recommendations."""
    user_id: str
    approved_recommendations: List[str]  # List of recommendation IDs
    modifications: Optional[dict] = None  # Optional modifications to recommendations
    reasoning: Optional[str] = None


@router.post("/{workflow_id}/approve")
async def approve_recommendations(
    workflow_id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve recommendations for execution.
    
    This endpoint allows users to approve AI-generated recommendations
    after reviewing them.
    
    Args:
        workflow_id: Workflow identifier
        request: Approval data
        db: Database session
        
    Returns:
        Approval confirmation
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Verify workflow is in correct state
    valid_states = [
        WorkflowState.READY_FOR_REVIEW.value,
        WorkflowState.POLICY_REVIEW_REQUIRED.value,
        WorkflowState.DRAFT_READY.value
    ]
    if workflow.state not in valid_states:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not in a reviewable state. Current state: {workflow.state}"
        )
    
    try:
        # Log human decision
        from database.utils import log_human_decision, save_decision
        from models import Decision
        
        log_human_decision(
            db=db,
            workflow_id=workflow_id,
            decision_type="approval",
            user_id=request.user_id,
            decision_data={
                "approved_recommendations": request.approved_recommendations,
                "approved_count": len(request.approved_recommendations),
                "modifications": request.modifications or {}
            },
            reasoning=request.reasoning
        )
        
        # Save decision to decisions table
        decision = Decision(
            decision_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            decision_type="approval",
            user_id=request.user_id,
            timestamp=datetime.utcnow(),
            reasoning=request.reasoning,
            modifications=request.modifications or {}
        )
        save_decision(db, decision)
        
        # Update workflow state
        workflow.state = WorkflowState.APPROVED.value
        workflow.updated_at = datetime.utcnow()
        
        # Store approval in metadata
        if not workflow.workflow_metadata:
            workflow.workflow_metadata = {}
        
        workflow.workflow_metadata["approved_recommendations"] = request.approved_recommendations
        workflow.workflow_metadata["approved_by"] = request.user_id
        workflow.workflow_metadata["approved_at"] = datetime.utcnow().isoformat()
        
        db.commit()
        db.refresh(workflow)
        
        return {
            "workflow_id": workflow_id,
            "status": "approved",
            "message": f"Approved {len(request.approved_recommendations)} recommendations",
            "approved_count": len(request.approved_recommendations),
            "next_state": WorkflowState.APPROVED.value,
            "next_action": "Recommendations will be executed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


class RejectionRequest(BaseModel):
    """Request body for rejecting recommendations."""
    user_id: str
    rejected_recommendations: List[str]  # List of recommendation IDs
    rejection_reasons: dict  # Map of recommendation_id -> reason
    reasoning: Optional[str] = None


@router.post("/{workflow_id}/reject")
async def reject_recommendations(
    workflow_id: str,
    request: RejectionRequest,
    db: Session = Depends(get_db)
):
    """
    Reject recommendations.
    
    This endpoint allows users to reject AI-generated recommendations
    and provide reasons for rejection.
    
    Args:
        workflow_id: Workflow identifier
        request: Rejection data
        db: Database session
        
    Returns:
        Rejection confirmation
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    # Verify workflow is in correct state
    valid_states = [
        WorkflowState.READY_FOR_REVIEW.value,
        WorkflowState.POLICY_REVIEW_REQUIRED.value,
        WorkflowState.DRAFT_READY.value
    ]
    if workflow.state not in valid_states:
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not in a reviewable state. Current state: {workflow.state}"
        )
    
    try:
        # Log human decision
        from database.utils import log_human_decision, save_decision
        from models import Decision
        
        log_human_decision(
            db=db,
            workflow_id=workflow_id,
            decision_type="rejection",
            user_id=request.user_id,
            decision_data={
                "rejected_recommendations": request.rejected_recommendations,
                "rejected_count": len(request.rejected_recommendations),
                "rejection_reasons": request.rejection_reasons
            },
            reasoning=request.reasoning
        )
        
        # Save decision to decisions table
        decision = Decision(
            decision_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            decision_type="rejection",
            user_id=request.user_id,
            timestamp=datetime.utcnow(),
            reasoning=request.reasoning,
            modifications={"rejection_reasons": request.rejection_reasons}
        )
        save_decision(db, decision)
        
        # Update workflow state back to review
        workflow.state = WorkflowState.READY_FOR_REVIEW.value
        workflow.updated_at = datetime.utcnow()
        
        # Store rejection in metadata
        if not workflow.workflow_metadata:
            workflow.workflow_metadata = {}
        
        workflow.workflow_metadata["rejected_recommendations"] = request.rejected_recommendations
        workflow.workflow_metadata["rejected_by"] = request.user_id
        workflow.workflow_metadata["rejected_at"] = datetime.utcnow().isoformat()
        workflow.workflow_metadata["rejection_reasons"] = request.rejection_reasons
        
        db.commit()
        db.refresh(workflow)
        
        return {
            "workflow_id": workflow_id,
            "status": "rejected",
            "message": f"Rejected {len(request.rejected_recommendations)} recommendations",
            "rejected_count": len(request.rejected_recommendations),
            "next_state": WorkflowState.READY_FOR_REVIEW.value,
            "next_action": "Review and modify recommendations, then re-submit for approval"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")


# ============================================================================
# Audit and Monitoring Endpoints
# ============================================================================

@router.get("/{workflow_id}/audit")
async def get_audit_trail(
    workflow_id: str,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    actor: Optional[str] = Query(None, description="Filter by actor"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of entries"),
    db: Session = Depends(get_db)
):
    """
    Get complete audit trail for a workflow.
    
    This endpoint provides the immutable audit log showing all actions
    taken on the workflow for compliance and debugging.
    
    Args:
        workflow_id: Workflow identifier
        action_type: Optional filter by action type
        actor: Optional filter by actor
        limit: Maximum number of entries to return
        db: Database session
        
    Returns:
        List of audit log entries
    """
    # Verify workflow exists
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    try:
        from database.utils import get_audit_trail as get_audit_entries
        from database.models import AuditLogDB
        
        # Get all audit entries for workflow
        query = db.query(AuditLogDB).filter(AuditLogDB.workflow_id == workflow_id)
        
        # Apply filters
        if action_type:
            query = query.filter(AuditLogDB.action_type == action_type)
        if actor:
            query = query.filter(AuditLogDB.actor == actor)
        
        # Order by timestamp and limit
        audit_entries = query.order_by(AuditLogDB.timestamp.asc()).limit(limit).all()
        
        return {
            "workflow_id": workflow_id,
            "total_entries": len(audit_entries),
            "entries": [
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "action_type": entry.action_type,
                    "actor": entry.actor,
                    "details": entry.details,
                    "hash": entry.hash
                }
                for entry in audit_entries
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit trail: {str(e)}")


@router.get("/dashboard/stats", include_in_schema=False)
async def get_dashboard_statistics_deprecated(
    db: Session = Depends(get_db)
):
    """
    DEPRECATED: Use /api/v1/dashboard/stats instead.
    
    Get dashboard statistics for monitoring.
    
    This endpoint provides aggregate statistics about workflows
    for the monitoring dashboard.
    
    Returns:
        Dashboard statistics
    """
    try:
        from database.models import WorkflowDB
        from sqlalchemy import func
        
        # Count workflows by state
        state_counts = (
            db.query(WorkflowDB.state, func.count(WorkflowDB.workflow_id))
            .group_by(WorkflowDB.state)
            .all()
        )
        
        workflows_by_state = {state: count for state, count in state_counts}
        
        # Count total workflows
        total_workflows = db.query(func.count(WorkflowDB.workflow_id)).scalar()
        
        # Count workflows requiring attention (human input needed)
        attention_states = [
            WorkflowState.NEEDS_CLARIFICATION.value,
            WorkflowState.POLICY_REVIEW_REQUIRED.value,
            WorkflowState.READY_FOR_REVIEW.value,
            WorkflowState.DRAFT_READY.value,
            WorkflowState.ESCALATED.value
        ]
        
        workflows_needing_attention = (
            db.query(func.count(WorkflowDB.workflow_id))
            .filter(WorkflowDB.state.in_(attention_states))
            .scalar()
        )
        
        # Get recent workflows (last 10)
        recent_workflows = (
            db.query(WorkflowDB)
            .order_by(WorkflowDB.created_at.desc())
            .limit(10)
            .all()
        )
        
        # Count workflows by creator
        creator_counts = (
            db.query(WorkflowDB.created_by, func.count(WorkflowDB.workflow_id))
            .group_by(WorkflowDB.created_by)
            .all()
        )
        
        workflows_by_creator = {creator: count for creator, count in creator_counts}
        
        # Calculate completion rate
        completed_count = workflows_by_state.get(WorkflowState.COMPLETED.value, 0)
        completion_rate = (completed_count / total_workflows * 100) if total_workflows > 0 else 0
        
        # Calculate failure rate
        failed_count = workflows_by_state.get(WorkflowState.FAILED.value, 0)
        failure_rate = (failed_count / total_workflows * 100) if total_workflows > 0 else 0
        
        return {
            "total_workflows": total_workflows,
            "workflows_by_state": workflows_by_state,
            "workflows_needing_attention": workflows_needing_attention,
            "completion_rate": round(completion_rate, 2),
            "failure_rate": round(failure_rate, 2),
            "workflows_by_creator": workflows_by_creator,
            "recent_workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "state": w.state,
                    "created_at": w.created_at.isoformat(),
                    "created_by": w.created_by
                }
                for w in recent_workflows
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard statistics: {str(e)}")


# ============================================================================
# T&C Comparison Endpoint
# ============================================================================

class TCCompareRequest(BaseModel):
    """Request body for T&C comparison."""
    workflow_id_a: str
    workflow_id_b: str


@router.post("/tc-compare")
async def compare_tc_documents(
    request: TCCompareRequest,
    db: Session = Depends(get_db)
):
    """
    Compare two T&C documents clause by clause.

    Extracts clauses from both documents and performs AI-powered
    semantic comparison with color-coded classification.

    Args:
        request: Two workflow IDs to compare
        db: Database session

    Returns:
        Clause comparison results with classifications
    """
    from components.tc_comparison import extract_clauses, compare_clauses

    # Get both workflows
    wf_a = get_workflow(db, request.workflow_id_a)
    wf_b = get_workflow(db, request.workflow_id_b)

    if not wf_a:
        raise HTTPException(status_code=404, detail=f"Workflow {request.workflow_id_a} not found")
    if not wf_b:
        raise HTTPException(status_code=404, detail=f"Workflow {request.workflow_id_b} not found")

    # Ensure both have document text
    text_a = wf_a.document_text or wf_a.redacted_text
    text_b = wf_b.document_text or wf_b.redacted_text

    if not text_a:
        raise HTTPException(status_code=400, detail=f"Workflow {request.workflow_id_a} has no document text")
    if not text_b:
        raise HTTPException(status_code=400, detail=f"Workflow {request.workflow_id_b} has no document text")

    try:
        # Extract clauses
        clauses_a = extract_clauses(text_a)
        clauses_b = extract_clauses(text_b)

        # Compare clauses
        comparisons = await compare_clauses(clauses_a, clauses_b)

        return {
            "workflow_a": {
                "workflow_id": request.workflow_id_a,
                "clause_count": len(clauses_a),
                "clauses": clauses_a,
            },
            "workflow_b": {
                "workflow_id": request.workflow_id_b,
                "clause_count": len(clauses_b),
                "clauses": clauses_b,
            },
            "comparisons": comparisons,
            "total_comparisons": len(comparisons),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"T&C comparison failed: {str(e)}")
