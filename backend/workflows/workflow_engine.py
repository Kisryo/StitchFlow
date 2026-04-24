"""
LangGraph Workflow Engine.

Orchestrates the complete workflow from document ingestion to completion
using LangGraph's state machine capabilities.
"""
from typing import Optional, List
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from models import WorkflowState
from database.utils import get_workflow, log_audit_entry
from components.ingestion import ingest_document
from components.redaction import redact_workflow_document
from components.reasoning import run_reasoning_chain
from components.policy_screening import screen_policy


# Simple dict-based state (avoid TypedDict issues)
def create_initial_state(workflow_id: str, document_path: str, file_type: str) -> dict:
    """Create initial workflow state."""
    return {
        "workflow_id": workflow_id,
        "current_state": WorkflowState.NEW.value,
        "document_path": document_path,
        "file_type": file_type,
        "error": None,
        "requires_human_input": False,
        "human_input_type": None,
        "messages": []
    }


def validate_state_transition(
    current_state: WorkflowState,
    next_state: WorkflowState
) -> bool:
    """
    Validate if a state transition is allowed.
    
    Args:
        current_state: Current workflow state
        next_state: Desired next state
        
    Returns:
        True if transition is valid, False otherwise
    """
    from models.workflow import VALID_TRANSITIONS
    return next_state in VALID_TRANSITIONS.get(current_state, [])


# ============================================================================
# Workflow Node Functions
# ============================================================================

async def ingest_node(state: dict, db: Session) -> dict:
    """
    Node: Ingest document and extract text.
    
    Transitions: New → Ingested (or Failed)
    """
    workflow_id = state["workflow_id"]
    document_path = state["document_path"]
    file_type = state["file_type"]
    
    try:
        print(f"[Workflow Engine] Ingesting document: {document_path}")
        
        # Run ingestion
        result = await ingest_document(
            workflow_id=workflow_id,
            file_path=document_path,
            file_type=file_type,
            db=db
        )
        
        if result.success:
            state["current_state"] = WorkflowState.INGESTED.value
            state["messages"].append(f"✅ Document ingested successfully")
            
            # Log state transition
            log_audit_entry(
                db=db,
                workflow_id=workflow_id,
                action_type="state_transition",
                actor="workflow_engine",
                details={
                    "from_state": "New",
                    "to_state": WorkflowState.INGESTED.value,
                    "reason": "Document ingestion successful",
                    "file_type": file_type,
                    "file_size": result.file_size
                }
            )
        else:
            state["current_state"] = WorkflowState.FAILED.value
            state["error"] = result.error
            state["messages"].append(f"❌ Ingestion failed: {result.error}")
            
            # Log failure
            log_audit_entry(
                db=db,
                workflow_id=workflow_id,
                action_type="state_transition",
                actor="workflow_engine",
                details={
                    "from_state": "New",
                    "to_state": WorkflowState.FAILED.value,
                    "reason": f"Ingestion failed: {result.error}"
                }
            )
        
        return state
        
    except Exception as e:
        state["current_state"] = WorkflowState.FAILED.value
        state["error"] = str(e)
        state["messages"].append(f"❌ Ingestion error: {str(e)}")
        
        # Log exception
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="state_transition",
            actor="workflow_engine",
            details={
                "from_state": "New",
                "to_state": WorkflowState.FAILED.value,
                "reason": f"Ingestion exception: {str(e)}"
            }
        )
        
        return state


async def redact_node(state: dict, db: Session) -> dict:
    """
    Node: Redact PII from document.
    
    Transitions: Ingested → Redacted (or Failed)
    """
    workflow_id = state["workflow_id"]
    
    try:
        print(f"[Workflow Engine] Redacting PII...")
        
        # Run redaction
        result = await redact_workflow_document(workflow_id, db)
        
        state["current_state"] = WorkflowState.REDACTED.value
        state["messages"].append(f"✅ PII redacted: {len(result.pii_matches)} instances found")
        
        # Log state transition
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="state_transition",
            actor="workflow_engine",
            details={
                "from_state": "Ingested",
                "to_state": WorkflowState.REDACTED.value,
                "reason": "PII redaction successful",
                "pii_instances_found": len(result.pii_matches),
                "redaction_time": result.redaction_time
            }
        )
        
        return state
        
    except Exception as e:
        state["current_state"] = WorkflowState.FAILED.value
        state["error"] = str(e)
        state["messages"].append(f"❌ Redaction error: {str(e)}")
        
        # Log failure
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="state_transition",
            actor="workflow_engine",
            details={
                "from_state": "Ingested",
                "to_state": WorkflowState.FAILED.value,
                "reason": f"Redaction failed: {str(e)}"
            }
        )
        
        return state


async def reason_node(state: dict, db: Session) -> dict:
    """
    Node: Run GLM reasoning chain.
    
    Transitions: Redacted → Parsed/NeedsClarification (or Failed)
    """
    workflow_id = state["workflow_id"]
    
    try:
        print(f"[Workflow Engine] Running AI reasoning...")
        
        # Run reasoning
        result = await run_reasoning_chain(workflow_id, db)
        
        # Check if clarification needed
        if result.ambiguities:
            state["current_state"] = WorkflowState.NEEDS_CLARIFICATION.value
            state["requires_human_input"] = True
            state["human_input_type"] = "clarification"
            state["messages"].append(f"⚠️  Clarification needed: {len(result.ambiguities)} ambiguities found")
        else:
            state["current_state"] = WorkflowState.PARSED.value
            state["messages"].append(f"✅ Reasoning complete: {len(result.recommendations)} recommendations")
        
        return state
        
    except Exception as e:
        state["current_state"] = WorkflowState.FAILED.value
        state["error"] = str(e)
        state["messages"].append(f"❌ Reasoning error: {str(e)}")
        return state


async def screen_policy_node(state: dict, db: Session) -> dict:
    """
    Node: Screen recommendations against policy rules.
    
    Transitions: Parsed → PolicyReviewRequired/ReadyForReview (or Failed)
    """
    workflow_id = state["workflow_id"]
    
    try:
        print(f"[Workflow Engine] Screening policy violations...")
        
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
            raise ValueError("No reasoning results found")
        
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
        
        # Run policy screening
        result = await screen_policy(workflow_id, reasoning_result, db)
        
        # Check if human review required
        if result.requires_human_review:
            state["current_state"] = WorkflowState.POLICY_REVIEW_REQUIRED.value
            state["requires_human_input"] = True
            state["human_input_type"] = "policy_review"
            state["messages"].append(f"⚠️  Policy review required: {len(result.violations)} violations (risk: {result.risk_score})")
        else:
            state["current_state"] = WorkflowState.READY_FOR_REVIEW.value
            state["messages"].append(f"✅ Policy screening passed: risk score {result.risk_score}")
        
        return state
        
    except Exception as e:
        state["current_state"] = WorkflowState.FAILED.value
        state["error"] = str(e)
        state["messages"].append(f"❌ Policy screening error: {str(e)}")
        return state


async def wait_for_human_node(state: dict, db: Session) -> dict:
    """
    Node: Wait for human input (interrupt point).
    
    This node pauses the workflow until human provides input.
    """
    workflow_id = state["workflow_id"]
    input_type = state.get("human_input_type", "unknown")
    
    print(f"[Workflow Engine] Waiting for human input: {input_type}")
    
    state["messages"].append(f"⏸️  Workflow paused: waiting for {input_type}")
    
    # Log audit entry
    log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="workflow_paused",
        actor="system",
        details={
            "reason": f"Waiting for human {input_type}",
            "current_state": state["current_state"]
        }
    )
    
    return state


# ============================================================================
# Conditional Routing Functions
# ============================================================================

def should_continue_after_reason(state: dict) -> str:
    """
    Decide next step after reasoning.
    
    If clarification needed → wait for human
    Otherwise → proceed to policy screening
    """
    if state.get("requires_human_input") and state.get("human_input_type") == "clarification":
        return "wait_for_human"
    return "screen_policy"


def should_continue_after_policy(state: dict) -> str:
    """
    Decide next step after policy screening.
    
    If review required → wait for human
    Otherwise → end (for now, until we implement task execution)
    """
    if state.get("requires_human_input") and state.get("human_input_type") == "policy_review":
        return "wait_for_human"
    return "end"


def check_for_failure(state: dict) -> str:
    """
    Check if workflow has failed.
    """
    if state["current_state"] == WorkflowState.FAILED.value:
        return "failed"
    return "continue"


# ============================================================================
# Build Workflow Graph
# ============================================================================

def create_workflow_graph(db: Session) -> StateGraph:
    """
    Create the LangGraph workflow state machine.
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create graph with simple dict state
    workflow = StateGraph(dict)
    
    # Add nodes - wrap async functions properly
    async def ingest_wrapper(state):
        return await ingest_node(state, db)
    
    async def redact_wrapper(state):
        return await redact_node(state, db)
    
    async def reason_wrapper(state):
        return await reason_node(state, db)
    
    async def screen_policy_wrapper(state):
        return await screen_policy_node(state, db)
    
    async def wait_for_human_wrapper(state):
        return await wait_for_human_node(state, db)
    
    workflow.add_node("ingest", ingest_wrapper)
    workflow.add_node("redact", redact_wrapper)
    workflow.add_node("reason", reason_wrapper)
    workflow.add_node("screen_policy", screen_policy_wrapper)
    workflow.add_node("wait_for_human", wait_for_human_wrapper)
    
    # Set entry point
    workflow.set_entry_point("ingest")
    
    # Add edges (transitions)
    workflow.add_edge("ingest", "redact")
    workflow.add_edge("redact", "reason")
    
    # Conditional routing after reasoning
    workflow.add_conditional_edges(
        "reason",
        should_continue_after_reason,
        {
            "screen_policy": "screen_policy",
            "wait_for_human": "wait_for_human"
        }
    )
    
    # Conditional routing after policy screening
    workflow.add_conditional_edges(
        "screen_policy",
        should_continue_after_policy,
        {
            "wait_for_human": "wait_for_human",
            "end": END
        }
    )
    
    # Human input node ends workflow (will be resumed later)
    workflow.add_edge("wait_for_human", END)
    
    # Compile graph
    return workflow.compile()


# ============================================================================
# Workflow Execution
# ============================================================================

async def run_workflow(
    workflow_id: str,
    document_path: str,
    file_type: str,
    db: Session
) -> dict:
    """
    Execute the complete workflow for a document.
    
    Args:
        workflow_id: Workflow identifier
        document_path: Path to uploaded document
        file_type: File type (pdf, docx, txt, email)
        db: Database session
        
    Returns:
        Final workflow state
    """
    print(f"[Workflow Engine] Starting workflow: {workflow_id}")
    
    # Initialize state (using plain dict to avoid TypedDict issues)
    initial_state = create_initial_state(workflow_id, document_path, file_type)
    
    # Create and run workflow graph
    graph = create_workflow_graph(db)
    
    try:
        # Execute workflow
        final_state = await graph.ainvoke(initial_state)
        
        print(f"[Workflow Engine] Workflow complete: {final_state['current_state']}")
        
        # Log completion
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="workflow_completed",
            actor="system",
            details={
                "final_state": final_state["current_state"],
                "requires_human_input": final_state.get("requires_human_input", False),
                "messages": final_state.get("messages", [])
            }
        )
        
        return {
            "workflow_id": workflow_id,
            "final_state": final_state["current_state"],
            "requires_human_input": final_state.get("requires_human_input", False),
            "human_input_type": final_state.get("human_input_type"),
            "error": final_state.get("error"),
            "messages": final_state.get("messages", [])
        }
        
    except Exception as e:
        print(f"[Workflow Engine] Workflow failed: {str(e)}")
        
        # Update workflow to failed state
        workflow = get_workflow(db, workflow_id)
        if workflow:
            workflow.state = WorkflowState.FAILED.value
            db.commit()
        
        # Log failure
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="workflow_failed",
            actor="system",
            details={
                "error": str(e),
                "messages": initial_state.get("messages", [])
            }
        )
        
        raise Exception(f"Workflow execution failed: {str(e)}")


async def resume_workflow(
    workflow_id: str,
    human_input: dict,
    db: Session
) -> dict:
    """
    Resume a paused workflow after human input.
    
    Args:
        workflow_id: Workflow identifier
        human_input: Human input data (clarifications, approvals, etc.)
        db: Database session
        
    Returns:
        Updated workflow state
    """
    print(f"[Workflow Engine] Resuming workflow: {workflow_id}")
    
    # Get current workflow state
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")
    
    # Log human input
    log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="human_input_received",
        actor=human_input.get("user_id", "unknown"),
        details={
            "input_type": human_input.get("type"),
            "data": human_input.get("data")
        }
    )
    
    # TODO: Implement workflow resumption logic
    # This will be expanded in future phases
    
    return {
        "workflow_id": workflow_id,
        "status": "resumed",
        "message": "Workflow resumption not fully implemented yet"
    }
