"""
SQLAlchemy database models.

These are the ORM models that map to database tables.
"""
from sqlalchemy import Column, String, DateTime, Text, Integer, Float, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from .base import Base
import uuid


def generate_uuid():
    """Generate UUID for primary keys."""
    return str(uuid.uuid4())


def empty_dict():
    """Return empty dict for mutable default."""
    return {}


class WorkflowDB(Base):
    """
    Workflows table - stores workflow instances.
    """
    __tablename__ = "workflows"
    
    workflow_id = Column(String(36), primary_key=True, default=generate_uuid)
    state = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(255), nullable=False, index=True)
    
    # Document content
    document_path = Column(Text, nullable=True)
    document_text = Column(Text, nullable=True)
    redacted_text = Column(Text, nullable=True)
    
    # PII redaction mapping (stored as JSON)
    token_map = Column(JSON, nullable=True, default=empty_dict)
    
    # Additional metadata (stored as JSON)
    workflow_metadata = Column(JSON, nullable=True, default=empty_dict)


class ReasoningResultDB(Base):
    """
    Reasoning results table - stores GLM reasoning outputs.
    """
    __tablename__ = "reasoning_results"
    
    result_id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(36), ForeignKey("workflows.workflow_id"), nullable=False, index=True)
    
    # Reasoning outputs (stored as JSON)
    classification = Column(JSON, nullable=False)
    entities = Column(JSON, nullable=False, default=[])
    ambiguities = Column(JSON, nullable=False, default=[])
    conflicts = Column(JSON, nullable=False, default=[])
    recommendations = Column(JSON, nullable=False, default=[])
    
    reasoning_time = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PolicyScreeningResultDB(Base):
    """
    Policy screening results table - stores policy screening outputs.
    """
    __tablename__ = "policy_screening_results"
    
    result_id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(36), ForeignKey("workflows.workflow_id"), nullable=False, index=True)
    
    # Screening outputs (stored as JSON)
    violations = Column(JSON, nullable=False, default=[])
    risk_score = Column(Float, nullable=False)
    requires_human_review = Column(Boolean, nullable=False)
    
    screening_time = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DecisionDB(Base):
    """
    Decisions table - stores human decisions.
    """
    __tablename__ = "decisions"
    
    decision_id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(36), ForeignKey("workflows.workflow_id"), nullable=False, index=True)
    decision_type = Column(String(50), nullable=False)
    user_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reasoning = Column(Text, nullable=True)
    
    # Modifications (stored as JSON)
    modifications = Column(JSON, nullable=True, default={})


class AuditLogDB(Base):
    """
    Audit log table - immutable log of all workflow actions.
    """
    __tablename__ = "audit_log"
    
    entry_id = Column(String(36), primary_key=True, default=generate_uuid)
    workflow_id = Column(String(36), ForeignKey("workflows.workflow_id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    actor = Column(String(255), nullable=False)
    
    # Action details (stored as JSON)
    details = Column(JSON, nullable=False)
    
    # Hash for tamper detection
    hash = Column(String(64), nullable=False)


class PolicyRuleDB(Base):
    """
    Policy rules table - stores compliance rules.
    """
    __tablename__ = "policy_rules"
    
    rule_id = Column(String(36), primary_key=True, default=generate_uuid)
    category = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Rule configuration (stored as JSON)
    keywords = Column(JSON, nullable=False, default=[])
    conditions = Column(JSON, nullable=False, default={})
    
    severity = Column(String(20), nullable=False, index=True)
    requires_review = Column(Boolean, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
