"""
StitchFlow V2 - Main application entry point.
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func
from config.settings import settings
from database.base import init_db, get_db
from api.workflows import router as workflows_router
from models import WorkflowState


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup: Initialize database
    print("Initializing database...")
    init_db()
    print("Database initialized successfully")
    
    yield
    
    # Shutdown: Cleanup if needed
    print("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered human-in-the-loop decision-support engine for workflow automation",
    version="2.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workflows_router)


# Dashboard endpoint (separate from workflows)
@app.get("/api/v1/dashboard/stats")
async def get_dashboard_statistics(db: Session = Depends(get_db)):
    """
    Get dashboard statistics for monitoring.
    
    This endpoint provides aggregate statistics about workflows
    for the monitoring dashboard.
    
    Returns:
        Dashboard statistics
    """
    try:
        from database.models import WorkflowDB
        
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
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard statistics: {str(e)}")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "name": settings.app_name,
        "version": "2.0.0",
        "status": "healthy",
        "environment": settings.app_env
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Add actual database check
        "glm_api": "configured" if settings.zhipu_api_key else "not_configured"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
