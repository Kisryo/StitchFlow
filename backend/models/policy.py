"""
Policy screening and compliance models.

Models for policy rules, violations, and screening results.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Literal
from datetime import datetime


class PolicyRule(BaseModel):
    """
    Policy rule for compliance screening.
    
    Defines a rule that recommendations are evaluated against.
    """
    rule_id: str = Field(..., description="Unique rule identifier")
    category: str = Field(..., description="Rule category (financial, legal, operational, etc.)")
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    keywords: List[str] = Field(..., description="Keywords to match against")
    conditions: Dict = Field(
        default_factory=dict,
        description="Conditions that must be met"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Violation severity level"
    )
    requires_review: bool = Field(
        ...,
        description="Whether violations require human review"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "rule_001",
                "category": "financial",
                "name": "Budget Limit Check",
                "description": "Events exceeding $10,000 require additional approval",
                "keywords": ["budget", "cost", "expense", "amount"],
                "conditions": {
                    "max_amount": 10000,
                    "currency": "USD"
                },
                "severity": "high",
                "requires_review": True
            }
        }


class Violation(BaseModel):
    """
    Policy violation detected during screening.
    
    Represents a potential compliance issue.
    """
    rule_id: str = Field(..., description="ID of violated rule")
    rule_name: str = Field(..., description="Name of violated rule")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Violation severity"
    )
    description: str = Field(..., description="Description of the violation")
    evidence: List[str] = Field(..., description="Evidence from input that triggered violation")
    affected_recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendation IDs affected by this violation"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "rule_id": "rule_001",
                "rule_name": "Budget Limit Check",
                "severity": "high",
                "description": "Event budget exceeds $10,000 limit",
                "evidence": [
                    "Total estimated cost: $15,000",
                    "Budget request for venue and catering"
                ],
                "affected_recommendations": ["rec_001", "rec_002"]
            }
        }


class PolicyScreeningResult(BaseModel):
    """
    Result of policy screening process.
    
    Contains all violations and risk assessment.
    """
    workflow_id: str = Field(..., description="Associated workflow ID")
    violations: List[Violation] = Field(default_factory=list, description="Detected violations")
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall risk score (0=no risk, 1=critical risk)"
    )
    requires_human_review: bool = Field(
        ...,
        description="Whether human review is required"
    )
    screening_time: float = Field(..., description="Screening time in seconds")
    
    @field_validator('risk_score')
    @classmethod
    def validate_risk_score(cls, v: float) -> float:
        """Ensure risk score is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Risk score must be between 0.0 and 1.0, got {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "violations": [
                    {
                        "rule_id": "rule_001",
                        "rule_name": "Budget Limit Check",
                        "severity": "high",
                        "description": "Budget exceeds limit",
                        "evidence": ["Total cost: $15,000"],
                        "affected_recommendations": ["rec_001"]
                    }
                ],
                "risk_score": 0.75,
                "requires_human_review": True,
                "screening_time": 0.3
            }
        }
