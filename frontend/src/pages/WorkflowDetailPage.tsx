import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  api,
  type WorkflowDetail,
  type AuditEntry,
  type ReasoningResponse,
  type PolicyScreeningResponse,
} from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import FileUpload from '@/components/FileUpload'
import ClarificationPanel from '@/components/ClarificationPanel'
import PolicyReviewPanel from '@/components/PolicyReviewPanel'
import RecommendationReviewPanel from '@/components/RecommendationReviewPanel'
import DraftReviewPanel from '@/components/DraftReviewPanel'
import ConflictResolutionPanel from '@/components/ConflictResolutionPanel'

const ATTENTION_STATES = ['NeedsClarification', 'PolicyReviewRequired', 'ReadyForReview', 'DraftReady', 'Escalated']

function stateColor(state: string) {
  if (state === 'Completed') return 'bg-green-100 text-green-800'
  if (state === 'Failed' || state === 'Escalated') return 'bg-red-100 text-red-800'
  if (ATTENTION_STATES.includes(state)) return 'bg-yellow-100 text-yellow-800'
  if (state === 'Approved' || state === 'Executed') return 'bg-blue-100 text-blue-800'
  return 'bg-slate-100 text-slate-800'
}

function stateLabel(state: string) {
  return state.replace(/([A-Z])/g, ' $1').trim()
}

function confidenceBadge(confidence: number) {
  const pct = Math.round(confidence * 100)
  if (pct >= 80) return <Badge className="bg-green-100 text-green-800">{pct}%</Badge>
  if (pct >= 50) return <Badge className="bg-yellow-100 text-yellow-800">{pct}%</Badge>
  return <Badge className="bg-red-100 text-red-800">{pct}%</Badge>
}

function severityColor(severity: string) {
  if (severity === 'critical') return 'bg-red-100 text-red-800'
  if (severity === 'high') return 'bg-orange-100 text-orange-800'
  if (severity === 'medium') return 'bg-yellow-100 text-yellow-800'
  return 'bg-slate-100 text-slate-800'
}

export default function WorkflowDetailPage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const navigate = useNavigate()

  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [reasoning, setReasoning] = useState<ReasoningResponse | null>(null)
  const [policy, setPolicy] = useState<PolicyScreeningResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  // Warn user before leaving if action is in progress
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (actionLoading) {
        e.preventDefault()
        e.returnValue = 'AI reasoning is still processing. You can leave and it will continue in the background.'
        return e.returnValue
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [actionLoading])

  const load = useCallback(async () => {
    if (!workflowId) return
    
    const abortController = new AbortController()
    
    try {
      const [wf, auditData] = await Promise.all([
        api.getWorkflow(workflowId),
        api.getAuditTrail(workflowId),
      ])
      
      // Check if component is still mounted
      if (abortController.signal.aborted) return
      
      setWorkflow(wf)
      setAudit(auditData.entries)
      
      // Auto-fetch reasoning results if workflow has been through reasoning
      const reasoningStates = ['Parsed', 'NeedsClarification', 'PolicyReviewRequired', 'ReadyForReview', 'DraftReady', 'Approved', 'Executed', 'Completed']
      if (reasoningStates.includes(wf.state)) {
        try {
          // Fetch reasoning results from backend (GET endpoint)
          const reasoningResult = await api.getReasoningResults(workflowId)
          if (!abortController.signal.aborted) {
            setReasoning(reasoningResult)
          }
        } catch (err) {
          // Reasoning results might not exist yet, that's okay
          console.log('No reasoning results available yet')
        }
      }
      
      // Auto-fetch policy screening results if workflow has been through policy screening
      const policyStates = ['PolicyReviewRequired', 'ReadyForReview', 'DraftReady', 'Approved', 'Executed', 'Completed']
      if (policyStates.includes(wf.state)) {
        try {
          // Fetch policy screening results from backend (GET endpoint)
          const policyResult = await api.getPolicyScreeningResults(workflowId)
          if (!abortController.signal.aborted) {
            setPolicy(policyResult)
          }
        } catch (err) {
          // Policy results might not exist yet, that's okay
          console.log('No policy screening results available yet')
        }
      }
    } catch (e) {
      if (!abortController.signal.aborted) {
        setError(e instanceof Error ? e.message : 'Failed to load workflow')
      }
    } finally {
      if (!abortController.signal.aborted) {
        setLoading(false)
      }
    }
    
    return () => abortController.abort()
  }, [workflowId])

  useEffect(() => {
    const cleanup = load()
    return () => {
      if (cleanup) cleanup.then(fn => fn?.())
    }
  }, [load])

  async function handleRunStep(step: 'redact' | 'reason' | 'screen' | 'run') {
    if (!workflowId) return
    setActionLoading(true)
    setError(null)  // Clear any previous errors
    
    let isCancelled = false
    
    try {
      if (step === 'redact') {
        await api.redact(workflowId)
      } else if (step === 'reason') {
        // Show a message that this might take a while
        console.log('[Frontend] Running AI reasoning - this may take up to 2 minutes...')
        const result = await api.reason(workflowId)
        if (!isCancelled) {
          setReasoning(result)
        }
      } else if (step === 'screen') {
        const result = await api.screenPolicy(workflowId)
        if (!isCancelled) {
          setPolicy(result)
        }
      } else if (step === 'run') {
        console.log('[Frontend] Running full pipeline - this may take several minutes...')
        await api.runWorkflow(workflowId)
      }
      
      if (!isCancelled) {
        await load()
      }
    } catch (e) {
      if (!isCancelled) {
        const errorMessage = e instanceof Error ? e.message : 'Action failed'
        console.error('[Frontend] Action failed:', errorMessage)
        setError(errorMessage)
        alert(`Error: ${errorMessage}\n\nPlease check the backend logs for more details.`)
      }
    } finally {
      if (!isCancelled) {
        setActionLoading(false)
      }
    }
    
    // Return cleanup function
    return () => {
      isCancelled = true
    }
  }

  async function handleUpload(file: File) {
    if (!workflowId) return
    setUploading(true)
    setUploadError(null)
    try {
      await api.uploadDocument(workflowId, file)
      await load()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground text-lg">Loading workflow...</p>
      </div>
    )
  }

  if (error || !workflow) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-destructive text-lg">{error ?? 'Workflow not found'}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4">
          <Button 
            variant="ghost" 
            onClick={() => {
              if (actionLoading) {
                const confirmed = window.confirm(
                  'AI reasoning is still processing in the background. You can go back to the dashboard and check the results later. Continue?'
                )
                if (!confirmed) return
              }
              // Navigate immediately - don't wait for pending requests
              navigate('/', { replace: true })
            }}
          >
            &larr; Back
          </Button>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold tracking-tight truncate">
              Workflow {workflowId!.slice(0, 8)}...
            </h1>
            <p className="text-sm text-muted-foreground">Created by {workflow.created_by}</p>
          </div>
          <Badge className={stateColor(workflow.state)}>{stateLabel(workflow.state)}</Badge>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Workflow Info */}
        <Card>
          <CardHeader>
            <CardTitle>Workflow Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="grid grid-cols-2 gap-x-8 gap-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">ID</span>
                <span className="font-mono">{workflowId!.slice(0, 12)}...</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">State</span>
                <Badge className={stateColor(workflow.state)}>{stateLabel(workflow.state)}</Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{new Date(workflow.created_at).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span>{new Date(workflow.updated_at).toLocaleString()}</span>
              </div>
              <div className="flex justify-between col-span-2">
                <span className="text-muted-foreground">Document</span>
                <span className="truncate max-w-md">{workflow.document_path ?? 'No document uploaded'}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
          </CardHeader>
          <CardContent>
            {actionLoading && (
              <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                  <div>
                    <p className="text-sm font-medium text-blue-900">Processing...</p>
                    <p className="text-xs text-blue-700">AI reasoning may take 1-2 minutes. Please wait...</p>
                  </div>
                </div>
              </div>
            )}
            {error && (
              <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm font-medium text-red-900">Error</p>
                <p className="text-xs text-red-700">{error}</p>
              </div>
            )}
            <div className="flex flex-wrap gap-3">
              {workflow.state === 'New' && (
                <FileUpload onFileSelected={handleUpload} uploading={uploading} error={uploadError} />
              )}
              {workflow.state === 'Ingested' && (
                <Button onClick={() => handleRunStep('redact')} disabled={actionLoading}>
                  Redact PII
                </Button>
              )}
              {workflow.state === 'Redacted' && (
                <Button onClick={() => handleRunStep('reason')} disabled={actionLoading}>
                  {actionLoading ? 'Running AI Reasoning...' : 'Run AI Reasoning'}
                </Button>
              )}
              {workflow.state === 'Parsed' && (
                <Button onClick={() => handleRunStep('screen')} disabled={actionLoading}>
                  Screen Policy
                </Button>
              )}
              {workflow.state === 'Approved' && (
                <Button onClick={() => handleRunStep('run')} disabled={actionLoading}>
                  Execute Tasks
                </Button>
              )}
              <Button variant="outline" onClick={() => handleRunStep('run')} disabled={actionLoading}>
                {actionLoading ? 'Running Pipeline...' : 'Run Full Pipeline'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Clarification Panel (NeedsClarification state) */}
        {workflow.state === 'NeedsClarification' && reasoning && (
          <>
            <ConflictResolutionPanel
              workflowId={workflowId!}
              reasoning={reasoning}
              onActionComplete={load}
            />
            <ClarificationPanel
              workflowId={workflowId!}
              reasoning={reasoning}
              onActionComplete={load}
            />
          </>
        )}

        {/* Policy Review Panel (PolicyReviewRequired state) */}
        {workflow.state === 'PolicyReviewRequired' && policy && (
          <PolicyReviewPanel
            workflowId={workflowId!}
            policy={policy}
            onActionComplete={load}
          />
        )}

        {/* Recommendation Review Panel (ReadyForReview state) */}
        {workflow.state === 'ReadyForReview' && reasoning && (
          <RecommendationReviewPanel
            workflowId={workflowId!}
            reasoning={reasoning}
            onActionComplete={load}
          />
        )}

        {/* Draft Review Panel (DraftReady state) */}
        {workflow.state === 'DraftReady' && (
          <DraftReviewPanel
            workflowId={workflowId!}
            metadata={workflow.metadata}
            onActionComplete={load}
          />
        )}

        {/* Reasoning / Policy / Audit Tabs */}
        <Card>
          <CardContent className="pt-6">
            <Tabs defaultValue="reasoning">
              <TabsList>
                <TabsTrigger value="reasoning">
                  AI Reasoning {reasoning ? `(${reasoning.entities_found} entities)` : ''}
                </TabsTrigger>
                <TabsTrigger value="policy">
                  Policy Screening {policy ? `(${policy.violations_found} violations)` : ''}
                </TabsTrigger>
                <TabsTrigger value="audit">
                  Audit Trail ({audit.length})
                </TabsTrigger>
              </TabsList>

              {/* Tab: AI Reasoning */}
              <TabsContent value="reasoning" className="space-y-4">
                {!reasoning ? (
                  <p className="text-muted-foreground text-sm py-4">
                    No reasoning results yet. Run AI reasoning to see analysis.
                  </p>
                ) : (
                  <>
                    {/* Classification */}
                    <div>
                      <h3 className="text-sm font-semibold mb-2">Classification</h3>
                      <div className="flex items-center gap-3 bg-slate-50 rounded-lg p-3">
                        <Badge variant="outline">{reasoning.classification.document_type}</Badge>
                        <span className="text-sm">{reasoning.classification.intent}</span>
                        {confidenceBadge(reasoning.classification.confidence)}
                      </div>
                    </div>

                    {/* Entities */}
                    <div>
                      <h3 className="text-sm font-semibold mb-2">
                        Extracted Entities ({reasoning.entities_found})
                      </h3>
                      {reasoning.entities.length === 0 ? (
                        <p className="text-muted-foreground text-sm">No entities extracted.</p>
                      ) : (
                        <div className="space-y-1">
                          {reasoning.entities.map((e, i) => (
                            <div key={i} className="flex items-center gap-3 text-sm py-1.5 px-3 bg-slate-50 rounded">
                              <Badge variant="outline" className="shrink-0">{e.type}</Badge>
                              <span className="truncate">{e.value}</span>
                              {confidenceBadge(e.confidence)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Ambiguities */}
                    {reasoning.ambiguities_found > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2">
                          Ambiguities ({reasoning.ambiguities_found})
                        </h3>
                        <div className="space-y-2">
                          {reasoning.ambiguities.map((a, i) => (
                            <div key={i} className="border-l-4 border-yellow-400 pl-3 py-2 text-sm">
                              <p className="font-medium text-yellow-800">{a.type}</p>
                              <p>{a.description}</p>
                              <p className="text-muted-foreground mt-1">Q: {a.question}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    <div>
                      <h3 className="text-sm font-semibold mb-2">
                        Recommendations ({reasoning.recommendations_generated})
                      </h3>
                      {reasoning.recommendations.length === 0 ? (
                        <p className="text-muted-foreground text-sm">No recommendations generated.</p>
                      ) : (
                        <div className="space-y-2">
                          {reasoning.recommendations.map((r) => (
                            <div key={r.id} className="flex items-start gap-3 text-sm border rounded-lg p-3">
                              <Badge variant="outline" className="shrink-0">{r.action}</Badge>
                              <div className="flex-1 min-w-0">
                                <p className="truncate">{r.description}</p>
                              </div>
                              {confidenceBadge(r.confidence)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Timing */}
                    <p className="text-xs text-muted-foreground">
                      Reasoning completed in {reasoning.reasoning_time.toFixed(2)}s
                    </p>
                  </>
                )}
              </TabsContent>

              {/* Tab: Policy Screening */}
              <TabsContent value="policy" className="space-y-4">
                {!policy ? (
                  <p className="text-muted-foreground text-sm py-4">
                    No policy screening results yet. Run policy screening to see violations.
                  </p>
                ) : (
                  <>
                    {/* Risk Summary */}
                    <div className="flex items-center gap-4 bg-slate-50 rounded-lg p-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Risk Score</p>
                        <p className="text-2xl font-bold">{(policy.risk_score * 100).toFixed(0)}%</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Human Review</p>
                        <Badge className={policy.requires_human_review ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}>
                          {policy.requires_human_review ? 'Required' : 'Not Required'}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Violations</p>
                        <p className="text-2xl font-bold">{policy.violations_found}</p>
                      </div>
                    </div>

                    {/* Violations List */}
                    {policy.violations.length === 0 ? (
                      <p className="text-muted-foreground text-sm">No policy violations detected.</p>
                    ) : (
                      <div className="space-y-3">
                        {policy.violations.map((v, i) => (
                          <div key={i} className="border rounded-lg p-3 space-y-1">
                            <div className="flex items-center gap-2">
                              <Badge className={severityColor(v.severity)}>{v.severity}</Badge>
                              <span className="text-sm font-semibold">{v.rule_name}</span>
                            </div>
                            <p className="text-sm">{v.description}</p>
                            {v.evidence.length > 0 && (
                              <div className="text-xs text-muted-foreground space-y-0.5">
                                {v.evidence.map((e, j) => (
                                  <p key={j}>{e}</p>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    <p className="text-xs text-muted-foreground">
                      Screening completed in {policy.screening_time.toFixed(2)}s
                    </p>
                  </>
                )}
              </TabsContent>

              {/* Tab: Audit Trail */}
              <TabsContent value="audit">
                {audit.length === 0 ? (
                  <p className="text-muted-foreground text-sm py-4">No audit entries yet.</p>
                ) : (
                  <div className="space-y-3">
                    {audit.map((entry) => {
                      // Format action type to human-readable
                      const actionLabel = entry.action_type
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (l) => l.toUpperCase())
                      
                      // Format actor
                      const actorLabel = entry.actor === 'system' 
                        ? '🤖 System' 
                        : entry.actor === 'glm' 
                        ? '🧠 AI Agent' 
                        : `👤 ${entry.actor}`
                      
                      // Generate human-readable description
                      let description = ''
                      const details = entry.details || {}
                      
                      if (entry.action_type === 'state_transition') {
                        description = `Workflow moved from "${details.from_state}" to "${details.to_state}"`
                        if (details.reason) {
                          description += `. Reason: ${details.reason}`
                        }
                      } else if (entry.action_type === 'glm_decision') {
                        description = `AI made a decision`
                        if (details.decision_type) {
                          description += `: ${details.decision_type}`
                        }
                      } else if (entry.action_type === 'human_decision') {
                        description = `User made a decision: ${details.decision_type || 'unknown'}`
                        if (details.reasoning) {
                          description += `. Reasoning: ${details.reasoning}`
                        }
                      } else if (entry.action_type === 'policy_check') {
                        description = `Policy screening completed`
                        if (details.violations_found !== undefined) {
                          description += `. Found ${details.violations_found} violation(s)`
                        }
                      } else if (entry.action_type === 'task_execution') {
                        description = `Task executed: ${details.task_type || 'unknown'}`
                        if (details.success !== undefined) {
                          description += details.success ? ' (Success)' : ' (Failed)'
                        }
                      } else if (entry.action_type === 'workflow_paused') {
                        description = `Workflow paused: ${details.reason || 'waiting for human input'}`
                      } else if (entry.action_type === 'workflow_completed') {
                        description = `Workflow completed with state: ${details.final_state}`
                      } else if (entry.action_type === 'workflow_failed') {
                        description = `Workflow failed: ${details.error || 'unknown error'}`
                      } else {
                        description = actionLabel
                      }
                      
                      return (
                        <div key={entry.entry_id} className="border rounded-lg p-4 hover:bg-slate-50 transition-colors">
                          {/* Header */}
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <Badge variant="outline" className="text-xs shrink-0">
                                  {actionLabel}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  {new Date(entry.timestamp).toLocaleString()}
                                </span>
                              </div>
                              <p className="text-sm font-medium">{description}</p>
                            </div>
                            <span className="text-xs text-muted-foreground shrink-0">{actorLabel}</span>
                          </div>
                          
                          {/* Additional Details (expandable) */}
                          {Object.keys(details).length > 0 && (
                            <details className="mt-2">
                              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                                Show technical details
                              </summary>
                              <pre className="text-xs text-muted-foreground bg-slate-50 rounded p-2 mt-1 overflow-x-auto">
                                {JSON.stringify(details, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
