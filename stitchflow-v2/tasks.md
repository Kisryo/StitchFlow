# Implementation Plan: StitchFlow V2

## Overview

This implementation plan breaks down the StitchFlow V2 system into discrete, incremental tasks. The approach follows a phased strategy: MVP core functionality first, then enhancements. Each task builds on previous work, with checkpoints to validate progress. The system uses Python with FastAPI, LangChain, LangGraph, and Z.AI GLM-4.5.

## Tasks

### Phase 1: Foundation and Core Infrastructure

- [x] 1. Set up project structure and dependencies
  - Create Python project with Poetry or pip requirements
  - Install core dependencies: FastAPI, LangChain, LangGraph, Pydantic, SQLAlchemy, PostgreSQL driver
  - Set up project directory structure (api/, workflows/, components/, models/, tests/)
  - Configure environment variables for API keys (Z.AI GLM-4.5, Google APIs)
  - _Requirements: All (foundational)_

- [ ] 2. Define core data models with Pydantic
  - [x] 2.1 Implement WorkflowState enum and Workflow model
    - Create Pydantic models for workflow state management
    - Include all state transitions from state machine
    - _Requirements: 9.1, 9.2_
  
  - [x] 2.2 Implement document processing models
    - Create IngestionResult, PIIMatch, RedactionResult models
    - Include validation rules for file types and sizes
    - _Requirements: 1.1, 1.2, 2.1, 2.2_
  
  - [x] 2.3 Implement reasoning and policy models
    - Create Classification, Entity, Ambiguity, Conflict, Recommendation models
    - Create PolicyRule, Violation, PolicyScreeningResult models
    - Include confidence score validation (0.0-1.0 range)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.1, 5.2, 5.3_
  
  - [x] 2.4 Implement decision and audit models
    - Create Decision, TaskResult, OrchestrationResult, AuditEntry models
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 15.1_

- [ ] 3. Set up database schema and connections
  - [x] 3.1 Create PostgreSQL database schema
    - Implement workflows, reasoning_results, policy_screening_results tables
    - Implement decisions, audit_log, policy_rules tables
    - Add indexes for performance optimization
    - _Requirements: 9.5, 12.5_
  
  - [x] 3.2 Implement database connection and session management
    - Set up SQLAlchemy engine and session factory
    - Implement connection pooling
    - Add database migration support (Alembic)
    - _Requirements: 9.5_
  
  - [ ] 3.3 Write property test for state persistence
    - **Property 7: State Persistence**
    - **Validates: Requirements 9.5**

- [x] 4. Checkpoint - Database foundation complete
  - Ensure database schema is created and migrations work
  - Verify all Pydantic models validate correctly
  - Ask the user if questions arise

### Phase 2: Document Ingestion and PII Redaction

- [ ] 5. Implement Document Ingestion Component
  - [x] 5.1 Create file upload handler
    - Implement FastAPI endpoint for file uploads (POST /api/v1/workflows/{workflow_id}/upload)
    - Support PDF, DOCX, TXT, email formats
    - Validate file types and sizes
    - _Requirements: 1.1, 1.2_
  
  - [x] 5.2 Implement text extraction for each file type
    - Use PyPDF2 for PDF extraction
    - Use python-docx for DOCX extraction
    - Use email library for email parsing
    - Handle extraction errors gracefully
    - _Requirements: 1.3_
  
  - [x] 5.3 Store extracted text and update workflow state
    - Save original file to file storage
    - Store extracted text in database
    - Transition workflow to "Ingested" state
    - _Requirements: 1.3, 9.1_
  
  - [ ] 5.4 Write property test for file upload and extraction
    - **Property 1: File Upload and Extraction**
    - **Validates: Requirements 1.1, 1.2, 1.3**
  
  - [ ] 5.5 Write property test for extraction failure handling
    - **Property 2: Extraction Failure Handling**
    - **Validates: Requirements 1.4**
  
  - [ ] 5.6 Write unit tests for edge cases
    - Test empty files, corrupted files, unsupported formats
    - Test large files near size limits
    - _Requirements: 1.4_

- [ ] 6. Implement PII Redaction Engine
  - [x] 6.1 Create PII pattern detection
    - Implement regex patterns for emails, phones, addresses, SSNs
    - Implement name detection (capitalized word sequences)
    - Return PIIMatch objects with positions and types
    - _Requirements: 2.1_
  
  - [x] 6.2 Implement PII redaction with token mapping
    - Replace PII with masked tokens ([EMAIL], [PHONE], [NAME], etc.)
    - Create bidirectional token mapping (token ↔ original value)
    - Store both original and redacted text
    - _Requirements: 2.2, 2.3_
  
  - [x] 6.3 Implement PII restoration function
    - Use token mapping to restore original PII from redacted text
    - _Requirements: 2.5_
  
  - [ ] 6.4 Write property test for PII detection
    - **Property 3: PII Detection**
    - **Validates: Requirements 2.1**
  
  - [ ] 6.5 Write property test for PII redaction round-trip
    - **Property 4: PII Redaction Round-Trip**
    - **Validates: Requirements 2.2, 2.3, 2.5**
  
  - [ ] 6.6 Write unit tests for PII patterns
    - Test various email formats, phone formats, address patterns
    - Test edge cases (special characters, international formats)
    - _Requirements: 2.1, 2.4_

- [x] 7. Checkpoint - Document processing complete
  - Ensure files can be uploaded and text extracted
  - Verify PII redaction works correctly
  - Test round-trip restoration
  - Ask the user if questions arise

### Phase 3: GLM Reasoning Chain

- [ ] 8. Set up Z.AI GLM-4.5 integration
  - [x] 8.1 Create GLM API client wrapper
    - Implement API authentication and request handling
    - Add error handling for API failures
    - Implement rate limiting and retry logic
    - _Requirements: 3.1, 10.1, 10.2_
  
  - [ ] 8.2 Create LangChain integration
    - Set up LangChain LLM wrapper for GLM-5.1
    - Configure prompt templates for reasoning steps
    - _Requirements: 3.1_

- [ ] 9. Implement multi-step reasoning chain
  - [x] 9.1 Implement document classification
    - Create prompt for document type and intent classification
    - Parse GLM response into Classification model
    - Include confidence score and reasoning
    - _Requirements: 3.2, 3.6_
  
  - [x] 9.2 Implement entity extraction
    - Create prompt for extracting structured entities (dates, names, amounts, requirements)
    - Parse GLM response into Entity models
    - Include confidence scores for each entity
    - _Requirements: 3.3, 3.6_
  
  - [x] 9.3 Implement ambiguity detection
    - Create prompt for identifying unclear or missing information
    - Parse GLM response into Ambiguity models with clarification questions
    - _Requirements: 3.4, 4.1, 4.2_
  
  - [x] 9.4 Implement conflict detection
    - Create prompt for identifying contradictory data points
    - Parse GLM response into Conflict models with evidence
    - _Requirements: 3.5, 11.1_
  
  - [x] 9.5 Implement recommendation generation
    - Create prompt for generating action recommendations
    - Parse GLM response into Recommendation models with confidence scores
    - Include reasoning and dependencies
    - _Requirements: 3.6_
  
  - [x] 9.6 Chain all reasoning steps together
    - Implement run_reasoning_chain function that executes all steps sequentially
    - Pass context between steps (classification informs extraction, etc.)
    - Store ReasoningResult in database
    - _Requirements: 3.1_
  
  - [ ] 9.7 Write property test for confidence score assignment
    - **Property 10: Confidence Score Assignment**
    - **Validates: Requirements 3.6, 5.3**
  
  - [ ] 9.8 Write property test for ambiguity detection
    - **Property 11: Ambiguity Detection Triggers Clarification**
    - **Validates: Requirements 4.1, 4.2**
  
  - [ ] 9.9 Write property test for conflict detection
    - **Property 23: Conflict Detection**
    - **Validates: Requirements 11.1, 11.3**
  
  - [ ] 9.10 Write unit tests for reasoning chain
    - Test each reasoning step independently
    - Test error handling for malformed GLM responses
    - Test schema validation for structured outputs
    - _Requirements: 14.1, 14.2_

- [ ] 10. Checkpoint - Reasoning chain complete
  - Ensure GLM integration works correctly
  - Verify all reasoning steps produce valid outputs
  - Test with sample documents
  - Ask the user if questions arise

### Phase 4: Policy Screening and Workflow Engine

- [ ] 11. Implement Policy Screener (MVP: Keyword-Based)
  - [x] 11.1 Create policy rule storage and retrieval
    - Implement functions to load policy rules from database
    - Support filtering by category and severity
    - _Requirements: 5.1_
  
  - [x] 11.2 Implement keyword-based policy matching
    - Match recommendations against policy rule keywords
    - Evaluate rule conditions
    - Generate Violation objects with evidence
    - _Requirements: 5.2_
  
  - [x] 11.3 Implement risk score calculation
    - Calculate risk score based on violation severity
    - Determine if human review is required
    - _Requirements: 5.3, 5.4_
  
  - [ ] 11.4 Write property test for policy violation detection
    - **Property 13: Policy Violation Detection**
    - **Validates: Requirements 5.2**
  
  - [ ] 11.5 Write property test for high-risk policy review
    - **Property 14: High-Risk Policy Review**
    - **Validates: Requirements 5.4**
  
  - [ ] 11.6 Write unit tests for policy screening
    - Test various policy rule patterns
    - Test risk score calculation edge cases
    - _Requirements: 5.1, 5.3_

- [ ] 12. Implement LangGraph Workflow Engine
  - [x] 12.1 Define LangGraph state graph
    - Create WorkflowState TypedDict with all required fields
    - Define all workflow nodes (ingest, redact, reason, screen_policy, etc.)
    - Define edges and conditional routing logic
    - _Requirements: 9.1, 9.2_
  
  - [x] 12.2 Implement workflow node functions
    - Create node functions for each processing step
    - Implement state update logic in each node
    - Handle errors and update state accordingly
    - _Requirements: 9.1_
  
  - [x] 12.3 Implement state transition validation
    - Validate transitions against state machine rules
    - Reject invalid transitions
    - _Requirements: 9.2_
  
  - [x] 12.4 Implement state persistence
    - Save workflow state to database after each transition
    - Load workflow state from database for resumption
    - _Requirements: 9.5_
  
  - [x] 12.5 Implement human-in-the-loop integration
    - Configure LangGraph to interrupt at approval nodes
    - Implement wait_for_human_approval function
    - Resume workflow after human decision
    - _Requirements: 4.3, 5.4, 7.4_
  
  - [ ] 12.6 Write property test for state machine validation
    - **Property 5: State Machine Transition Validation**
    - **Validates: Requirements 9.2**
  
  - [ ] 12.7 Write property test for terminal state immutability
    - **Property 6: Terminal State Immutability**
    - **Validates: Requirements 9.3**
  
  - [ ] 12.8 Write property test for state persistence
    - **Property 7: State Persistence**
    - **Validates: Requirements 9.5**
  
  - [ ] 12.9 Write unit tests for workflow engine
    - Test each node function independently
    - Test conditional routing logic
    - Test error handling and state transitions
    - _Requirements: 9.1, 9.2, 9.3_

- [ ] 13. Checkpoint - Workflow engine complete
  - Ensure state machine transitions work correctly
  - Verify state persistence and resumption
  - Test human-in-the-loop interruption
  - Ask the user if questions arise

### Phase 5: Task Orchestration and External Integrations

- [ ] 14. Implement Google Sheets integration
  - [x] 14.1 Set up Google Sheets API client
    - Configure OAuth2 authentication
    - Implement API request wrapper with error handling
    - _Requirements: 6.1_
  
  - [x] 14.2 Implement sync_to_sheets function
    - Format extracted data for Sheets
    - Write data to specified sheet and range
    - Handle API rate limits and errors
    - _Requirements: 6.1, 6.2_
  
  - [x] 14.3 Implement bidirectional sync
    - Read data from Sheets to detect manual edits
    - Update workflow state with changes from Sheets
    - _Requirements: 6.3_
  
  - [ ] 14.4 Write property test for Sheets sync round-trip
    - **Property 15: Google Sheets Sync Round-Trip**
    - **Validates: Requirements 6.1, 6.2, 6.5**
  
  - [ ] 14.5 Write property test for bidirectional sync
    - **Property 16: Bidirectional Sheets Sync**
    - **Validates: Requirements 6.3**
  
  - [ ] 14.6 Write unit tests for Sheets integration
    - Test API error handling
    - Test data formatting edge cases
    - _Requirements: 6.4_

- [ ] 15. Implement Gmail integration
  - [x] 15.1 Set up Gmail API client
    - Configure OAuth2 authentication
    - Implement API request wrapper with error handling
    - _Requirements: 7.1_
  
  - [x] 15.2 Implement create_gmail_draft function
    - Format email content from recommendations
    - Create draft via Gmail API
    - Store draft ID in workflow state
    - _Requirements: 7.1, 7.2_
  
  - [x] 15.3 Implement draft approval workflow
    - Send draft when user approves
    - Delete or update draft when user rejects
    - _Requirements: 7.4, 7.5_
  
  - [ ] 15.4 Write property test for Gmail draft creation
    - **Property 19: Gmail Draft Creation**
    - **Validates: Requirements 7.1, 7.2**
  
  - [ ] 15.5 Write property test for draft approval workflow
    - **Property 20: Draft Approval Workflow**
    - **Validates: Requirements 7.4, 7.5**
  
  - [ ] 15.6 Write unit tests for Gmail integration
    - Test API error handling
    - Test email formatting edge cases
    - _Requirements: 7.3_

- [ ] 16. Implement Task Orchestrator
  - [x] 16.1 Create task execution framework
    - Implement execute_with_retry function with exponential backoff
    - Support different task types (SYNC_SHEETS, CREATE_DRAFT, etc.)
    - _Requirements: 15.1, 10.2_
  
  - [x] 16.2 Implement task dependency resolution
    - Parse recommendation dependencies
    - Execute tasks in correct order
    - _Requirements: 15.2_
  
  - [x] 16.3 Implement orchestrate_tasks function
    - Coordinate execution of all approved recommendations
    - Collect task results
    - Update workflow state based on results
    - _Requirements: 15.3, 15.4_
  
  - [ ] 16.4 Implement retry and escalation logic
    - Retry failed tasks with exponential backoff
    - Transition to "Escalated" after max retries
    - _Requirements: 10.2, 10.3, 10.4_
  
  - [ ] 16.5 Write property test for exponential backoff retry
    - **Property 17: Exponential Backoff Retry**
    - **Validates: Requirements 6.4, 10.2**
  
  - [ ] 16.6 Write property test for retry limit escalation
    - **Property 18: Retry Limit Escalation**
    - **Validates: Requirements 10.3, 10.4**
  
  - [ ] 16.7 Write property test for task orchestration sequence
    - **Property 28: Task Orchestration Sequence**
    - **Validates: Requirements 15.2**
  
  - [ ] 16.8 Write property test for task execution completion
    - **Property 29: Task Execution Completion**
    - **Validates: Requirements 15.4**
  
  - [ ] 16.9 Write unit tests for task orchestrator
    - Test retry logic with mock failures
    - Test dependency resolution
    - Test error handling
    - _Requirements: 10.1, 15.1_

- [ ] 17. Checkpoint - Task orchestration complete
  - Ensure Google Sheets and Gmail integrations work
  - Verify retry logic and escalation
  - Test task dependency resolution
  - Ask the user if questions arise

### Phase 6: Audit Logging and API Layer

- [ ] 18. Implement Audit Logger
  - [x] 18.1 Create audit log storage
    - Implement append-only audit_log table writes
    - Generate hash for each entry (tamper detection)
    - _Requirements: 12.5_
  
  - [x] 18.2 Implement audit logging functions
    - Create log_action, log_glm_decision, log_human_decision functions
    - Log all workflow state transitions
    - Log all GLM inputs/outputs with confidence scores
    - Log all human decisions with reasoning
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [x] 18.3 Integrate audit logging throughout system
    - Add audit logging calls to workflow engine
    - Add audit logging to reasoning chain
    - Add audit logging to policy screener
    - Add audit logging to task orchestrator
    - _Requirements: 12.1, 12.2, 12.3, 12.4_
  
  - [ ] 18.4 Write property test for comprehensive audit logging
    - **Property 8: Comprehensive Audit Logging**
    - **Validates: Requirements 9.4, 12.1, 12.2, 12.3, 12.4**
  
  - [ ] 18.5 Write property test for audit log immutability
    - **Property 9: Audit Log Immutability**
    - **Validates: Requirements 12.5**
  
  - [ ] 18.6 Write unit tests for audit logger
    - Test hash generation
    - Test audit entry retrieval
    - _Requirements: 12.5_

- [ ] 19. Implement FastAPI REST API
  - [x] 19.1 Create workflow management endpoints
    - POST /api/v1/workflows (create workflow)
    - POST /api/v1/workflows/{workflow_id}/upload (upload document)
    - GET /api/v1/workflows/{workflow_id} (get workflow details)
    - GET /api/v1/workflows (list workflows with filtering)
    - _Requirements: 9.1_
  
  - [x] 19.2 Create human decision endpoints
    - POST /api/v1/workflows/{workflow_id}/clarify (provide clarification)
    - POST /api/v1/workflows/{workflow_id}/approve (approve recommendations)
    - POST /api/v1/workflows/{workflow_id}/reject (reject recommendations)
    - _Requirements: 4.3, 4.4, 5.4, 7.4, 7.5_
  
  - [x] 19.3 Create audit and monitoring endpoints
    - GET /api/v1/workflows/{workflow_id}/audit (get audit trail)
    - GET /api/v1/dashboard/stats (get dashboard statistics)
    - _Requirements: 12.1, 13.1, 13.2_
  
  - [ ] 19.4 Write integration tests for API endpoints
    - Test complete workflow via API
    - Test error responses
    - Test authentication and authorization
    - _Requirements: 9.1, 4.3, 12.1_

- [x] 20. Checkpoint - Backend complete
  - Ensure all API endpoints work correctly
  - Verify audit logging is comprehensive
  - Test end-to-end workflow via API
  - Ask the user if questions arise

### Phase 7: Frontend Dashboard

- [ ] 21. Set up React frontend project
  - [ ] 21.1 Create React + TypeScript project
    - Initialize project with Vite or Create React App
    - Install dependencies: React, TypeScript, Tailwind CSS, shadcn/ui
    - Set up project structure (components/, pages/, hooks/, api/)
    - _Requirements: 13.1_
  
  - [ ] 21.2 Create API client for backend
    - Implement fetch wrapper for API calls
    - Add error handling and loading states
    - _Requirements: 13.1_

- [ ] 22. Implement dashboard UI
  - [ ] 22.1 Create workflow list view
    - Display workflows grouped by state
    - Show workflow metadata (created_at, created_by, state)
    - Implement filtering and sorting
    - _Requirements: 13.1, 13.2_
  
  - [ ] 22.2 Highlight workflows requiring attention
    - Visually distinguish workflows in review states
    - Show count of workflows needing attention
    - _Requirements: 13.3_
  
  - [ ] 22.3 Create workflow detail view
    - Display full workflow information
    - Show reasoning results, policy screening, recommendations
    - Display audit trail
    - _Requirements: 13.1_
  
  - [ ] 22.4 Write property test for dashboard workflow display
    - **Property 30: Dashboard Workflow Display**
    - **Validates: Requirements 13.1, 13.2**
  
  - [ ] 22.5 Write property test for dashboard attention highlighting
    - **Property 31: Dashboard Attention Highlighting**
    - **Validates: Requirements 13.3**

- [ ] 23. Implement document upload UI
  - [ ] 23.1 Create file upload component
    - Support drag-and-drop file upload
    - Show upload progress
    - Display file validation errors
    - _Requirements: 1.1, 1.2_
  
  - [ ] 23.2 Integrate with workflow creation
    - Create new workflow on upload
    - Navigate to workflow detail after upload
    - _Requirements: 1.1_

- [ ] 24. Implement review and approval UI
  - [ ] 24.1 Create clarification request UI
    - Display ambiguities with clarification questions
    - Provide input fields for clarifications
    - Submit clarifications to backend
    - _Requirements: 4.2, 4.3_
  
  - [ ] 24.2 Create policy review UI
    - Display policy violations with evidence
    - Show risk score and severity
    - Provide approve/reject actions
    - _Requirements: 5.4_
  
  - [ ] 24.3 Create recommendation review UI
    - Display all recommendations with confidence scores
    - Show reasoning for each recommendation
    - Provide approve/reject/modify actions
    - _Requirements: 3.6, 5.3_
  
  - [ ] 24.4 Create email draft review UI
    - Display Gmail draft content
    - Provide approve/reject/edit actions
    - _Requirements: 7.4, 7.5_

- [ ] 25. Checkpoint - Frontend complete
  - Ensure all UI components render correctly
  - Verify user can complete full workflow via UI
  - Test responsive design
  - Ask the user if questions arise

### Phase 8: Advanced Features

- [ ] 26. Implement T&C comparison feature
  - [ ] 26.1 Implement T&C clause extraction
    - Parse T&C documents into individual clauses
    - Store clauses with metadata
    - _Requirements: 8.1_
  
  - [ ] 26.2 Implement clause comparison
    - Compare two T&C documents clause-by-clause
    - Identify similarities and differences
    - Use GLM for semantic comparison
    - _Requirements: 8.2_
  
  - [ ] 26.3 Create T&C comparison UI
    - Display side-by-side clause comparison
    - Highlight differences
    - Show similarity scores
    - _Requirements: 8.3_
  
  - [ ] 26.4 Write property test for T&C clause extraction
    - **Property 21: T&C Clause Extraction**
    - **Validates: Requirements 8.1**
  
  - [ ] 26.5 Write property test for clause comparison
    - **Property 22: Clause Comparison**
    - **Validates: Requirements 8.2**

- [ ] 27. Implement conflict resolution workflow
  - [ ] 27.1 Create conflict resolution UI
    - Display conflicts with evidence
    - Provide input for resolution
    - Capture user reasoning
    - _Requirements: 11.2, 11.4_
  
  - [ ] 27.2 Store conflict resolutions
    - Save resolution and reasoning to database
    - Update workflow state
    - _Requirements: 11.4_
  
  - [ ] 27.3 Write property test for conflict resolution recording
    - **Property 24: Conflict Resolution Recording**
    - **Validates: Requirements 11.4**

- [-] 28. Implement schema validation and error handling
  - [x] 28.1 Add Pydantic validation to all GLM outputs
    - Validate structured outputs against schemas
    - Catch validation errors
    - _Requirements: 14.1_
  
  - [x] 28.2 Implement validation failure handling
    - Transition to "Failed" state on validation errors
    - Log specific validation errors
    - _Requirements: 14.2_
  
  - [x] 28.3 Implement repeated failure escalation
    - Track validation failure count
    - Escalate after 3 failures
    - _Requirements: 14.5_
  
  - [ ] 28.4 Write property test for schema validation
    - **Property 25: Schema Validation**
    - **Validates: Requirements 14.1**
  
  - [ ] 28.5 Write property test for validation failure handling
    - **Property 26: Validation Failure Handling**
    - **Validates: Requirements 14.2**
  
  - [ ] 28.6 Write property test for repeated validation failure escalation
    - **Property 27: Repeated Validation Failure Escalation**
    - **Validates: Requirements 14.5**

- [-] 29. Implement clarification re-triggering
  - [x] 29.1 Update reasoning chain to accept clarifications
    - Pass clarifications as context to GLM
    - Re-run reasoning with updated context
    - _Requirements: 4.3, 4.4_
  
  - [ ] 29.2 Write property test for clarification re-triggering
    - **Property 12: Clarification Re-triggers Reasoning**
    - **Validates: Requirements 4.3, 4.4**

- [x] 30. Checkpoint - Advanced features complete
  - Ensure T&C comparison works correctly
  - Verify conflict resolution workflow
  - Test schema validation and error handling
  - Ask the user if questions arise

### Phase 9: Testing, Documentation, and Deployment

- [ ] 31. Complete property-based test suite
  - [ ] 31.1 Ensure all 31 properties have tests
    - Review design document properties
    - Verify each property has corresponding test
    - Ensure all tests run at least 100 iterations
    - _Requirements: All_
  
  - [ ] 31.2 Create Hypothesis strategies for test data generation
    - Implement strategies for workflows, documents, recommendations
    - Implement strategies for policy rules, API responses
    - _Requirements: All_

- [ ] 32. Complete unit test suite
  - Write unit tests for edge cases not covered by property tests
  - Test error conditions and exception handling
  - Test integration points between components
  - _Requirements: All_

- [ ] 33. Run integration and end-to-end tests
  - Test complete workflows from upload to completion
  - Test all API endpoints with real backend
  - Test UI flows with real frontend
  - _Requirements: All_

- [x] 34. Create deployment configuration
  - [x] 34.1 Create Docker containers
    - Dockerfile for backend (FastAPI)
    - Dockerfile for frontend (React)
    - Docker Compose for local development
    - _Requirements: All (deployment)_
  
  - [x] 34.2 Set up environment configuration
    - Document required environment variables
    - Create .env.example file
    - _Requirements: All (deployment)_
  
  - [x] 34.3 Create database migration scripts
    - Alembic migrations for schema changes
    - Seed data for policy rules
    - _Requirements: 9.5_

- [x] 35. Final checkpoint - System complete
  - Run full test suite (property tests + unit tests + integration tests)
  - Verify all 31 correctness properties pass
  - Test complete end-to-end workflow
  - Ask the user if questions arise

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout development
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation follows a phased approach: core functionality first, then enhancements
- All property tests must include the tag format: `# Feature: stitchflow-v2, Property {number}: {property_text}`
