import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type TCCompareResponse, type WorkflowSummary } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const CLASSIFICATION_COLORS: Record<string, string> = {
  precedent: 'bg-green-100 text-green-800 border-green-300',
  ai_generated: 'bg-blue-100 text-blue-800 border-blue-300',
  needs_review: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  identical: 'bg-slate-100 text-slate-600 border-slate-300',
  unique_a: 'bg-purple-100 text-purple-800 border-purple-300',
  unique_b: 'bg-orange-100 text-orange-800 border-orange-300',
}

const CLASSIFICATION_LABELS: Record<string, string> = {
  precedent: 'Precedent',
  ai_generated: 'AI Generated',
  needs_review: 'Needs Review',
  identical: 'Identical',
  unique_a: 'Only in Doc A',
  unique_b: 'Only in Doc B',
}

export default function TCComparePage() {
  const navigate = useNavigate()
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [selectedA, setSelectedA] = useState('')
  const [selectedB, setSelectedB] = useState('')
  const [result, setResult] = useState<TCCompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [workflowsLoaded, setWorkflowsLoaded] = useState(false)

  async function loadWorkflows() {
    try {
      const data = await api.listWorkflows({ limit: 100 })
      setWorkflows(data.workflows.filter((w) => w.state !== 'New'))
      setWorkflowsLoaded(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load workflows')
    }
  }

  if (!workflowsLoaded) {
    loadWorkflows()
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Loading workflows...</p>
      </div>
    )
  }

  async function handleCompare() {
    if (!selectedA || !selectedB) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.compareTC(selectedA, selectedB)
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Comparison failed')
    } finally {
      setLoading(false)
    }
  }

  // Build clause lookup maps
  const clausesA = new Map((result?.workflow_a.clauses ?? []).map((c) => [c.clause_id, c.content]))
  const clausesB = new Map((result?.workflow_b.clauses ?? []).map((c) => [c.clause_id, c.content]))

  // Stats
  const stats = result?.comparisons.reduce(
    (acc, c) => {
      acc[c.classification] = (acc[c.classification] || 0) + 1
      return acc
    },
    {} as Record<string, number>,
  )

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/')}>&larr; Back</Button>
          <h1 className="text-xl font-bold tracking-tight">T&C Comparison</h1>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Document Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Select Documents to Compare</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Document A</label>
                <select
                  value={selectedA}
                  onChange={(e) => setSelectedA(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select workflow...</option>
                  {workflows.map((w) => (
                    <option key={w.workflow_id} value={w.workflow_id}>
                      {w.workflow_id.slice(0, 8)}... — {w.created_by} ({w.state})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5">Document B</label>
                <select
                  value={selectedB}
                  onChange={(e) => setSelectedB(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">Select workflow...</option>
                  {workflows.map((w) => (
                    <option key={w.workflow_id} value={w.workflow_id}>
                      {w.workflow_id.slice(0, 8)}... — {w.created_by} ({w.state})
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleCompare} disabled={!selectedA || !selectedB || loading}>
                {loading ? 'Comparing...' : 'Compare Documents'}
              </Button>
            </div>
            {error && <p className="text-sm text-destructive mt-2">{error}</p>}
          </CardContent>
        </Card>

        {/* Legend */}
        <Card>
          <CardContent className="pt-4">
            <div className="flex flex-wrap gap-3">
              {Object.entries(CLASSIFICATION_LABELS).map(([key, label]) => (
                <div key={key} className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border ${CLASSIFICATION_COLORS[key]}`}>
                  <span>{label}</span>
                  {stats?.[key] !== undefined && <span className="font-bold">({stats[key]})</span>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Comparison Results */}
        {result && (
          <Card>
            <CardHeader>
              <CardTitle>
                Comparison Results ({result.total_comparisons} clauses)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {result.comparisons.map((comp, i) => {
                  const contentA = clausesA.get(comp.clause_a_id) ?? ''
                  const contentB = comp.clause_b_id ? (clausesB.get(comp.clause_b_id) ?? '') : ''
                  const colorClass = CLASSIFICATION_COLORS[comp.classification] ?? 'bg-slate-100'

                  return (
                    <div key={i} className={`border rounded-lg overflow-hidden ${colorClass.split(' ')[2] ?? ''}`}>
                      {/* Header */}
                      <div className={`flex items-center justify-between px-4 py-2 ${colorClass} text-sm`}>
                        <div className="flex items-center gap-2">
                          <Badge className={colorClass}>
                            {CLASSIFICATION_LABELS[comp.classification] ?? comp.classification}
                          </Badge>
                          <span className="text-muted-foreground">
                            Similarity: {Math.round(comp.similarity_score * 100)}%
                          </span>
                        </div>
                        <span className="text-muted-foreground text-xs">
                          {comp.clause_a_id} ↔ {comp.clause_b_id ?? '—'}
                        </span>
                      </div>
                      {/* Side by side */}
                      <div className="grid grid-cols-1 md:grid-cols-2 divide-x">
                        <div className="p-4 bg-white">
                          <p className="text-xs font-semibold text-muted-foreground mb-1">Document A</p>
                          <p className="text-sm whitespace-pre-wrap">{contentA || comp.clause_a_id}</p>
                        </div>
                        <div className="p-4 bg-white">
                          <p className="text-xs font-semibold text-muted-foreground mb-1">Document B</p>
                          <p className="text-sm whitespace-pre-wrap">{contentB || 'No matching clause'}</p>
                        </div>
                      </div>
                      {/* Summary */}
                      <div className="px-4 py-2 bg-slate-50 text-sm text-muted-foreground border-t">
                        {comp.summary}
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}
