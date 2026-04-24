# Requirements Document: StitchFlow V2

## Introduction

StitchFlow V2 is an AI-powered human-in-the-loop (HITL) decision-support engine for workflow automation. The system leverages Z.AI GLM-4.5 as its central reasoning engine to process unstructured inputs, perform multi-step reasoning, orchestrate dynamic tasks, and generate structured outputs while maintaining human oversight at critical decision points. The system is designed for event directors, operations managers, legal/compliance reviewers, and administrative coordinators who need to automate complex workflows while maintaining control and compliance.

## Glossary

- **StitchFlow**: The complete AI-powered HITL decision-support system
- **GLM**: Z.AI GLM-4.5 language model used for reasoning and decision-making
- **HITL**: Human-in-the-loop - requiring human review/approval at key stages
- **Redaction_Engine**: Component that masks PII before GLM processing
- **Reasoning_Chain**: Multi-step GLM processing pipeline for decision-making
- **Task_Orchestrator**: Component managing dynamic tool/API interactions
- **Workflow_Engine**: Stateful engine managing workflow state transitions (implemented using LangGraph)
- **Policy_Screener**: Component validating decisions against compliance rules
- **Audit_Logger**: Component recording all workflow actions and decisions
- **PII**: Personally Identifiable Information requiring protection
- **T&C**: Terms and Conditions documents
- **Confidence_Score**: Numerical measure (0-1) of GLM decision certainty
- **LangGraph**: Framework for building stateful, multi-agent workflows with cycles and human-in-the-loop
- **RAG**: Retrieval Augmented Generation - technique for grounding LLM responses in retrieved documents
- **Vector_Store**: Database storing embeddings for semantic search (Chroma or Pinecone)
- **Pydantic**: Python library for data validation and schema enforcement

## Requirements

### Requirement 1: Unstructured Input Processing

**User Story:** As an operations manager, I want to upload various unstructured documents (messages, forms, PDFs), so that the system can automatically extract relevant information without manual data entry.

#### Acceptance Criteria

1. WHEN a user uploads a file (PDF, DOCX, TXT, email), THE StitchFlow SHALL accept and store the file
2. WHEN a file is uploaded, THE StitchFlow SHALL extract text content from the file
3. WHEN text is extracted, THE StitchFlow SHALL transition the workflow to "Ingested" state
4. WHEN extraction fails, THE StitchFlow SHALL transition to "Failed" state and log the error
5. THE StitchFlow SHALL support multiple file formats including PDF, DOCX, TXT, and email formats

### Requirement 2: PII Redaction

**User Story:** As a compliance officer, I want all personally identifiable information automatically redacted before AI processing, so that we maintain data privacy and regulatory compliance.

#### Acceptance Criteria

1. WHEN text content is ingested, THE Redaction_Engine SHALL identify PII patterns (names, emails, phone numbers, addresses, SSNs)
2. WHEN PII is identified, THE Redaction_Engine SHALL replace it with masked tokens (e.g., [NAME], [EMAIL], [PHONE])
3. WHEN redaction completes, THE Redaction_Engine SHALL store both original and redacted versions
4. WHEN redaction completes, THE Workflow_Engine SHALL transition to "Redacted" state
5. THE Redaction_Engine SHALL maintain a mapping between masked tokens and original values for later restoration

### Requirement 3: Multi-Step GLM Reasoning

**User Story:** As an event director, I want the AI to perform sophisticated multi-step reasoning on my documents, so that it can classify content, extract key information, detect ambiguities, and recommend actions.

#### Acceptance Criteria

1. WHEN redacted text is available, THE Reasoning_Chain SHALL classify the document type and intent
2. WHEN classification completes, THE Reasoning_Chain SHALL extract structured entities and key information
3. WHEN extraction completes, THE Reasoning_Chain SHALL detect ambiguous or unclear content
4. WHEN ambiguity is detected, THE Reasoning_Chain SHALL identify specific missing or unclear data points
5. WHEN conflicts exist in the data, THE Reasoning_Chain SHALL identify and surface contradictions
6. WHEN all analysis completes, THE Reasoning_Chain SHALL generate action recommendations with confidence scores
7. WHEN reasoning completes, THE Workflow_Engine SHALL transition to "Parsed" state

### Requirement 4: Ambiguity and Missing Data Handling

**User Story:** As an administrative coordinator, I want the system to clearly identify when information is ambiguous or missing, so that I can provide clarification before proceeding.

#### Acceptance Criteria

1. WHEN the Reasoning_Chain detects ambiguous content, THE Workflow_Engine SHALL transition to "Needs Clarification" state
2. WHEN in "Needs Clarification" state, THE StitchFlow SHALL present specific questions to the user
3. WHEN the user provides clarification, THE StitchFlow SHALL store the additional information
4. WHEN clarification is provided, THE Workflow_Engine SHALL re-run the Reasoning_Chain with updated context
5. WHEN multiple interpretations exist, THE StitchFlow SHALL present all interpretations for user selection

### Requirement 5: Policy and Compliance Screening

**User Story:** As a legal reviewer, I want all AI recommendations screened against our policies and compliance rules, so that I can quickly identify potential violations before approval.

#### Acceptance Criteria

1. WHEN the Reasoning_Chain generates recommendations, THE Policy_Screener SHALL evaluate them against defined policy rules
2. WHEN policy violations are detected, THE Policy_Screener SHALL flag specific violations with evidence
3. WHEN policy screening completes, THE Policy_Screener SHALL assign confidence scores to each recommendation
4. WHEN high-risk items are detected, THE Workflow_Engine SHALL transition to "Policy Review Required" state
5. WHEN no violations are found, THE Workflow_Engine SHALL transition to "Ready for Review" state

### Requirement 6: Google Sheets Integration

**User Story:** As an operations manager, I want extracted data automatically synced to Google Sheets, so that my team can review and edit information in a familiar spreadsheet interface.

#### Acceptance Criteria

1. WHEN structured data is extracted, THE Task_Orchestrator SHALL create or update rows in a designated Google Sheet
2. WHEN data is synced, THE Task_Orchestrator SHALL include confidence scores and flags for review
3. WHEN users edit the Google Sheet, THE StitchFlow SHALL detect changes and update internal state
4. WHEN sync fails, THE Task_Orchestrator SHALL retry with exponential backoff
5. THE Task_Orchestrator SHALL maintain bidirectional sync between StitchFlow and Google Sheets

### Requirement 7: Gmail Draft Workflow

**User Story:** As an event director, I want the system to generate email drafts for my review, so that I can approve or modify communications before they are sent.

#### Acceptance Criteria

1. WHEN the Reasoning_Chain recommends email communication, THE Task_Orchestrator SHALL generate an email draft using Gmail API
2. WHEN a draft is created, THE Workflow_Engine SHALL transition to "Draft Ready" state
3. WHEN in "Draft Ready" state, THE StitchFlow SHALL present the draft to the user for review
4. WHEN the user approves the draft, THE Task_Orchestrator SHALL send the email
5. WHEN the user rejects the draft, THE Workflow_Engine SHALL transition back to "Ready for Review" state

### Requirement 8: Terms and Conditions Comparison

**User Story:** As a legal reviewer, I want to compare multiple T&C documents with color-coded differences, so that I can quickly identify precedent clauses, AI-generated content, and sections needing review.

#### Acceptance Criteria

1. WHEN multiple T&C documents are uploaded, THE StitchFlow SHALL parse and segment them into clauses
2. WHEN clauses are extracted, THE Reasoning_Chain SHALL compare them and identify similarities and differences
3. WHEN comparison completes, THE StitchFlow SHALL present a color-coded UI showing: precedent clauses (green), AI-generated clauses (blue), and needs-review clauses (yellow)
4. WHEN a user clicks a clause, THE StitchFlow SHALL display the source document and context
5. THE StitchFlow SHALL allow users to accept, reject, or modify individual clauses

### Requirement 9: Stateful Workflow Engine

**User Story:** As a system administrator, I want the workflow engine to maintain explicit states and handle transitions correctly, so that workflows can be tracked, resumed, and audited.

#### Acceptance Criteria

1. THE Workflow_Engine SHALL support these states: New, Ingested, Redacted, Parsed, Needs Clarification, Policy Review Required, Ready for Review, Draft Ready, Approved, Executed, Retrying, Failed, Escalated, Completed
2. WHEN a workflow transitions between states, THE Workflow_Engine SHALL validate the transition is allowed
3. WHEN a workflow is in a terminal state (Completed, Failed, Escalated), THE Workflow_Engine SHALL prevent further transitions
4. WHEN a workflow state changes, THE Audit_Logger SHALL record the transition with timestamp and reason
5. THE Workflow_Engine SHALL persist workflow state to survive system restarts

### Requirement 10: Retry and Escalation Logic

**User Story:** As an operations manager, I want the system to automatically retry failed operations and escalate persistent failures, so that transient issues are handled gracefully without manual intervention.

#### Acceptance Criteria

1. WHEN an operation fails, THE Workflow_Engine SHALL transition to "Retrying" state
2. WHEN in "Retrying" state, THE Workflow_Engine SHALL retry the operation with exponential backoff
3. WHEN retry count exceeds the maximum (3 attempts), THE Workflow_Engine SHALL transition to "Escalated" state
4. WHEN in "Escalated" state, THE StitchFlow SHALL notify designated administrators
5. WHEN a retry succeeds, THE Workflow_Engine SHALL transition to the appropriate next state

### Requirement 11: Conflict Resolution

**User Story:** As an administrative coordinator, I want the system to surface conflicting information from documents, so that I can resolve contradictions before making decisions.

#### Acceptance Criteria

1. WHEN the Reasoning_Chain detects conflicting data points, THE StitchFlow SHALL identify the specific conflicts
2. WHEN conflicts are identified, THE StitchFlow SHALL present the conflicting evidence side-by-side
3. WHEN conflicts exist, THE Workflow_Engine SHALL transition to "Needs Clarification" state
4. WHEN the user resolves a conflict, THE StitchFlow SHALL record the resolution and reasoning
5. THE StitchFlow SHALL use resolved conflicts to inform future similar decisions

### Requirement 12: Audit Trail and Logging

**User Story:** As a compliance officer, I want complete audit trails of all workflow actions and decisions, so that I can demonstrate compliance and investigate issues.

#### Acceptance Criteria

1. WHEN any workflow action occurs, THE Audit_Logger SHALL record the action with timestamp, user, and context
2. WHEN the GLM makes a decision, THE Audit_Logger SHALL record the input, output, and confidence score
3. WHEN a user makes a decision, THE Audit_Logger SHALL record the choice and any provided reasoning
4. WHEN policy screening occurs, THE Audit_Logger SHALL record all evaluated rules and results
5. THE Audit_Logger SHALL store logs in an immutable, tamper-evident format

### Requirement 13: Dashboard and Monitoring

**User Story:** As an operations manager, I want a dashboard showing all active workflows and their states, so that I can monitor progress and identify bottlenecks.

#### Acceptance Criteria

1. THE StitchFlow SHALL provide a dashboard displaying all workflows with their current states
2. WHEN viewing the dashboard, THE StitchFlow SHALL show workflows grouped by state
3. WHEN viewing the dashboard, THE StitchFlow SHALL highlight workflows requiring human attention
4. WHEN a user clicks a workflow, THE StitchFlow SHALL display detailed workflow history and current data
5. THE StitchFlow SHALL update the dashboard in real-time as workflow states change

### Requirement 14: Schema Validation

**User Story:** As a developer, I want all structured outputs validated against schemas, so that downstream systems receive correctly formatted data.

#### Acceptance Criteria

1. WHEN the Reasoning_Chain generates structured output, THE StitchFlow SHALL validate it against the defined schema
2. WHEN validation fails, THE Workflow_Engine SHALL transition to "Failed" state and log specific validation errors
3. WHEN validation succeeds, THE Workflow_Engine SHALL proceed to the next state
4. THE StitchFlow SHALL support JSON Schema for output validation
5. WHEN schema validation fails repeatedly, THE Workflow_Engine SHALL transition to "Escalated" state

### Requirement 15: Dynamic Task Orchestration

**User Story:** As an event director, I want the system to dynamically determine which tools and APIs to use based on the workflow context, so that appropriate actions are taken automatically.

#### Acceptance Criteria

1. WHEN the Reasoning_Chain recommends actions, THE Task_Orchestrator SHALL determine which tools/APIs are needed
2. WHEN tools are identified, THE Task_Orchestrator SHALL execute them in the correct sequence
3. WHEN a tool execution fails, THE Task_Orchestrator SHALL handle the error and retry if appropriate
4. WHEN all tasks complete, THE Workflow_Engine SHALL transition to "Executed" state
5. THE Task_Orchestrator SHALL support Google Sheets API, Gmail API, and dashboard update operations
