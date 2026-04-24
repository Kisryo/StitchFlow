"""
GLM reasoning and decision-making models.

Models for classification, entity extraction, ambiguity detection,
conflict detection, and recommendation generation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional
from datetime import datetime


class Classification(BaseModel):
    """
    Document classification result from GLM.
    
    Identifies document type and intent.
    """
    document_type: str = Field(
        ...,
        description="Document type (event_request, terms_conditions, inquiry, etc.)"
    )
    intent: str = Field(..., description="User intent or purpose of document")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score")
    reasoning: str = Field(..., description="GLM's reasoning for this classification")
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "event_request",
                "intent": "Request approval for university event",
                "confidence": 0.92,
                "reasoning": "Document contains event details, venue requirements, and approval request language"
            }
        }


class Entity(BaseModel):
    """
    Extracted entity from document.
    
    Represents structured information identified by GLM.
    """
    entity_type: str = Field(
        ...,
        description="Entity type (date, person, amount, requirement, location, etc.)"
    )
    value: str = Field(..., description="Extracted entity value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")
    source_text: str = Field(..., description="Original text where entity was found")
    metadata: Dict = Field(
        default_factory=dict,
        description="Additional entity metadata"
    )
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity_type": "date",
                "value": "2024-03-15",
                "confidence": 0.95,
                "source_text": "The event will be held on March 15, 2024",
                "metadata": {
                    "format": "YYYY-MM-DD",
                    "day_of_week": "Friday"
                }
            }
        }


class Ambiguity(BaseModel):
    """
    Detected ambiguity or unclear information.
    
    Represents content that requires clarification.
    """
    ambiguity_type: str = Field(
        ...,
        description="Type of ambiguity (missing_data, unclear_reference, multiple_interpretations)"
    )
    description: str = Field(..., description="Description of the ambiguity")
    affected_entities: List[str] = Field(
        default_factory=list,
        description="Entity types affected by this ambiguity"
    )
    clarification_question: str = Field(
        ...,
        description="Question to ask user for clarification"
    )
    possible_interpretations: List[str] = Field(
        default_factory=list,
        description="Possible interpretations if multiple exist"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "ambiguity_type": "missing_data",
                "description": "Event capacity not specified",
                "affected_entities": ["capacity", "venue_requirements"],
                "clarification_question": "How many attendees are expected for this event?",
                "possible_interpretations": []
            }
        }


class Conflict(BaseModel):
    """
    Detected conflict or contradiction in data.
    
    Represents inconsistent information that needs resolution.
    """
    conflict_type: str = Field(
        ...,
        description="Type of conflict (contradictory_dates, inconsistent_amounts, etc.)"
    )
    description: str = Field(..., description="Description of the conflict")
    conflicting_entities: List[Dict] = Field(
        ...,
        description="Entities that are in conflict"
    )
    evidence: List[str] = Field(
        ...,
        description="Text evidence showing the conflict"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "conflict_type": "contradictory_dates",
                "description": "Event date mentioned as both March 15 and March 20",
                "conflicting_entities": [
                    {
                        "entity_type": "date",
                        "value": "2024-03-15",
                        "confidence": 0.9,
                        "source_text": "Event on March 15",
                        "metadata": {}
                    },
                    {
                        "entity_type": "date",
                        "value": "2024-03-20",
                        "confidence": 0.85,
                        "source_text": "Scheduled for March 20",
                        "metadata": {}
                    }
                ],
                "evidence": [
                    "The event will be held on March 15, 2024",
                    "Please confirm availability for March 20, 2024"
                ]
            }
        }


class Recommendation(BaseModel):
    """
    Action recommendation from GLM reasoning.
    
    Suggests what action should be taken based on analysis.
    """
    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    action_type: str = Field(
        ...,
        description="Action type (sync_sheets, create_draft, notify_user, etc.)"
    )
    description: str = Field(..., description="Human-readable description of recommendation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Recommendation confidence score")
    parameters: Dict = Field(
        default_factory=dict,
        description="Parameters for executing this action"
    )
    reasoning: str = Field(..., description="GLM's reasoning for this recommendation")
    dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of recommendations that must complete first"
    )
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "recommendation_id": "rec_001",
                "action_type": "sync_sheets",
                "description": "Sync extracted event details to Google Sheets",
                "confidence": 0.88,
                "parameters": {
                    "sheet_id": "abc123",
                    "data": {
                        "event_name": "Tech Conference",
                        "date": "2024-03-15",
                        "capacity": 200
                    }
                },
                "reasoning": "All required event details extracted with high confidence",
                "dependencies": []
            }
        }


class ReasoningResult(BaseModel):
    """
    Complete result of GLM reasoning chain.
    
    Contains all outputs from multi-step reasoning process.
    """
    workflow_id: str = Field(..., description="Associated workflow ID")
    classification: Classification = Field(..., description="Document classification")
    entities: List[Entity] = Field(default_factory=list, description="Extracted entities")
    ambiguities: List[Ambiguity] = Field(default_factory=list, description="Detected ambiguities")
    conflicts: List[Conflict] = Field(default_factory=list, description="Detected conflicts")
    recommendations: List[Recommendation] = Field(
        default_factory=list,
        description="Action recommendations"
    )
    reasoning_time: float = Field(..., description="Total reasoning time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
                "classification": {
                    "document_type": "event_request",
                    "intent": "Request approval",
                    "confidence": 0.92,
                    "reasoning": "Contains event details and approval language"
                },
                "entities": [],
                "ambiguities": [],
                "conflicts": [],
                "recommendations": [],
                "reasoning_time": 2.5
            }
        }
