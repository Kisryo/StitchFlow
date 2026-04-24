import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type DashboardStats, type WorkflowSummary } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const ATTENTION_STATES = [
  'NeedsClarification',
  'PolicyReviewRequired',
  'ReadyForReview',
  'DraftReady',
  'Escalated',
]

const ALL_STATES = [
  'New',
  'Ingested',
  'Redacted',
  'Parsed',
  'NeedsClarification',
  'PolicyReviewRequired',
  'ReadyForReview',
  'DraftReady',
  'Approved',
  'Executed',
  'Retrying',
  'Failed',
  'Escalated',
  'Completed',
]

type SortKey = 'created_at' | 'state' | 'created_by'
type SortDir = 'asc' | 'desc'

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

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filtering & sorting state
  const [filterState, setFilterState] = useState<string>('all')
  const [sortKey, setSortKey] = useState<SortKey>('created_at')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  useEffect(() => {
    let isMounted = true
    const abortController = new AbortController()
    
    async function load() {
      try {
        const [dashboardData, workflowData] = await Promise.all([
          api.getDashboardStats(),
          api.listWorkflows({ limit: 100 }),
        ])
        
        if (isMounted && !abortController.signal.aborted) {
          setStats(dashboardData)
          setWorkflows(workflowData.workflows)
        }
      } catch (e) {
        if (isMounted && !abortController.signal.aborted) {
          setError(e instanceof Error ? e.message : 'Failed to load dashboard')
        }
      } finally {
        if (isMounted && !abortController.signal.aborted) {
          setLoading(false)
        }
      }
    }
    
    load()
    
    return () => {
      isMounted = false
      abortController.abort()
    }
  }, [])

  // Filtered + sorted workflows
  const filtered = useMemo(() => {
    let list = workflows
    if (filterState !== 'all') {
      list = list.filter((w) => w.state === filterState)
    }
    list = [...list].sort((a, b) => {
      let cmp = 0
      if (sortKey === 'created_at') {
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      } else if (sortKey === 'state') {
        cmp = a.state.localeCompare(b.state)
      } else if (sortKey === 'created_by') {
        cmp = a.created_by.localeCompare(b.created_by)
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
    return list
  }, [workflows, filterState, sortKey, sortDir])

  // Group by state
  const grouped = useMemo(() => {
    const map = new Map<string, WorkflowSummary[]>()
    for (const w of filtered) {
      const group = map.get(w.state) ?? []
      group.push(w)
      map.set(w.state, group)
    }
    return map
  }, [filtered])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground text-lg">Loading dashboard...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-destructive text-lg">{error}</p>
      </div>
    )
  }

  const byState = stats?.workflows_by_state ?? {}
  const attentionCount = stats?.workflows_needing_attention ?? 0

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">StitchFlow V2</h1>
            <p className="text-sm text-muted-foreground">AI-Powered Decision-Support Engine</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => navigate('/tc-compare')}>
              Compare T&C
            </Button>
            <Button onClick={() => navigate('/workflows/new')}>
              + New Workflow
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Workflows</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{stats?.total_workflows ?? 0}</p>
            </CardContent>
          </Card>

          <Card className={attentionCount > 0 ? 'border-yellow-400' : ''}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Need Attention</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-yellow-600">{attentionCount}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Completion Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{stats?.completion_rate.toFixed(1) ?? 0}%</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Failure Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-red-600">{stats?.failure_rate.toFixed(1) ?? 0}%</p>
            </CardContent>
          </Card>
        </div>

        {/* State Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Workflows by State</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {ALL_STATES.filter((s) => byState[s]).map((state) => (
                <button
                  key={state}
                  onClick={() => setFilterState(filterState === state ? 'all' : state)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm cursor-pointer transition-colors ${
                    filterState === state
                      ? 'ring-2 ring-primary bg-primary/10'
                      : stateColor(state)
                  }`}
                >
                  <span>{stateLabel(state)}</span>
                  <span className="font-semibold">{byState[state]}</span>
                </button>
              ))}
              {Object.keys(byState).length === 0 && (
                <p className="text-muted-foreground">No workflows yet</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Workflow List — Tabs: All / Grouped / Needs Attention */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
            <CardTitle className="text-lg">Workflows</CardTitle>
            <div className="flex items-center gap-3">
              <Select value={filterState} onValueChange={setFilterState}>
                <SelectTrigger className="w-44">
                  <SelectValue placeholder="Filter by state" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All States</SelectItem>
                  {ALL_STATES.map((s) => (
                    <SelectItem key={s} value={s}>{stateLabel(s)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={`${sortKey}-${sortDir}`} onValueChange={(v) => {
                const [k, d] = v.split('-') as [SortKey, SortDir]
                setSortKey(k)
                setSortDir(d)
              }}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="created_at-desc">Newest first</SelectItem>
                  <SelectItem value="created_at-asc">Oldest first</SelectItem>
                  <SelectItem value="state-asc">State A-Z</SelectItem>
                  <SelectItem value="state-desc">State Z-A</SelectItem>
                  <SelectItem value="created_by-asc">Creator A-Z</SelectItem>
                  <SelectItem value="created_by-desc">Creator Z-A</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="all">
              <TabsList>
                <TabsTrigger value="all">All ({filtered.length})</TabsTrigger>
                <TabsTrigger value="grouped">Grouped by State</TabsTrigger>
                <TabsTrigger value="attention">
                  Attention ({workflows.filter((w) => ATTENTION_STATES.includes(w.state)).length})
                </TabsTrigger>
              </TabsList>

              {/* Tab: All Workflows (flat list) */}
              <TabsContent value="all">
                {filtered.length === 0 ? (
                  <p className="text-muted-foreground py-8 text-center">
                    No workflows found.
                  </p>
                ) : (
                  <WorkflowTable workflows={filtered} onRowClick={(id) => navigate(`/workflows/${id}`)} />
                )}
              </TabsContent>

              {/* Tab: Grouped by State */}
              <TabsContent value="grouped">
                {grouped.size === 0 ? (
                  <p className="text-muted-foreground py-8 text-center">
                    No workflows found.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {Array.from(grouped.entries()).map(([state, ws]) => (
                      <div key={state}>
                        <div className="flex items-center gap-2 mb-2">
                          <Badge className={stateColor(state)}>{stateLabel(state)}</Badge>
                          <span className="text-sm text-muted-foreground">{ws.length} workflow{ws.length !== 1 ? 's' : ''}</span>
                        </div>
                        <div className="ml-4">
                          <WorkflowTable workflows={ws} onRowClick={(id) => navigate(`/workflows/${id}`)} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </TabsContent>

              {/* Tab: Needs Attention */}
              <TabsContent value="attention">
                {(() => {
                  const attentionWfs = workflows.filter((w) => ATTENTION_STATES.includes(w.state))
                  return attentionWfs.length === 0 ? (
                    <p className="text-muted-foreground py-8 text-center">
                      No workflows need attention right now.
                    </p>
                  ) : (
                    <WorkflowTable workflows={attentionWfs} onRowClick={(id) => navigate(`/workflows/${id}`)} highlight />
                  )
                })()}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}

// ── Shared Workflow Table ──

function WorkflowTable({
  workflows,
  onRowClick,
  highlight,
}: {
  workflows: WorkflowSummary[]
  onRowClick: (id: string) => void
  highlight?: boolean
}) {
  return (
    <div className="divide-y">
      {workflows.map((w) => {
        const isAttention = ATTENTION_STATES.includes(w.state)
        return (
          <div
            key={w.workflow_id}
            className={`flex items-center justify-between py-3 px-3 cursor-pointer transition-colors rounded-md ${
              isAttention && highlight
                ? 'bg-yellow-50 hover:bg-yellow-100'
                : 'hover:bg-slate-50'
            }`}
            onClick={() => onRowClick(w.workflow_id)}
          >
            <div className="flex items-center gap-3 min-w-0">
              {isAttention && highlight && (
                <span className="shrink-0 h-2 w-2 rounded-full bg-yellow-500" />
              )}
              <span className="text-sm font-mono text-muted-foreground truncate">
                {w.workflow_id.slice(0, 8)}
              </span>
              <span className="text-sm truncate">{w.created_by}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <Badge className={stateColor(w.state)}>{stateLabel(w.state)}</Badge>
              <span className="text-xs text-muted-foreground hidden sm:inline">
                {new Date(w.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
