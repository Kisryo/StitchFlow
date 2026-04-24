"""
Database utility functions.

Helper functions for common database operations.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib
import json

from .models import (
    WorkflowDB,
    ReasoningResultDB,
    PolicyScreeningResultDB,
    DecisionDB,
    AuditLogDB,
    PolicyRuleDB
)
from models import (
    Workflow,
    WorkflowState,
    ReasoningResult,
    PolicyScreeningResult,
    Decision,
    AuditEntry,
    PolicyRule
)


def create_workflow(db: Session, workflow: Workflow) -> WorkflowDB:
    """
    Create a new workflow in the database.
    
    Args:
        db: Database session
        workflow: Workflow Pydantic model
        
    Returns:
        Created WorkflowDB instance
    """
    db_workflow = WorkflowDB(
        workflow_id=workflow.workflow_id,
        state=workflow.state.value,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        created_by=workflow.created_by,
        document_path=workflow.document_path,
        document_text=workflow.document_text,
        redacted_text=workflow.redacted_text,
        token_map=workflow.token_map,
        workflow_metadata=workflow.metadata  # Map Pydantic 'metadata' to SQLAlchemy 'workflow_metadata'
    )
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow


def get_workflow(db: Session, workflow_id: str) -> Optional[WorkflowDB]:
    """
    Get workflow by ID.
    
    Args:
        db: Database session
        workflow_id: Workflow identifier
        
    Returns:
        WorkflowDB instance or None if not found
    """
    return db.query(WorkflowDB).filter(WorkflowDB.workflow_id == workflow_id).first()


def update_workflow_state(
    db: Session,
    workflow_id: str,
    new_state: WorkflowState,
    reason: str,
    actor: str = "system"
) -> WorkflowDB:
    """
    Update workflow state and log the transition.
    
    Args:
        db: Database session
        workflow_id: Workflow identifier
        new_state: New workflow state
        reason: Reason for state change
        actor: Who/what triggered the change
        
    Returns:
        Updated WorkflowDB instance
    """
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")
    
    old_state = workflow.state
    workflow.state = new_state.value
    workflow.updated_at = datetime.utcnow()
    
    # Log the state transition
    log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="state_transition",
        actor=actor,
        details={
            "from_state": old_state,
            "to_state": new_state.value,
            "reason": reason
        }
    )
    
    db.commit()
    db.refresh(workflow)
    return workflow


def list_workflows(
    db: Session,
    state: Optional[WorkflowState] = None,
    created_by: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[WorkflowDB]:
    """
    List workflows with optional filtering.
    
    Args:
        db: Database session
        state: Filter by workflow state
        created_by: Filter by creator
        limit: Maximum number of results
        offset: Offset for pagination
        
    Returns:
        List of WorkflowDB instances
    """
    query = db.query(WorkflowDB)
    
    if state:
        query = query.filter(WorkflowDB.state == state.value)
    if created_by:
        query = query.filter(WorkflowDB.created_by == created_by)
    
    return query.order_by(WorkflowDB.created_at.desc()).limit(limit).offset(offset).all()


def save_reasoning_result(db: Session, result: ReasoningResult) -> ReasoningResultDB:
    """
    Save GLM reasoning result to database.
    
    Args:
        db: Database session
        result: ReasoningResult Pydantic model
        
    Returns:
        Created ReasoningResultDB instance
    """
    db_result = ReasoningResultDB(
        workflow_id=result.workflow_id,
        classification=result.classification.model_dump(),
        entities=[e.model_dump() for e in result.entities],
        ambiguities=[a.model_dump() for a in result.ambiguities],
        conflicts=[c.model_dump() for c in result.conflicts],
        recommendations=[r.model_dump() for r in result.recommendations],
        reasoning_time=result.reasoning_time
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def save_policy_screening_result(
    db: Session,
    result: PolicyScreeningResult
) -> PolicyScreeningResultDB:
    """
    Save policy screening result to database.
    
    Args:
        db: Database session
        result: PolicyScreeningResult Pydantic model
        
    Returns:
        Created PolicyScreeningResultDB instance
    """
    db_result = PolicyScreeningResultDB(
        workflow_id=result.workflow_id,
        violations=[v.model_dump() for v in result.violations],
        risk_score=result.risk_score,
        requires_human_review=result.requires_human_review,
        screening_time=result.screening_time
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


def save_decision(db: Session, decision: Decision) -> DecisionDB:
    """
    Save human decision to database.
    
    Args:
        db: Database session
        decision: Decision Pydantic model
        
    Returns:
        Created DecisionDB instance
    """
    db_decision = DecisionDB(
        decision_id=decision.decision_id,
        workflow_id=decision.workflow_id,
        decision_type=decision.decision_type,
        user_id=decision.user_id,
        timestamp=decision.timestamp,
        reasoning=decision.reasoning,
        modifications=decision.modifications
    )
    db.add(db_decision)
    db.commit()
    db.refresh(db_decision)
    return db_decision


def log_audit_entry(
    db: Session,
    workflow_id: str,
    action_type: str,
    actor: str,
    details: Dict[str, Any]
) -> AuditLogDB:
    """
    Create immutable audit log entry.
    
    Args:
        db: Database session
        workflow_id: Associated workflow ID
        action_type: Type of action
        actor: Who/what performed the action
        details: Action details
        
    Returns:
        Created AuditLogDB instance
    """
    # Generate hash for tamper detection
    entry_data = {
        "workflow_id": workflow_id,
        "timestamp": datetime.utcnow().isoformat(),
        "action_type": action_type,
        "actor": actor,
        "details": details
    }
    entry_hash = hashlib.sha256(json.dumps(entry_data, sort_keys=True).encode()).hexdigest()
    
    db_entry = AuditLogDB(
        workflow_id=workflow_id,
        action_type=action_type,
        actor=actor,
        details=details,
        hash=entry_hash
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


def log_glm_decision(
    db: Session,
    workflow_id: str,
    decision_type: str,
    input_text: str,
    output_data: Dict[str, Any],
    confidence_score: Optional[float] = None,
    reasoning_time: Optional[float] = None
) -> AuditLogDB:
    """
    Log GLM decision with input, output, and confidence score.
    
    This specialized function logs AI decisions for audit trail compliance.
    
    Args:
        db: Database session
        workflow_id: Associated workflow ID
        decision_type: Type of GLM decision (classification, extraction, recommendation, etc.)
        input_text: Input text sent to GLM (redacted)
        output_data: Structured output from GLM
        confidence_score: Confidence score (0-1) if applicable
        reasoning_time: Time taken for reasoning in seconds
        
    Returns:
        Created AuditLogDB instance
    """
    details = {
        "decision_type": decision_type,
        "input_length": len(input_text),
        "input_preview": input_text[:200] + "..." if len(input_text) > 200 else input_text,
        "output_data": output_data,
        "confidence_score": confidence_score,
        "reasoning_time": reasoning_time,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type=f"glm_decision_{decision_type}",
        actor="glm_agent",
        details=details
    )


def log_human_decision(
    db: Session,
    workflow_id: str,
    decision_type: str,
    user_id: str,
    decision_data: Dict[str, Any],
    reasoning: Optional[str] = None
) -> AuditLogDB:
    """
    Log human decision with reasoning.
    
    This specialized function logs human decisions for audit trail compliance.
    
    Args:
        db: Database session
        workflow_id: Associated workflow ID
        decision_type: Type of decision (approve, reject, clarify, modify, etc.)
        user_id: User who made the decision
        decision_data: Decision details (what was approved/rejected/modified)
        reasoning: User's reasoning for the decision
        
    Returns:
        Created AuditLogDB instance
    """
    details = {
        "decision_type": decision_type,
        "decision_data": decision_data,
        "reasoning": reasoning,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type=f"human_decision_{decision_type}",
        actor=user_id,
        details=details
    )


def log_policy_screening(
    db: Session,
    workflow_id: str,
    rules_evaluated: List[str],
    violations_found: List[Dict[str, Any]],
    risk_score: float,
    requires_review: bool,
    screening_time: Optional[float] = None
) -> AuditLogDB:
    """
    Log policy screening results.
    
    This specialized function logs policy screening for audit trail compliance.
    
    Args:
        db: Database session
        workflow_id: Associated workflow ID
        rules_evaluated: List of policy rule IDs evaluated
        violations_found: List of violations detected
        risk_score: Calculated risk score
        requires_review: Whether human review is required
        screening_time: Time taken for screening in seconds
        
    Returns:
        Created AuditLogDB instance
    """
    details = {
        "rules_evaluated": rules_evaluated,
        "rules_count": len(rules_evaluated),
        "violations_found": violations_found,
        "violations_count": len(violations_found),
        "risk_score": risk_score,
        "requires_review": requires_review,
        "screening_time": screening_time,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="policy_screening",
        actor="policy_screener",
        details=details
    )


def get_audit_trail(db: Session, workflow_id: str) -> List[AuditLogDB]:
    """
    Get complete audit trail for a workflow.
    
    Args:
        db: Database session
        workflow_id: Workflow identifier
        
    Returns:
        List of AuditLogDB entries ordered by timestamp
    """
    return (
        db.query(AuditLogDB)
        .filter(AuditLogDB.workflow_id == workflow_id)
        .order_by(AuditLogDB.timestamp.asc())
        .all()
    )


def get_policy_rules(
    db: Session,
    category: Optional[str] = None,
    severity: Optional[str] = None
) -> List[PolicyRuleDB]:
    """
    Get policy rules with optional filtering.
    
    Args:
        db: Database session
        category: Filter by category
        severity: Filter by severity
        
    Returns:
        List of PolicyRuleDB instances
    """
    query = db.query(PolicyRuleDB)
    
    if category:
        query = query.filter(PolicyRuleDB.category == category)
    if severity:
        query = query.filter(PolicyRuleDB.severity == severity)
    
    return query.all()


def create_policy_rule(db: Session, rule: PolicyRule) -> PolicyRuleDB:
    """
    Create a new policy rule.
    
    Args:
        db: Database session
        rule: PolicyRule Pydantic model
        
    Returns:
        Created PolicyRuleDB instance
    """
    db_rule = PolicyRuleDB(
        rule_id=rule.rule_id,
        category=rule.category,
        name=rule.name,
        description=rule.description,
        keywords=rule.keywords,
        conditions=rule.conditions,
        severity=rule.severity,
        requires_review=rule.requires_review
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule
