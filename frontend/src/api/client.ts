const API_BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || res.statusText)
  }
  return res.json()
}

// ── Types ──

export interface WorkflowSummary {
  workflow_id: string
  state: string
  created_at: string
  created_by: string
}

export interface WorkflowDetail extends WorkflowSummary {
  updated_at: string
  document_path: string | null
  metadata: Record<string, unknown> | null
}

export interface DashboardStats {
  total_workflows: number
  workflows_by_state: Record<string, number>
  workflows_needing_attention: number
  completion_rate: number
  failure_rate: number
  workflows_by_creator: Record<string, number>
  recent_workflows: WorkflowSummary[]
}

export interface CreateWorkflowResponse {
  workflow_id: string
  name: string
  status: string
  created_at: string
}

export interface UploadResponse {
  workflow_id: string
  state: string
  extraction_result: {
    extracted_text: string
    file_type: string
    file_size: number
    success: boolean
  }
}

export interface Conflict {
  conflict_type: string
  description: string
  evidence: string[]
  conflicting_entities: { entity_type: string; value: string; confidence: number; source_text: string; metadata?: Record<string, unknown> }[]
}

export interface PIIMatch {
  pii_type: string
  masked_token: string
  original_value: string
  start_pos?: number
  end_pos?: number
}

export interface RedactionResponse {
  workflow_id: string
  state: string
  pii_found: number
  pii_by_type: Record<string, number>
  pii_matches: PIIMatch[]
  redaction_time?: number
  redacted_text_preview?: string
}

export interface ReasoningResponse {
  workflow_id: string
  state: string
  classification: { document_type: string; intent: string; confidence: number }
  entities_found: number
  entities: { type: string; value: string; confidence: number }[]
  ambiguities_found: number
  ambiguities: { type: string; description: string; question: string; possible_interpretations?: string[] }[]
  conflicts_found: number
  conflicts: Conflict[]
  recommendations_generated: number
  recommendations: { id: string; action: string; description: string; confidence: number }[]
  reasoning_time: number
}

export interface PolicyScreeningResponse {
  workflow_id: string
  state: string
  violations_found: number
  violations: { rule_name: string; severity: string; description: string; evidence: string[] }[]
  risk_score: number
  requires_human_review: boolean
  screening_time: number
}

export interface AuditEntry {
  entry_id: string
  timestamp: string
  action_type: string
  actor: string
  details: Record<string, unknown>
  hash: string
}

export interface GeneratedDocument {
  title: string
  executive_summary: string
  classification: string
  key_findings: string[]
  issues_resolved?: string[]
  recommendations_summary: string[]
  draft_email: { subject: string; body: string }
  next_steps: string[]
}

export interface ExecutionResultsResponse {
  workflow_id: string
  state: string
  document: GeneratedDocument
}

export interface ListWorkflowsResponse {
  workflows: WorkflowSummary[]
  total: number
  limit: number
  offset: number
}

export interface TCCompareClause {
  clause_id: string
  content: string
}

export interface TCCompareResult {
  clause_a_id: string
  clause_b_id: string | null
  classification: 'precedent' | 'ai_generated' | 'needs_review' | 'identical' | 'unique_a' | 'unique_b'
  similarity_score: number
  summary: string
}

export interface TCCompareResponse {
  workflow_a: { workflow_id: string; clause_count: number; clauses: TCCompareClause[] }
  workflow_b: { workflow_id: string; clause_count: number; clauses: TCCompareClause[] }
  comparisons: TCCompareResult[]
  total_comparisons: number
}

// ── API Calls ──

export const api = {
  createWorkflow: (name: string, description = '') =>
    request<CreateWorkflowResponse>('/workflows', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    }),

  listWorkflows: (params?: { state?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams()
    if (params?.state) search.set('state', params.state)
    if (params?.limit) search.set('limit', String(params.limit))
    if (params?.offset) search.set('offset', String(params.offset))
    const qs = search.toString()
    return request<ListWorkflowsResponse>(`/workflows${qs ? `?${qs}` : ''}`)
  },

  getWorkflow: (id: string) =>
    request<WorkflowDetail>(`/workflows/${id}`),

  uploadDocument: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<UploadResponse>(`/workflows/${id}/upload`, {
      method: 'POST',
      headers: {},
      body: form,
    })
  },

  redact: (id: string) =>
    request<RedactionResponse>(
      `/workflows/${id}/redact`,
      { method: 'POST' },
    ),

  getRedactionResults: (id: string) =>
    request<RedactionResponse>(`/workflows/${id}/redact`, { method: 'GET' }),

  reason: (id: string) =>
    request<ReasoningResponse>(`/workflows/${id}/reason`, { method: 'POST' }),

  getReasoningResults: (id: string) =>
    request<ReasoningResponse>(`/workflows/${id}/reason`, { method: 'GET' }),

  screenPolicy: (id: string) =>
    request<PolicyScreeningResponse>(`/workflows/${id}/screen`, { method: 'POST' }),

  getPolicyScreeningResults: (id: string) =>
    request<PolicyScreeningResponse>(`/workflows/${id}/screen`, { method: 'GET' }),

  runWorkflow: (id: string) =>
    request<{ workflow_id: string; final_state: string; requires_human_input: boolean; execution_log: string[] }>(
      `/workflows/${id}/run`,
      { method: 'POST' },
    ),

  clarify: (id: string, userId: string, clarifications: { ambiguity_id: string; answer: string }[], reasoning?: string) =>
    request<{ workflow_id: string; status: string; message: string }>(
      `/workflows/${id}/clarify`,
      {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, clarifications, reasoning }),
      },
    ),

  approve: (id: string, userId: string, approvedRecs: string[], modifications?: Record<string, unknown>, reasoning?: string) =>
    request<{ workflow_id: string; status: string; approved_count: number }>(
      `/workflows/${id}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, approved_recommendations: approvedRecs, modifications, reasoning }),
      },
    ),

  reject: (id: string, userId: string, rejectedRecs: string[], rejectionReasons: Record<string, string>, reasoning?: string) =>
    request<{ workflow_id: string; status: string; rejected_count: number }>(
      `/workflows/${id}/reject`,
      {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, rejected_recommendations: rejectedRecs, rejection_reasons: rejectionReasons, reasoning }),
      },
    ),

  getAuditTrail: (id: string, params?: { action_type?: string; actor?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.action_type) search.set('action_type', params.action_type)
    if (params?.actor) search.set('actor', params.actor)
    if (params?.limit) search.set('limit', String(params.limit))
    const qs = search.toString()
    return request<{ workflow_id: string; total_entries: number; entries: AuditEntry[] }>(
      `/workflows/${id}/audit${qs ? `?${qs}` : ''}`,
    )
  },

  execute: (id: string) =>
    request<{
      workflow_id: string
      state: string
      overall_success: boolean
      total_tasks: number
      successful_tasks: number
      failed_tasks: number
      task_results: { task_id: string; task_type: string; success: boolean; result_data: Record<string, unknown>; error: string | null; execution_time: number }[]
    }>(
      `/workflows/${id}/execute`,
      { method: 'POST' },
    ),

  getExecutionResults: (id: string) =>
    request<ExecutionResultsResponse>(`/workflows/${id}/execute`, { method: 'GET' }),

  getDashboardStats: () =>
    request<DashboardStats>('/dashboard/stats'),

  compareTC: (workflowIdA: string, workflowIdB: string) =>
    request<TCCompareResponse>('/workflows/tc-compare', {
      method: 'POST',
      body: JSON.stringify({ workflow_id_a: workflowIdA, workflow_id_b: workflowIdB }),
    }),
}
