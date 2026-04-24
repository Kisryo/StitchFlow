"""
Task Orchestrator Component.

Executes approved recommendations using GLM-powered document generation.
Produces structured output documents (summaries, draft emails) instead of
calling external APIs like Google Sheets/Gmail.
"""
import time
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from models import (
    Recommendation,
    TaskResult,
    OrchestrationResult,
    WorkflowState
)
from database.utils import get_workflow, log_audit_entry
from components.document_generator import generate_summary_document
from config.settings import settings


async def execute_generate_summary(
    workflow_id: str,
    recommendation: Recommendation,
    db: Session
) -> TaskResult:
    """
    Generate a structured summary document using GLM.

    Args:
        workflow_id: Workflow identifier
        recommendation: Recommendation triggering this task
        db: Database session

    Returns:
        TaskResult with generated document
    """
    start_time = time.time()

    try:
        from database.models import ReasoningResultDB
        from models import ReasoningResult, Classification, Entity, Ambiguity, Conflict

        db_reasoning = (
            db.query(ReasoningResultDB)
            .filter(ReasoningResultDB.workflow_id == workflow_id)
            .order_by(ReasoningResultDB.created_at.desc())
            .first()
        )

        if not db_reasoning:
            raise ValueError("No reasoning results found for workflow")

        # Convert to Pydantic models
        conflicts_data = []
        for conflict in db_reasoning.conflicts:
            conflict_dict = dict(conflict) if not isinstance(conflict, dict) else conflict
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

        # Get clarifications from workflow metadata
        workflow = get_workflow(db, workflow_id)
        clarifications = None
        if workflow and workflow.workflow_metadata and "clarifications" in workflow.workflow_metadata:
            clarifications = workflow.workflow_metadata["clarifications"]

        # Generate document
        result = await generate_summary_document(
            workflow_id=workflow_id,
            classification=reasoning_result.classification,
            entities=reasoning_result.entities,
            ambiguities=reasoning_result.ambiguities,
            conflicts=reasoning_result.conflicts,
            recommendations=reasoning_result.recommendations,
            clarifications=clarifications,
        )

        execution_time = time.time() - start_time

        if result["success"]:
            # Store generated document in workflow metadata
            if workflow and workflow.workflow_metadata:
                workflow.workflow_metadata["generated_document"] = result["document"]
                db.commit()

            return TaskResult(
                task_id=recommendation.recommendation_id,
                task_type="generate_summary",
                success=True,
                result_data={
                    "title": result["document"].get("title", ""),
                    "executive_summary": result["document"].get("executive_summary", ""),
                    "key_findings_count": len(result["document"].get("key_findings", [])),
                    "recommendations_count": len(result["document"].get("recommendations_summary", [])),
                    "draft_email_subject": result["document"].get("draft_email", {}).get("subject", ""),
                    "generation_time": result["generation_time"],
                },
                error=None,
                execution_time=execution_time,
                retry_count=0,
            )
        else:
            return TaskResult(
                task_id=recommendation.recommendation_id,
                task_type="generate_summary",
                success=False,
                result_data={},
                error=result.get("error", "Document generation failed"),
                execution_time=execution_time,
                retry_count=0,
            )

    except Exception as e:
        execution_time = time.time() - start_time
        return TaskResult(
            task_id=recommendation.recommendation_id,
            task_type="generate_summary",
            success=False,
            result_data={},
            error=str(e),
            execution_time=execution_time,
            retry_count=settings.max_retries,
        )


async def execute_task(
    workflow_id: str,
    recommendation: Recommendation,
    db: Session
) -> TaskResult:
    """
    Execute a single task based on recommendation type.

    All tasks now use GLM for document generation instead of external APIs.

    Args:
        workflow_id: Workflow identifier
        recommendation: Recommendation to execute
        db: Database session

    Returns:
        TaskResult with execution outcome
    """
    action_type = recommendation.action_type.lower()

    print(f"[Task Orchestrator] Executing task: {recommendation.recommendation_id} ({action_type})")

    # All task types now generate a summary document via GLM
    # Regardless of whether AI says "sync_sheets" or "create_draft",
    # we produce a structured document output
    return await execute_generate_summary(workflow_id, recommendation, db)


def resolve_dependencies(
    recommendations: List[Recommendation]
) -> List[List[Recommendation]]:
    """
    Resolve task dependencies and return execution order.

    Groups recommendations into batches where:
    - Batch 0: No dependencies
    - Batch 1: Depends only on Batch 0
    - etc.

    Args:
        recommendations: List of recommendations with dependencies

    Returns:
        List of batches, where each batch can be executed in parallel
    """
    rec_map = {rec.recommendation_id: rec for rec in recommendations}
    batches = []
    remaining = set(rec_map.keys())
    completed = set()

    while remaining:
        batch = []
        for rec_id in list(remaining):
            rec = rec_map[rec_id]
            dependencies = set(rec.dependencies)

            if dependencies.issubset(completed):
                batch.append(rec)
                remaining.remove(rec_id)

        if not batch:
            print(f"[Task Orchestrator] Warning: Circular dependency detected. Remaining tasks: {remaining}")
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

    batches = resolve_dependencies(recommendations)
    print(f"[Task Orchestrator] Execution batches: {len(batches)}")

    all_results = []
    failed_tasks = []

    for batch_num, batch in enumerate(batches):
        print(f"[Task Orchestrator] Executing batch {batch_num + 1}/{len(batches)} ({len(batch)} tasks)")

        batch_tasks = [
            execute_task(workflow_id, rec, db)
            for rec in batch
        ]

        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
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
