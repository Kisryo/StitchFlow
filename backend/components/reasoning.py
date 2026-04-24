"""
GLM Reasoning Chain - AI Agent for Document Analysis.

Multi-step reasoning agent that analyzes documents, extracts information,
detects ambiguities, and generates recommendations.
"""
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from models import (
    Classification,
    Entity,
    Ambiguity,
    Conflict,
    Recommendation,
    ReasoningResult,
    WorkflowState
)
from database.utils import get_workflow, save_reasoning_result, log_audit_entry
from components.glm_client import glm_client


def handle_validation_failure(
    db: Session,
    workflow_id: str,
    step_name: str,
    error_message: str
) -> None:
    """
    Handle validation failure by tracking failures and escalating if needed.
    
    Args:
        db: Database session
        workflow_id: Workflow identifier
        step_name: Name of the reasoning step that failed
        error_message: Error message describing the failure
    """
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        return
    
    # Get current failure count from metadata
    metadata = workflow.workflow_metadata or {}
    validation_failures = metadata.get("validation_failures", 0)
    validation_failures += 1
    
    # Update metadata with failure count and details
    if "validation_failure_history" not in metadata:
        metadata["validation_failure_history"] = []
    
    metadata["validation_failure_history"].append({
        "step": step_name,
        "error": error_message,
        "timestamp": time.time()
    })
    metadata["validation_failures"] = validation_failures
    
    workflow.workflow_metadata = metadata
    db.commit()
    db.refresh(workflow)
    
    # Log validation failure
    log_audit_entry(
        db=db,
        workflow_id=workflow_id,
        action_type="validation_failure",
        actor="system",
        details={
            "step": step_name,
            "error": error_message,
            "failure_count": validation_failures
        }
    )
    
    # Escalate if too many failures
    if validation_failures >= 3:
        workflow.state = WorkflowState.ESCALATED.value
        db.commit()
        db.refresh(workflow)
        
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="state_transition",
            actor="system",
            details={
                "from_state": "Redacted",
                "to_state": WorkflowState.ESCALATED.value,
                "reason": f"Escalated after {validation_failures} validation failures",
                "failure_history": metadata["validation_failure_history"]
            }
        )
        
        print(f"[Reasoning] Workflow {workflow_id} escalated after {validation_failures} validation failures")
    else:
        print(f"[Reasoning] Validation failure {validation_failures}/3 for workflow {workflow_id}")


async def classify_document(text: str) -> Classification:
    """
    Classify document type and intent using GLM.
    
    This is the first step in the reasoning chain where the AI agent
    determines what kind of document it's analyzing.
    
    Args:
        text: Redacted document text
        
    Returns:
        Classification with document type, intent, and confidence
    """
    prompt = f"""Analyze this document and classify it.

Document:
{text[:2000]}  # Limit to first 2000 chars for classification

Determine:
1. Document type (e.g., event_request, terms_conditions, inquiry, contract, email, form, report)
2. Primary intent or purpose
3. Your confidence level (0.0 to 1.0)
4. Brief reasoning for your classification

Respond with JSON in this exact format:
{{
    "document_type": "type_here",
    "intent": "intent description",
    "confidence": 0.95,
    "reasoning": "explanation"
}}"""
    
    try:
        schema = {
            "type": "object",
            "properties": {
                "document_type": {"type": "string"},
                "intent": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "reasoning": {"type": "string"}
            },
            "required": ["document_type", "intent", "confidence", "reasoning"]
        }
        
        response = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            temperature=0.3  # Lower temperature for classification
        )
        
        # Validate response with Pydantic
        try:
            classification = Classification(**response)
            print(f"[Reasoning] Classification successful: {classification.document_type} (confidence: {classification.confidence})")
            return classification
        except Exception as validation_error:
            print(f"[Reasoning] Classification validation failed: {str(validation_error)}")
            print(f"[Reasoning] Raw GLM response: {response}")
            # Return fallback classification
            return Classification(
                document_type="unknown",
                intent="Unable to determine intent",
                confidence=0.0,
                reasoning=f"Validation failed: {str(validation_error)}"
            )
        
    except Exception as e:
        print(f"[Reasoning] Classification GLM call failed: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback classification if GLM fails
        return Classification(
            document_type="unknown",
            intent="Unable to determine intent",
            confidence=0.0,
            reasoning=f"Classification failed: {str(e)}"
        )


async def extract_entities(text: str, document_type: str, clarifications: Optional[List[Dict]] = None) -> List[Entity]:
    """
    Extract structured entities from document using GLM.
    
    The AI agent identifies key information based on document type.
    
    Args:
        text: Redacted document text
        document_type: Document type from classification
        clarifications: Optional list of user-provided clarifications
        
    Returns:
        List of extracted entities
    """
    # Build clarifications context if available
    clarifications_context = ""
    if clarifications:
        clarifications_context = "\n\nUser-provided clarifications:\n"
        for clarification in clarifications:
            clarifications_context += f"- {clarification.get('ambiguity_id', 'N/A')}: {clarification.get('answer', 'N/A')}\n"
        clarifications_context += "\nUse these clarifications to extract more accurate entities.\n"
    
    prompt = f"""Extract key entities from this {document_type} document.

Document:
{text[:3000]}  # Limit to first 3000 chars
{clarifications_context}
Extract entities such as:
- Dates (event dates, deadlines, etc.)
- People (names, roles)
- Amounts (budget, costs, quantities)
- Locations (venues, addresses)
- Requirements (what needs to be done)
- Organizations
- Any other relevant structured information

For each entity, provide:
- entity_type: Type of entity
- value: The extracted value
- confidence: Your confidence (0.0 to 1.0)
- source_text: The original text where you found it
- metadata: Any additional context (optional)

Respond with JSON array:
[
    {{
        "entity_type": "date",
        "value": "2024-03-15",
        "confidence": 0.95,
        "source_text": "event on March 15, 2024",
        "metadata": {{"format": "YYYY-MM-DD"}}
    }}
]"""
    
    try:
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                    "source_text": {"type": "string"},
                    "metadata": {"type": "object"}
                },
                "required": ["entity_type", "value", "confidence", "source_text"]
            }
        }
        
        response = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            temperature=0.5
        )
        
        # Convert to Entity objects with validation
        entities = []
        for i, item in enumerate(response):
            try:
                if "metadata" not in item:
                    item["metadata"] = {}
                entity = Entity(**item)
                entities.append(entity)
            except Exception as validation_error:
                print(f"[Reasoning] Entity {i} validation failed: {str(validation_error)}")
                print(f"[Reasoning] Invalid entity data: {item}")
                # Skip invalid entities
                continue
        
        print(f"[Reasoning] Entity extraction successful: {len(entities)} entities extracted")
        return entities
        
    except Exception as e:
        print(f"[Reasoning] Entity extraction GLM call failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def detect_ambiguities(text: str, entities: List[Entity], clarifications: Optional[List[Dict]] = None) -> List[Ambiguity]:
    """
    Detect ambiguous or unclear information using GLM.
    
    The AI agent identifies what information is missing or unclear.
    
    Args:
        text: Redacted document text
        entities: Previously extracted entities
        clarifications: Optional list of user-provided clarifications
        
    Returns:
        List of detected ambiguities
    """
    entities_summary = "\n".join([f"- {e.entity_type}: {e.value}" for e in entities[:10]])
    
    # Build clarifications context if available
    clarifications_context = ""
    if clarifications:
        clarifications_context = "\n\nUser has already provided these clarifications:\n"
        for clarification in clarifications:
            clarifications_context += f"- {clarification.get('ambiguity_id', 'N/A')}: {clarification.get('answer', 'N/A')}\n"
        clarifications_context += "\nDo NOT ask for clarification on items already clarified above. Only identify NEW ambiguities.\n"
    
    prompt = f"""Analyze this document for ambiguities, missing information, or unclear content.

Document:
{text[:2000]}

Extracted entities so far:
{entities_summary}
{clarifications_context}
Identify:
1. Missing required information
2. Unclear references or vague statements
3. Multiple possible interpretations
4. Incomplete data

For each ambiguity, provide:
- ambiguity_type: "missing_data", "unclear_reference", or "multiple_interpretations"
- description: What is ambiguous
- affected_entities: List of entity types affected
- clarification_question: Specific question to ask user
- possible_interpretations: List of possible meanings (if applicable)

Respond with JSON array. If no ambiguities, return empty array []."""
    
    try:
        response = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema={"type": "array"},
            temperature=0.6
        )
        
        # Validate and convert to Ambiguity objects
        ambiguities = []
        for i, item in enumerate(response):
            try:
                if "affected_entities" not in item:
                    item["affected_entities"] = []
                if "possible_interpretations" not in item:
                    item["possible_interpretations"] = []
                ambiguity = Ambiguity(**item)
                ambiguities.append(ambiguity)
            except Exception as validation_error:
                print(f"[Reasoning] Ambiguity {i} validation failed: {str(validation_error)}")
                print(f"[Reasoning] Invalid ambiguity data: {item}")
                # Skip invalid ambiguities
                continue
        
        print(f"[Reasoning] Ambiguity detection successful: {len(ambiguities)} ambiguities found")
        return ambiguities
        
    except Exception as e:
        print(f"[Reasoning] Ambiguity detection GLM call failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def detect_conflicts(text: str, entities: List[Entity]) -> List[Conflict]:
    """
    Detect conflicts or contradictions in data using GLM.
    
    The AI agent identifies contradictory information that needs resolution.
    
    Args:
        text: Redacted document text
        entities: Previously extracted entities
        
    Returns:
        List of detected conflicts
    """
    entities_summary = "\n".join([f"- {e.entity_type}: {e.value} (from: {e.source_text})" for e in entities[:15]])
    
    prompt = f"""Analyze this document for conflicts, contradictions, or inconsistent information.

Document:
{text[:2000]}

Extracted entities:
{entities_summary}

Identify:
1. Contradictory dates or times
2. Inconsistent amounts or quantities
3. Conflicting requirements or conditions
4. Contradictory statements

For each conflict, provide:
- conflict_type: Type of conflict (e.g., "contradictory_dates", "inconsistent_amounts", "conflicting_requirements")
- description: Description of the conflict
- conflicting_entities: List of entities that are in conflict (include entity_type, value, confidence, source_text, metadata)
- evidence: List of text excerpts showing the conflict

Respond with JSON array. If no conflicts, return empty array []."""
    
    try:
        response = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema={"type": "array"},
            temperature=0.6
        )
        
        # Validate and convert to Conflict objects
        conflicts = []
        for i, item in enumerate(response):
            try:
                # Ensure conflicting_entities is a list of Entity objects
                if "conflicting_entities" in item:
                    conflicting_entities = []
                    for j, entity_data in enumerate(item["conflicting_entities"]):
                        try:
                            if "metadata" not in entity_data:
                                entity_data["metadata"] = {}
                            entity = Entity(**entity_data)
                            conflicting_entities.append(entity)
                        except Exception as entity_validation_error:
                            print(f"[Reasoning] Conflict {i} entity {j} validation failed: {str(entity_validation_error)}")
                            print(f"[Reasoning] Invalid entity data: {entity_data}")
                            # Skip invalid entities
                            continue
                    # Convert Entity objects to dicts for the new Conflict model
                    item["conflicting_entities"] = [
                        {
                            "entity_type": e.entity_type,
                            "value": e.value,
                            "confidence": e.confidence,
                            "source_text": e.source_text,
                            "metadata": e.metadata
                        }
                        for e in conflicting_entities
                    ]
                else:
                    item["conflicting_entities"] = []
                
                if "evidence" not in item:
                    item["evidence"] = []
                
                conflict = Conflict(**item)
                conflicts.append(conflict)
            except Exception as validation_error:
                print(f"[Reasoning] Conflict {i} validation failed: {str(validation_error)}")
                print(f"[Reasoning] Invalid conflict data: {item}")
                # Skip invalid conflicts
                continue
        
        print(f"[Reasoning] Conflict detection successful: {len(conflicts)} conflicts found")
        return conflicts
        
    except Exception as e:
        print(f"[Reasoning] Conflict detection GLM call failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def generate_recommendations(
    classification: Classification,
    entities: List[Entity],
    ambiguities: List[Ambiguity]
) -> List[Recommendation]:
    """
    Generate action recommendations using GLM.
    
    The AI agent decides what actions should be taken based on analysis.
    
    Args:
        classification: Document classification
        entities: Extracted entities
        ambiguities: Detected ambiguities
        
    Returns:
        List of recommendations
    """
    context = f"""Document Type: {classification.document_type}
Intent: {classification.intent}

Extracted Information:
{chr(10).join([f"- {e.entity_type}: {e.value}" for e in entities[:15]])}

Ambiguities Found: {len(ambiguities)}
{chr(10).join([f"- {a.description}" for a in ambiguities[:5]])}"""
    
    prompt = f"""Based on this document analysis, recommend appropriate actions.

{context}

Generate recommendations for:
1. What should be done with this information (e.g., sync to sheets, create draft email, notify someone)
2. What tools or APIs should be used
3. What parameters are needed

For each recommendation:
- recommendation_id: Unique ID (e.g., "rec_001")
- action_type: Type of action (sync_sheets, create_draft, notify_user, etc.)
- description: What to do
- confidence: Your confidence (0.0 to 1.0)
- parameters: Dict of parameters needed
- reasoning: Why this action
- dependencies: List of recommendation IDs that must complete first

Respond with JSON array of recommendations."""
    
    try:
        response = glm_client.structured_output(
            messages=[{"role": "user", "content": prompt}],
            schema={"type": "array"},
            temperature=0.7
        )
        
        # Validate and convert to Recommendation objects
        recommendations = []
        for i, item in enumerate(response):
            try:
                if "recommendation_id" not in item:
                    item["recommendation_id"] = f"rec_{i+1:03d}"
                if "parameters" not in item:
                    item["parameters"] = {}
                if "dependencies" not in item:
                    item["dependencies"] = []
                recommendation = Recommendation(**item)
                recommendations.append(recommendation)
            except Exception as validation_error:
                print(f"[Reasoning] Recommendation {i} validation failed: {str(validation_error)}")
                print(f"[Reasoning] Invalid recommendation data: {item}")
                # Skip invalid recommendations
                continue
        
        print(f"[Reasoning] Recommendation generation successful: {len(recommendations)} recommendations generated")
        return recommendations
        
    except Exception as e:
        print(f"[Reasoning] Recommendation generation GLM call failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def run_reasoning_chain(
    workflow_id: str,
    db: Session
) -> ReasoningResult:
    """
    Execute complete multi-step reasoning chain.
    
    This is the main AI agent that orchestrates all reasoning steps.
    
    Args:
        workflow_id: Workflow identifier
        db: Database session
        
    Returns:
        Complete reasoning result
        
    Raises:
        ValueError: If workflow not found or has no redacted text
    """
    start_time = time.time()
    
    # Get workflow
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")
    
    if not workflow.redacted_text:
        raise ValueError(f"Workflow {workflow_id} has no redacted text. Run PII redaction first.")
    
    # Check if workflow is already escalated
    if workflow.state == WorkflowState.ESCALATED.value:
        raise ValueError(f"Workflow {workflow_id} has been escalated due to repeated failures")
    
    text = workflow.redacted_text
    
    # Get clarifications from workflow metadata if available
    clarifications = None
    if workflow.workflow_metadata and "clarifications" in workflow.workflow_metadata:
        clarifications = workflow.workflow_metadata["clarifications"]
        print(f"[Reasoning Agent] Using {len(clarifications)} clarifications from user")
    
    # Step 1: Classify document
    print(f"[Reasoning Agent] Step 1: Classifying document...")
    classification = await classify_document(text)
    
    # Check for validation failure in classification
    if classification.confidence == 0.0 and "failed" in classification.reasoning.lower():
        handle_validation_failure(db, workflow_id, "classification", classification.reasoning)
        # Check if escalated
        workflow = get_workflow(db, workflow_id)
        if workflow and workflow.state == WorkflowState.ESCALATED.value:
            raise ValueError(f"Workflow escalated after classification failure")
    
    # Log GLM classification decision
    from database.utils import log_glm_decision
    log_glm_decision(
        db=db,
        workflow_id=workflow_id,
        decision_type="classification",
        input_text=text,
        output_data=classification.model_dump(),
        confidence_score=classification.confidence
    )
    
    # Step 2: Extract entities (with clarifications if available)
    print(f"[Reasoning Agent] Step 2: Extracting entities...")
    entities = await extract_entities(text, classification.document_type, clarifications)
    
    # Check for validation failure in entity extraction (empty result could indicate failure)
    if len(entities) == 0 and len(text) > 100:  # Only flag if document has substantial content
        handle_validation_failure(db, workflow_id, "entity_extraction", "No entities extracted from substantial document")
        # Check if escalated
        workflow = get_workflow(db, workflow_id)
        if workflow and workflow.state == WorkflowState.ESCALATED.value:
            raise ValueError(f"Workflow escalated after entity extraction failure")
    
    # Log GLM entity extraction decision
    log_glm_decision(
        db=db,
        workflow_id=workflow_id,
        decision_type="entity_extraction",
        input_text=text,
        output_data={"entities": [e.model_dump() for e in entities], "count": len(entities)},
        confidence_score=sum([e.confidence for e in entities]) / len(entities) if entities else 0.0
    )
    
    # Step 3: Detect ambiguities (with clarifications to avoid re-asking)
    print(f"[Reasoning Agent] Step 3: Detecting ambiguities...")
    ambiguities = await detect_ambiguities(text, entities, clarifications)
    
    # Log GLM ambiguity detection decision
    log_glm_decision(
        db=db,
        workflow_id=workflow_id,
        decision_type="ambiguity_detection",
        input_text=text,
        output_data={"ambiguities": [a.model_dump() for a in ambiguities], "count": len(ambiguities)}
    )
    
    # Step 4: Detect conflicts
    print(f"[Reasoning Agent] Step 4: Detecting conflicts...")
    conflicts = await detect_conflicts(text, entities)
    
    # Log GLM conflict detection decision
    log_glm_decision(
        db=db,
        workflow_id=workflow_id,
        decision_type="conflict_detection",
        input_text=text,
        output_data={"conflicts": [c.model_dump() for c in conflicts], "count": len(conflicts)}
    )
    
    # Step 5: Generate recommendations
    print(f"[Reasoning Agent] Step 5: Generating recommendations...")
    recommendations = await generate_recommendations(classification, entities, ambiguities)
    
    # Check for validation failure in recommendations (empty result could indicate failure)
    if len(recommendations) == 0 and classification.confidence > 0.5:  # Only flag if classification was confident
        handle_validation_failure(db, workflow_id, "recommendation_generation", "No recommendations generated despite confident classification")
        # Check if escalated
        workflow = get_workflow(db, workflow_id)
        if workflow and workflow.state == WorkflowState.ESCALATED.value:
            raise ValueError(f"Workflow escalated after recommendation generation failure")
    
    # Log GLM recommendation generation decision
    log_glm_decision(
        db=db,
        workflow_id=workflow_id,
        decision_type="recommendation_generation",
        input_text=text,
        output_data={"recommendations": [r.model_dump() for r in recommendations], "count": len(recommendations)},
        confidence_score=sum([r.confidence for r in recommendations]) / len(recommendations) if recommendations else 0.0
    )
    
    reasoning_time = time.time() - start_time
    
    # Create result
    result = ReasoningResult(
        workflow_id=workflow_id,
        classification=classification,
        entities=entities,
        ambiguities=ambiguities,
        conflicts=conflicts,
        recommendations=recommendations,
        reasoning_time=reasoning_time
    )
    
    # Save to database
    save_reasoning_result(db, result)
    
    # Update workflow state
    workflow = get_workflow(db, workflow_id)
    if workflow:
        if ambiguities:
            workflow.state = WorkflowState.NEEDS_CLARIFICATION.value
            reason = f"Reasoning complete. Found {len(ambiguities)} ambiguities requiring clarification."
        else:
            workflow.state = WorkflowState.PARSED.value
            reason = f"Reasoning complete. Extracted {len(entities)} entities, generated {len(recommendations)} recommendations."
        
        db.commit()
        db.refresh(workflow)
        
        # Log audit entry
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="state_transition",
            actor="glm",
            details={
                "from_state": "Redacted",
                "to_state": workflow.state,
                "reason": reason,
                "used_clarifications": clarifications is not None
            }
        )
    
    print(f"[Reasoning Agent] Complete! Time: {reasoning_time:.2f}s")
    
    return result
