# Policy Screening Setup Guide

## Overview

The policy screening system checks AI-generated recommendations against compliance rules to detect potential violations and calculate risk scores.

## Setup Policy Rules

### Option 1: Seed Default Rules (Recommended for Testing)

Run the seed script to populate the database with 8 default policy rules:

```bash
cd backend
python seed_policy_rules.py
```

**Default Rules Include:**
- **Financial**: High budget alerts ($10K+), medium budget alerts ($5K+), emergency spending
- **Legal**: Contract review requirements
- **Operational**: Large event coordination, vendor selection
- **Security**: Data privacy checks
- **Compliance**: Regulatory compliance checks

### Option 2: Create Custom Rules via API

You can create custom policy rules programmatically (API endpoint to be added in Phase 6).

## How Policy Screening Works

### 1. Keyword Matching
- Each policy rule has a list of keywords
- System searches recommendation text for keyword matches
- Case-insensitive matching

### 2. Condition Evaluation
- Rules can have conditions (e.g., `max_amount: 10000`)
- System evaluates conditions against recommendation data
- Supported conditions:
  - `max_amount`: Triggers if dollar amount exceeds threshold
  - `action_type`: Triggers for specific action types
  - `min_confidence`: Triggers if confidence score meets threshold

### 3. Violation Detection
- If keywords match AND conditions are met → Violation created
- Violation includes:
  - Rule name and severity
  - Description
  - Evidence (matched keywords, recommendation text)
  - Affected recommendation IDs

### 4. Risk Score Calculation
- Weighted by severity:
  - Low: 0.1
  - Medium: 0.3
  - High: 0.6
  - Critical: 1.0
- Normalized to 0.0-1.0 range
- Higher score = higher risk

### 5. Human Review Determination
- Required if:
  - Any violation has "high" or "critical" severity
  - Risk score ≥ 0.5
- Workflow state updated accordingly:
  - `PolicyReviewRequired` - Human review needed
  - `ReadyForReview` - No high-risk violations

## Testing Policy Screening

### Complete Workflow Test

```bash
# 1. Create workflow
curl -X POST "http://localhost:8000/api/v1/workflows/?created_by=test@example.com"
# Save workflow_id

# 2. Upload document with budget info
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/upload" \
  -F "file=@test_event.txt"

# 3. Redact PII
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/redact"

# 4. Run AI reasoning
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/reason"

# 5. Screen policy violations
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/screen"
```

### Expected Results

For a document with "$5,000 budget request":
- **Violations**: 1-2 (Medium Budget Alert, possibly High Budget Alert)
- **Risk Score**: 0.3-0.6
- **Review Required**: Yes (if high severity triggered)

For a document with "$500 budget request":
- **Violations**: 0
- **Risk Score**: 0.0
- **Review Required**: No

## Policy Rule Structure

```python
PolicyRule(
    rule_id="unique-id",
    category="financial",  # financial, legal, operational, security, compliance
    name="Rule Name",
    description="What this rule checks for",
    keywords=["keyword1", "keyword2"],  # Words to match
    conditions={"max_amount": 10000},   # Optional conditions
    severity="high",  # low, medium, high, critical
    requires_review=True  # Whether violations need human review
)
```

## Customizing Rules

### Add New Keywords
Edit `seed_policy_rules.py` and add keywords to existing rules:

```python
keywords=["budget", "cost", "expense", "amount", "$", "price", "funding", "financial"]
```

### Add New Conditions
Extend `evaluate_rule_conditions()` in `components/policy_screening.py`:

```python
# Example: Check for specific document types
if "document_type" in conditions:
    required_type = conditions["document_type"]
    if workflow_data["classification"]["document_type"] == required_type:
        return True
```

### Adjust Risk Thresholds
Modify `SEVERITY_WEIGHTS` in `components/policy_screening.py`:

```python
SEVERITY_WEIGHTS = {
    "low": 0.1,
    "medium": 0.3,
    "high": 0.6,
    "critical": 1.0
}
```

## Troubleshooting

**No violations detected when expected:**
- Check if policy rules are seeded: `python seed_policy_rules.py`
- Verify keywords match recommendation text
- Check if conditions are too restrictive

**Too many false positives:**
- Add more specific keywords
- Add stricter conditions
- Adjust severity levels

**Risk score seems wrong:**
- Review `SEVERITY_WEIGHTS` configuration
- Check violation count and severities
- Verify calculation in `calculate_risk_score()`

## Next Steps

After policy screening is working:
1. **Phase 5**: Implement LangGraph workflow engine for automated orchestration
2. **Phase 6**: Add Google Sheets and Gmail integrations
3. **Phase 7**: Build frontend dashboard for human review

## API Reference

### POST /api/v1/workflows/{workflow_id}/screen

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/screen"
```

**Response:**
```json
{
  "workflow_id": "...",
  "state": "PolicyReviewRequired",
  "violations_found": 2,
  "violations": [
    {
      "rule_name": "High Budget Alert",
      "severity": "high",
      "description": "Events exceeding $10,000 require approval",
      "evidence": [
        "Matched keywords: budget, amount, $",
        "Recommendation: Approve $15,000 budget request"
      ],
      "affected_recommendations": ["rec_001"]
    }
  ],
  "risk_score": 0.6,
  "requires_human_review": true,
  "screening_time": 0.15
}
```

## Database Schema

Policy rules are stored in the `policy_rules` table:

```sql
CREATE TABLE policy_rules (
    rule_id VARCHAR(36) PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    keywords JSON NOT NULL,
    conditions JSON NOT NULL,
    severity VARCHAR(20) NOT NULL,
    requires_review BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Screening results are stored in `policy_screening_results` table.
