# LangGraph Workflow Engine Guide

## Overview

The LangGraph Workflow Engine orchestrates the complete StitchFlow V2 workflow automatically, chaining together all processing steps and handling human-in-the-loop interrupts.

## Workflow Architecture

### State Machine Flow

```
New → Ingested → Redacted → Parsed → [Policy Screening]
                                ↓
                    [NeedsClarification] → Wait for Human
                                ↓
                    [PolicyReviewRequired] → Wait for Human
                                ↓
                    [ReadyForReview] → Continue
```

### Automated Steps

1. **Ingest** - Extract text from document
2. **Redact** - Mask PII for safe AI processing
3. **Reason** - AI analyzes document and generates recommendations
4. **Screen Policy** - Check recommendations against compliance rules

### Human-in-the-Loop Interrupts

The workflow automatically pauses when:
- **Clarification Needed** - AI detected ambiguities or missing information
- **Policy Review Required** - High-risk violations detected (risk score ≥ 0.5)

## How to Use

### Option 1: Automated Workflow (Recommended)

Run the complete workflow with a single API call:

```bash
# 1. Create workflow and upload document first
curl -X POST "http://localhost:8000/api/v1/workflows/?created_by=test@example.com"
# Save workflow_id

curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/upload" \
  -F "file=@test_event.txt"

# 2. Run automated workflow
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/run"
```

**Response:**
```json
{
  "workflow_id": "...",
  "final_state": "ReadyForReview",
  "requires_human_input": false,
  "human_input_type": null,
  "error": null,
  "execution_log": [
    "✅ Document ingested successfully",
    "✅ PII redacted: 3 instances found",
    "✅ Reasoning complete: 2 recommendations",
    "✅ Policy screening passed: risk score 0.3"
  ]
}
```

### Option 2: Manual Step-by-Step

Run each step individually (useful for debugging):

```bash
# Step 1: Upload
POST /api/v1/workflows/{id}/upload

# Step 2: Redact
POST /api/v1/workflows/{id}/redact

# Step 3: Reason
POST /api/v1/workflows/{id}/reason

# Step 4: Screen
POST /api/v1/workflows/{id}/screen
```

## Workflow States

### Processing States
- **New** - Workflow created, awaiting document
- **Ingested** - Document uploaded, text extracted
- **Redacted** - PII masked
- **Parsed** - AI reasoning complete

### Human Input States
- **NeedsClarification** - AI needs more information
- **PolicyReviewRequired** - Compliance violations need review
- **ReadyForReview** - Ready for final approval
- **DraftReady** - Email draft created (future)

### Execution States
- **Approved** - Human approved recommendations
- **Executed** - Tasks executed
- **Completed** - Workflow finished successfully

### Error States
- **Failed** - Workflow failed at some step
- **Retrying** - Retrying failed tasks
- **Escalated** - Requires manual intervention

## LangGraph Components

### State Definition

```python
class WorkflowGraphState(TypedDict):
    workflow_id: str
    current_state: str
    document_path: str
    file_type: str
    error: str | None
    requires_human_input: bool
    human_input_type: str | None
    messages: Annotated[Sequence[str], operator.add]
```

### Workflow Nodes

Each node represents a processing step:

1. **ingest_node** - Document ingestion
2. **redact_node** - PII redaction
3. **reason_node** - AI reasoning
4. **screen_policy_node** - Policy screening
5. **wait_for_human_node** - Human input interrupt

### Conditional Routing

The workflow uses conditional edges to decide next steps:

```python
# After reasoning
if clarification_needed:
    → wait_for_human
else:
    → screen_policy

# After policy screening
if review_required:
    → wait_for_human
else:
    → end
```

## State Persistence

The workflow engine automatically:
- ✅ Saves state to database after each step
- ✅ Logs all transitions to audit trail
- ✅ Handles errors gracefully
- ✅ Supports workflow resumption (future)

## Error Handling

### Automatic Failure Handling

If any step fails:
1. Workflow state → `Failed`
2. Error logged to audit trail
3. Error message returned to user

### Retry Logic (Future)

For transient failures:
- Automatic retry with exponential backoff
- Max 3 retry attempts
- Escalate after max retries

## Human-in-the-Loop Integration

### Clarification Flow

```
Parsed → NeedsClarification → Wait for Human
                                      ↓
                            User provides clarification
                                      ↓
                            Re-run reasoning → Continue
```

### Policy Review Flow

```
Parsed → PolicyReviewRequired → Wait for Human
                                      ↓
                            User approves/rejects
                                      ↓
                            Update recommendations → Continue
```

## Testing the Workflow Engine

### Test Case 1: Clean Document (No Issues)

**Document**: Simple event request with all info
**Expected Flow**: New → Ingested → Redacted → Parsed → ReadyForReview
**Expected Result**: No human input required

```bash
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/run"
```

### Test Case 2: Document with Ambiguities

**Document**: Event request missing date or budget
**Expected Flow**: New → Ingested → Redacted → Parsed → NeedsClarification
**Expected Result**: Workflow pauses, requires clarification

### Test Case 3: High-Risk Document

**Document**: Event with $15,000 budget (exceeds $10K limit)
**Expected Flow**: New → Ingested → Redacted → Parsed → PolicyReviewRequired
**Expected Result**: Workflow pauses, requires policy review

## Monitoring Workflow Execution

### Check Workflow State

```bash
GET /api/v1/workflows/{workflow_id}
```

### View Audit Trail

```bash
# Future endpoint
GET /api/v1/workflows/{workflow_id}/audit
```

### Execution Logs

The `/run` endpoint returns execution logs:

```json
{
  "execution_log": [
    "✅ Document ingested successfully",
    "✅ PII redacted: 3 instances found",
    "✅ Reasoning complete: 2 recommendations",
    "⚠️  Policy review required: 1 violations (risk: 0.6)"
  ]
}
```

## Advanced Features (Future)

### Workflow Resumption

```python
# Resume after human input
await resume_workflow(
    workflow_id=workflow_id,
    human_input={
        "type": "clarification",
        "data": {"missing_date": "2024-03-15"}
    },
    db=db
)
```

### Parallel Processing

For multiple documents:
```python
# Process multiple workflows concurrently
results = await asyncio.gather(*[
    run_workflow(wf_id, doc_path, file_type, db)
    for wf_id, doc_path, file_type in documents
])
```

### Custom Workflow Graphs

Create custom workflows for specific use cases:
```python
# Custom graph for contract review
contract_workflow = StateGraph(WorkflowGraphState)
contract_workflow.add_node("ingest", ingest_node)
contract_workflow.add_node("extract_clauses", extract_clauses_node)
contract_workflow.add_node("compare_precedents", compare_node)
# ...
```

## Troubleshooting

### Workflow Stuck in Processing

**Cause**: Long-running AI operation
**Solution**: Check server logs for progress

### Workflow Failed Unexpectedly

**Cause**: API error, database issue, or validation failure
**Solution**: Check `error` field in response and server logs

### Human Input Not Triggering Pause

**Cause**: Conditional routing logic issue
**Solution**: Check `requires_human_input` flag in state

## Performance Considerations

### Execution Time

Typical workflow execution:
- **Ingestion**: 0.5-2s (depends on file size)
- **Redaction**: 0.1-0.5s
- **Reasoning**: 3-10s (GLM API call)
- **Policy Screening**: 0.1-0.3s
- **Total**: ~5-15s for complete workflow

### Optimization Tips

1. **Batch Processing**: Process multiple documents in parallel
2. **Caching**: Cache policy rules to avoid repeated database queries
3. **Async Operations**: Use async/await throughout
4. **Connection Pooling**: Configure database connection pool

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  LangGraph Workflow Engine               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────┐    ┌────────┐    ┌────────┐    ┌──────────┐ │
│  │Ingest│ -> │ Redact │ -> │ Reason │ -> │  Policy  │ │
│  └──────┘    └────────┘    └────────┘    │Screening │ │
│                                           └──────────┘ │
│                                                 │       │
│                                                 v       │
│                                    ┌────────────────┐  │
│                                    │ Human Required?│  │
│                                    └────────────────┘  │
│                                         │       │      │
│                                        Yes     No      │
│                                         │       │      │
│                                         v       v      │
│                                    ┌─────┐  ┌─────┐   │
│                                    │Wait │  │ End │   │
│                                    └─────┘  └─────┘   │
│                                                        │
└────────────────────────────────────────────────────────┘
```

## Next Steps

After workflow engine is working:
1. **Phase 5**: Add Google Sheets and Gmail integrations
2. **Phase 6**: Implement workflow resumption after human input
3. **Phase 7**: Build frontend dashboard for monitoring
4. **Phase 8**: Add advanced features (T&C comparison, conflict resolution)

## API Reference

### POST /api/v1/workflows/{workflow_id}/run

**Description**: Run automated workflow

**Request**: No body required

**Response**:
```json
{
  "workflow_id": "string",
  "final_state": "string",
  "requires_human_input": boolean,
  "human_input_type": "string | null",
  "error": "string | null",
  "execution_log": ["string"]
}
```

**Status Codes**:
- `200` - Workflow executed successfully
- `400` - Invalid workflow state or missing document
- `404` - Workflow not found
- `500` - Workflow execution failed

## Summary

✅ **Automated orchestration** - Single API call runs complete workflow
✅ **Human-in-the-loop** - Pauses automatically when input needed
✅ **State persistence** - All state saved to database
✅ **Error handling** - Graceful failure with detailed logs
✅ **Audit trail** - Complete history of workflow execution
✅ **Extensible** - Easy to add new nodes and routing logic

The LangGraph Workflow Engine provides intelligent, automated document processing with human oversight when needed! 🚀
