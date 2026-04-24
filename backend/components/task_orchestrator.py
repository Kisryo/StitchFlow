"""
Task Orchestrator Component.

Executes approved recommendations with retry logic, dependency resolution,
and error handling.
"""
import time
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from models import (
    Recommendation,
    TaskResult,
    OrchestrationResult,
    WorkflowState
)
from database.utils import get_workflow, log_audit_entry
from components.google_sheets import sync_to_sheets
from components.gmail import create_gmail_draft, approve_and_send_draft
from config.settings import settings


# Task type constants
TASK_TYPE_SYNC_SHEETS = "sync_sheets"
TASK_TYPE_CREATE_DRAFT = "create_draft"
TASK_TYPE_SEND_EMAIL = "send_email"
TASK_TYPE_NOTIFY_USER = "notify_user"


async def execute_with_retry(
    task_func,
    task_args: Dict[str, Any],
    max_retries: int = None,
    initial_delay: float = None,
    backoff_factor: float = None
) -> Dict[str, Any]:
    """
    Execute a task with exponential backoff retry logic.
    
    Args:
        task_func: Async function to execute
        task_args: Arguments to pass to the function
        max_retries: Maximum number of retry attempts (default from settings)
        initial_delay: Initial delay in seconds (default from settings)
        backoff_factor: Backoff multiplier (default from settings)
        
    Returns:
        Task execution result
        
    Raises:
        RetryError: If all retries are exhausted
    """
    max_retries = max_retries or settings.max_retries
    initial_delay = initial_delay or settings.retry_initial_delay
    backoff_factor = backoff_factor or settings.retry_backoff_factor
    
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=initial_delay, max=60),
        reraise=True
    )
    async def _execute():
        return await task_func(**task_args)
    
    try:
        result = await _execute()
        return result
    except RetryError as e:
        # All retries exhausted
        raise Exception(f"Task failed after {max_retries} retries: {str(e)}")


async def execute_sync_sheets_task(
    workflow_id: str,
    recommendation: Recommendation,
    db: Session
) -> TaskResult:
    """
    Execute Google Sheets sync task.
    
    Args:
        workflow_id: Workflow identifier
        recommendation: Recommendation with sync parameters
        db: Database session
        
    Returns:
        TaskResult with execution outcome
    """
    start_time = time.time()
    
    try:
        # Extract parameters from recommendation
        params = recommendation.parameters
        entities = params.get("entities", [])
        recommendations_data = params.get("recommendations", [])
        spreadsheet_id = params.get("spreadsheet_id")
        
        # Get workflow for context
        workflow = get_workflow(db, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Get reasoning result from database
        from database.models import ReasoningResultDB
        from models import Entity, Recommendation as RecModel
        
        db_reasoning = (
            db.query(ReasoningResultDB)
            .filter(ReasoningResultDB.workflow_id == workflow_id)
            .order_by(ReasoningResultDB.created_at.desc())
            .first()
        )
        
        if not db_reasoning:
            raise ValueError("No reasoning results found for workflow")
        
        # Convert to Pydantic models
        entities_list = [Entity(**e) for e in db_reasoning.entities]
        recommendations_list = [RecModel(**r) for r in db_reasoning.recommendations]
        
        # Execute sync with retry
        result = await execute_with_retry(
            sync_to_sheets,
            {
                "workflow_id": workflow_id,
                "entities": entities_list,
                "recommendations": recommendations_list,
                "spreadsheet_id": spreadsheet_id
            }
        )
        
        execution_time = time.time() - start_time
        
        if result.get("success"):
            return TaskResult(
                task_id=recommendation.recommendation_id,
                task_type=TASK_TYPE_SYNC_SHEETS,
                success=True,
                result_data={
                    "spreadsheet_id": result.get("spreadsheet_id"),
                    "spreadsheet_url": result.get("spreadsheet_url"),
                    "entities_synced": result.get("entities_synced"),
                    "recommendations_synced": result.get("recommendations_synced")
                },
                error=None,
                execution_time=execution_time,
                retry_count=0
            )
        else:
            return TaskResult(
                task_id=recommendation.recommendation_id,
                task_type=TASK_TYPE_SYNC_SHEETS,
                success=False,
                result_data={},
                error=result.get("error", "Unknown error"),
                execution_time=execution_time,
                retry_count=0
            )
    
    except Exception as e:
        execution_time = time.time() - start_time
        return TaskResult(
            task_id=recommendation.recommendation_id,
            task_type=TASK_TYPE_SYNC_SHEETS,
            success=False,
            result_data={},
            error=str(e),
            execution_time=execution_time,
            retry_count=settings.max_retries
        )


async def execute_create_draft_task(
    workflow_id: str,
    recommendation: Recommendation,
    db: Session
) -> TaskResult:
    """
    Execute Gmail draft creation task.
    
    Args:
        workflow_id: Workflow identifier
        recommendation: Recommendation with draft parameters
        db: Database session
        
    Returns:
        TaskResult with execution outcome
    """
    start_time = time.time()
    
    try:
        # Extract parameters from recommendation
        params = recommendation.parameters
        recipient_email = params.get("recipient_email", "admin@example.com")
        subject = params.get("subject")
        document_type = params.get("document_type", "Request")
        
        # Get reasoning result from database
        from database.models import ReasoningResultDB
        from models import Recommendation as RecModel
        
        db_reasoning = (
            db.query(ReasoningResultDB)
            .filter(ReasoningResultDB.workflow_id == workflow_id)
            .order_by(ReasoningResultDB.created_at.desc())
            .first()
        )
        
        if not db_reasoning:
            raise ValueError("No reasoning results found for workflow")
        
        # Convert to Pydantic models
        recommendations_list = [RecModel(**r) for r in db_reasoning.recommendations]
        
        # Execute draft creation with retry
        result = await execute_with_retry(
            create_gmail_draft,
            {
                "workflow_id": workflow_id,
                "recommendations": recommendations_list,
                "recipient_email": recipient_email,
                "document_type": document_type,
                "subject": subject
            }
        )
        
        execution_time = time.time() - start_time
        
        if result.get("success"):
            return TaskResult(
                task_id=recommendation.recommendation_id,
                task_type=TASK_TYPE_CREATE_DRAFT,
                success=True,
                result_data={
                    "draft_id": result.get("draft_id"),
                    "recipient": result.get("recipient"),
                    "recommendations_count": result.get("recommendations_count")
                },
                error=None,
                execution_time=execution_time,
                retry_count=0
            )
        else:
            return TaskResult(
                task_id=recommendation.recommendation_id,
                task_type=TASK_TYPE_CREATE_DRAFT,
                success=False,
                result_data={},
                error=result.get("error", "Unknown error"),
                execution_time=execution_time,
                retry_count=0
            )
    
    except Exception as e:
        execution_time = time.time() - start_time
        return TaskResult(
            task_id=recommendation.recommendation_id,
            task_type=TASK_TYPE_CREATE_DRAFT,
            success=False,
            result_data={},
            error=str(e),
            execution_time=execution_time,
            retry_count=settings.max_retries
        )


async def execute_task(
    workflow_id: str,
    recommendation: Recommendation,
    db: Session
) -> TaskResult:
    """
    Execute a single task based on recommendation type.
    
    Args:
        workflow_id: Workflow identifier
        recommendation: Recommendation to execute
        db: Database session
        
    Returns:
        TaskResult with execution outcome
    """
    action_type = recommendation.action_type.lower()
    
    print(f"[Task Orchestrator] Executing task: {recommendation.recommendation_id} ({action_type})")
    
    if action_type == TASK_TYPE_SYNC_SHEETS:
        return await execute_sync_sheets_task(workflow_id, recommendation, db)
    
    elif action_type == TASK_TYPE_CREATE_DRAFT:
        return await execute_create_draft_task(workflow_id, recommendation, db)
    
    elif action_type == TASK_TYPE_SEND_EMAIL:
        # TODO: Implement send email task
        return TaskResult(
            task_id=recommendation.recommendation_id,
            task_type=action_type,
            success=False,
            result_data={},
            error="Send email task not yet implemented",
            execution_time=0.0,
            retry_count=0
        )
    
    elif action_type == TASK_TYPE_NOTIFY_USER:
        # TODO: Implement notify user task
        return TaskResult(
            task_id=recommendation.recommendation_id,
            task_type=action_type,
            success=False,
            result_data={},
            error="Notify user task not yet implemented",
            execution_time=0.0,
            retry_count=0
        )
    
    else:
        # Unknown task type
        return TaskResult(
            task_id=recommendation.recommendation_id,
            task_type=action_type,
            success=False,
            result_data={},
            error=f"Unknown task type: {action_type}",
            execution_time=0.0,
            retry_count=0
        )


def resolve_dependencies(
    recommendations: List[Recommendation]
) -> List[List[Recommendation]]:
    """
    Resolve task dependencies and return execution order.
    
    Groups recommendations into batches where:
    - Batch 0: No dependencies
    - Batch 1: Depends only on Batch 0
    - Batch 2: Depends on Batch 0 or 1
    - etc.
    
    Args:
        recommendations: List of recommendations with dependencies
        
    Returns:
        List of batches, where each batch can be executed in parallel
    """
    # Create dependency graph
    rec_map = {rec.recommendation_id: rec for rec in recommendations}
    batches = []
    remaining = set(rec_map.keys())
    completed = set()
    
    while remaining:
        # Find recommendations with no unmet dependencies
        batch = []
        for rec_id in list(remaining):
            rec = rec_map[rec_id]
            dependencies = set(rec.dependencies)
            
            # Check if all dependencies are completed
            if dependencies.issubset(completed):
                batch.append(rec)
                remaining.remove(rec_id)
        
        if not batch:
            # Circular dependency or invalid dependency
            print(f"[Task Orchestrator] Warning: Circular dependency detected. Remaining tasks: {remaining}")
            # Add remaining tasks to final batch
            batch = [rec_map[rec_id] for rec_id in remaining]
            remaining.clear()
        
        batches.append(batch)
        completed.update([rec.recommendation_id for rec in batch])
    
    return batches


async def orchestrate_tasks(
    workflow_id: str,
    recommendations: List[Recommendation],
    db: Session
) -> OrchestrationResult:
    """
    Orchestrate execution of all approved recommendations.
    
    Resolves dependencies, executes tasks in correct order,
    and collects results.
    
    Args:
        workflow_id: Workflow identifier
        recommendations: List of approved recommendations
        db: Database session
        
    Returns:
        OrchestrationResult with all task results
    """
    print(f"[Task Orchestrator] Starting orchestration for workflow: {workflow_id}")
    print(f"[Task Orchestrator] Total recommendations: {len(recommendations)}")
    
    # Resolve dependencies
    batches = resolve_dependencies(recommendations)
    print(f"[Task Orchestrator] Execution batches: {len(batches)}")
    
    all_results = []
    failed_tasks = []
    
    # Execute batches sequentially
    for batch_num, batch in enumerate(batches):
        print(f"[Task Orchestrator] Executing batch {batch_num + 1}/{len(batches)} ({len(batch)} tasks)")
        
        # Execute tasks in batch concurrently
        batch_tasks = [
            execute_task(workflow_id, rec, db)
            for rec in batch
        ]
        
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                # Task raised an exception
                failed_tasks.append("unknown")
                all_results.append(TaskResult(
                    task_id="unknown",
                    task_type="unknown",
                    success=False,
                    result_data={},
                    error=str(result),
                    execution_time=0.0,
                    retry_count=0
                ))
            else:
                all_results.append(result)
                if not result.success:
                    failed_tasks.append(result.task_id)
    
    overall_success = len(failed_tasks) == 0
    
    # Log orchestration result
    log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="task_orchestration",
        actor="system",
        details={
            "total_tasks": len(recommendations),
            "successful_tasks": len(all_results) - len(failed_tasks),
            "failed_tasks": len(failed_tasks),
            "failed_task_ids": failed_tasks
        }
    )
    
    print(f"[Task Orchestrator] Orchestration complete. Success: {overall_success}")
    
    return OrchestrationResult(
        workflow_id=workflow_id,
        task_results=all_results,
        overall_success=overall_success,
        failed_tasks=failed_tasks
    )


async def handle_task_failure(
    workflow_id: str,
    failed_task: TaskResult,
    retry_count: int,
    db: Session
) -> bool:
    """
    Handle task failure with retry or escalation logic.
    
    Args:
        workflow_id: Workflow identifier
        failed_task: Failed task result
        retry_count: Current retry count
        db: Database session
        
    Returns:
        True if should retry, False if should escalate
    """
    max_retries = settings.max_retries
    
    if retry_count < max_retries:
        # Retry the task
        print(f"[Task Orchestrator] Retrying task {failed_task.task_id} (attempt {retry_count + 1}/{max_retries})")
        
        # Update workflow state to Retrying
        workflow = get_workflow(db, workflow_id)
        if workflow:
            workflow.state = WorkflowState.RETRYING.value
            db.commit()
        
        return True
    else:
        # Escalate after max retries
        print(f"[Task Orchestrator] Escalating workflow {workflow_id} after {max_retries} failed retries")
        
        # Update workflow state to Escalated
        workflow = get_workflow(db, workflow_id)
        if workflow:
            workflow.state = WorkflowState.ESCALATED.value
            db.commit()
        
        # Log escalation
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="workflow_escalated",
            actor="system",
            details={
                "reason": f"Task {failed_task.task_id} failed after {max_retries} retries",
                "error": failed_task.error,
                "task_type": failed_task.task_type
            }
        )
        
        return False
