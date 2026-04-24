"""
Policy Screening Component.

Screens recommendations against policy rules to detect compliance violations.
"""
import time
from typing import List, Dict
from sqlalchemy.orm import Session

from models import (
    PolicyRule,
    Violation,
    PolicyScreeningResult,
    ReasoningResult,
    Recommendation,
    WorkflowState
)
from database.utils import (
    get_workflow,
    get_policy_rules,
    save_policy_screening_result,
    log_audit_entry
)


# Risk score weights by severity
SEVERITY_WEIGHTS = {
    "low": 0.1,
    "medium": 0.3,
    "high": 0.6,
    "critical": 1.0
}


def load_policy_rules(
    db: Session,
    category: str = None,
    severity: str = None
) -> List[PolicyRule]:
    """
    Load policy rules from database.
    
    Args:
        db: Database session
        category: Optional category filter
        severity: Optional severity filter
        
    Returns:
        List of PolicyRule objects
    """
    db_rules = get_policy_rules(db, category=category, severity=severity)
    
    # Convert database models to Pydantic models
    rules = []
    for db_rule in db_rules:
        rule = PolicyRule(
            rule_id=db_rule.rule_id,
            category=db_rule.category,
            name=db_rule.name,
            description=db_rule.description,
            keywords=db_rule.keywords,
            conditions=db_rule.conditions,
            severity=db_rule.severity,
            requires_review=db_rule.requires_review
        )
        rules.append(rule)
    
    return rules


def match_keywords(
    text: str,
    keywords: List[str]
) -> List[str]:
    """
    Match keywords in text (case-insensitive).
    
    Args:
        text: Text to search
        keywords: Keywords to match
        
    Returns:
        List of matched keywords
    """
    text_lower = text.lower()
    matched = []
    
    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched.append(keyword)
    
    return matched


def evaluate_rule_conditions(
    rule: PolicyRule,
    recommendation: Recommendation,
    workflow_data: Dict
) -> bool:
    """
    Evaluate if rule conditions are met.
    
    Args:
        rule: Policy rule to evaluate
        recommendation: Recommendation being checked
        workflow_data: Additional workflow context
        
    Returns:
        True if conditions are met (violation detected), False otherwise
    """
    conditions = rule.conditions
    
    # If no conditions, rely only on keyword matching
    if not conditions:
        return True
    
    # Example condition checks (can be extended)
    
    # Check max_amount condition
    if "max_amount" in conditions:
        max_amount = conditions["max_amount"]
        
        # Try to extract amount from recommendation description
        import re
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?'
        amounts = re.findall(amount_pattern, recommendation.description)
        
        for amount_str in amounts:
            # Remove $ and commas, convert to float
            amount_value = float(amount_str.replace('$', '').replace(',', ''))
            if amount_value > max_amount:
                return True
    
    # Check action_type condition
    if "action_type" in conditions:
        required_action = conditions["action_type"]
        if recommendation.action_type == required_action:
            return True
    
    # Check confidence threshold
    if "min_confidence" in conditions:
        min_confidence = conditions["min_confidence"]
        if recommendation.confidence >= min_confidence:
            return True
    
    return False


def screen_recommendation(
    recommendation: Recommendation,
    rules: List[PolicyRule],
    workflow_data: Dict
) -> List[Violation]:
    """
    Screen a single recommendation against all policy rules.
    
    Args:
        recommendation: Recommendation to screen
        rules: List of policy rules
        workflow_data: Additional workflow context
        
    Returns:
        List of violations detected
    """
    violations = []
    
    # Combine recommendation text for keyword matching
    recommendation_text = f"{recommendation.description} {recommendation.reasoning}"
    
    for rule in rules:
        # Check if any keywords match
        matched_keywords = match_keywords(recommendation_text, rule.keywords)
        
        if matched_keywords:
            # Evaluate rule conditions
            conditions_met = evaluate_rule_conditions(rule, recommendation, workflow_data)
            
            if conditions_met:
                # Create violation
                violation = Violation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    description=f"{rule.description}",
                    evidence=[
                        f"Matched keywords: {', '.join(matched_keywords)}",
                        f"Recommendation: {recommendation.description}"
                    ],
                    affected_recommendations=[recommendation.recommendation_id]
                )
                violations.append(violation)
    
    return violations


def calculate_risk_score(violations: List[Violation]) -> float:
    """
    Calculate overall risk score based on violations.
    
    Risk score is weighted average of violation severities.
    
    Args:
        violations: List of violations
        
    Returns:
        Risk score between 0.0 and 1.0
    """
    if not violations:
        return 0.0
    
    # Calculate weighted sum
    total_weight = 0.0
    for violation in violations:
        weight = SEVERITY_WEIGHTS.get(violation.severity, 0.5)
        total_weight += weight
    
    # Normalize to 0-1 range
    # Use max possible weight as denominator
    max_possible_weight = len(violations) * SEVERITY_WEIGHTS["critical"]
    risk_score = min(total_weight / max_possible_weight, 1.0) if max_possible_weight > 0 else 0.0
    
    return round(risk_score, 2)


def requires_human_review(violations: List[Violation], risk_score: float) -> bool:
    """
    Determine if human review is required.
    
    Args:
        violations: List of violations
        risk_score: Calculated risk score
        
    Returns:
        True if human review is required
    """
    # Require review if any violation requires it
    for violation in violations:
        if violation.severity in ["high", "critical"]:
            return True
    
    # Require review if risk score is above threshold
    if risk_score >= 0.5:
        return True
    
    return False


async def screen_policy(
    workflow_id: str,
    reasoning_result: ReasoningResult,
    db: Session
) -> PolicyScreeningResult:
    """
    Screen recommendations against policy rules.
    
    Args:
        workflow_id: Workflow identifier
        reasoning_result: Reasoning result with recommendations
        db: Database session
        
    Returns:
        PolicyScreeningResult with violations and risk assessment
        
    Raises:
        ValueError: If workflow not found
    """
    start_time = time.time()
    
    # Get workflow for context
    workflow = get_workflow(db, workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")
    
    # Load all policy rules
    rules = load_policy_rules(db)
    
    print(f"[Policy Screener] Loaded {len(rules)} policy rules")
    
    # Prepare workflow data for condition evaluation
    workflow_data = {
        "workflow_id": workflow_id,
        "classification": reasoning_result.classification.model_dump(),
        "entities": [e.model_dump() for e in reasoning_result.entities]
    }
    
    # Screen each recommendation
    all_violations = []
    for recommendation in reasoning_result.recommendations:
        violations = screen_recommendation(recommendation, rules, workflow_data)
        all_violations.extend(violations)
    
    print(f"[Policy Screener] Found {len(all_violations)} violations")
    
    # Calculate risk score
    risk_score = calculate_risk_score(all_violations)
    
    # Determine if human review is required
    needs_review = requires_human_review(all_violations, risk_score)
    
    # Calculate screening time
    screening_time = time.time() - start_time
    
    # Create result
    result = PolicyScreeningResult(
        workflow_id=workflow_id,
        violations=all_violations,
        risk_score=risk_score,
        requires_human_review=needs_review,
        screening_time=screening_time
    )
    
    # Save to database
    save_policy_screening_result(db, result)
    
    # Log policy screening with specialized function
    from database.utils import log_policy_screening
    log_policy_screening(
        db=db,
        workflow_id=workflow_id,
        rules_evaluated=[rule.rule_id for rule in rules],
        violations_found=[v.model_dump() for v in all_violations],
        risk_score=risk_score,
        requires_review=needs_review,
        screening_time=screening_time
    )
    
    # Update workflow state
    workflow = get_workflow(db, workflow_id)
    if workflow:
        if needs_review:
            workflow.state = WorkflowState.POLICY_REVIEW_REQUIRED.value
            reason = f"Policy screening complete. Found {len(all_violations)} violations (risk score: {risk_score}). Human review required."
        else:
            workflow.state = WorkflowState.READY_FOR_REVIEW.value
            reason = f"Policy screening complete. No high-risk violations found (risk score: {risk_score})."
        
        db.commit()
        db.refresh(workflow)
        
        # Log state transition
        log_audit_entry(
            db=db,
            workflow_id=workflow_id,
            action_type="state_transition",
            actor="policy_screener",
            details={
                "from_state": "Parsed",
                "to_state": workflow.state,
                "reason": reason,
                "violations_count": len(all_violations),
                "risk_score": risk_score
            }
        )
    
    print(f"[Policy Screener] Complete! Risk score: {risk_score}, Review required: {needs_review}")
    
    return result
