import { useState } from 'react'
import { api, type PolicyScreeningResponse } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

function severityColor(severity: string) {
  if (severity === 'critical') return 'bg-red-100 text-red-800'
  if (severity === 'high') return 'bg-orange-100 text-orange-800'
  if (severity === 'medium') return 'bg-yellow-100 text-yellow-800'
  return 'bg-slate-100 text-slate-800'
}

interface Props {
  workflowId: string
  policy: PolicyScreeningResponse
  onActionComplete: () => void
}

export default function PolicyReviewPanel({ workflowId, policy, onActionComplete }: Props) {
  const [reasoning, setReasoning] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleApprove() {
    setSubmitting(true)
    try {
      await api.approve(
        workflowId,
        'user@stitchflow.io',
        [],
        undefined,
        reasoning || 'Approved after policy review',
      )
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Approval failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleReject() {
    setSubmitting(true)
    try {
      const rejectionReasons: Record<string, string> = {}
      policy.violations.forEach((v, i) => {
        rejectionReasons[`violation_${i}`] = v.description
      })
      await api.reject(
        workflowId,
        'user@stitchflow.io',
        [],
        rejectionReasons,
        reasoning || 'Rejected due to policy violations',
      )
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Rejection failed')
    } finally {
      setSubmitting(false)
    }
  }

  const riskPct = Math.round(policy.risk_score * 100)
  const highSeverity = policy.violations.some((v) => v.severity === 'high' || v.severity === 'critical')

  return (
    <Card className={highSeverity ? 'border-red-300' : 'border-yellow-300'}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Badge className={highSeverity ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}>
            Policy Review Required
          </Badge>
          <span>Risk: {riskPct}% &middot; {policy.violations_found} violations</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Risk gauge */}
        <div className="flex items-center gap-3 bg-slate-50 rounded-lg p-3">
          <div className="flex-1">
            <p className="text-sm text-muted-foreground mb-1">Risk Score</p>
            <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${riskPct >= 60 ? 'bg-red-500' : riskPct >= 30 ? 'bg-yellow-500' : 'bg-green-500'}`}
                style={{ width: `${riskPct}%` }}
              />
            </div>
          </div>
          <p className="text-2xl font-bold">{riskPct}%</p>
        </div>

        {/* Violations */}
        <div className="space-y-2">
          {policy.violations.map((v, i) => (
            <div key={i} className="border rounded-lg p-3 space-y-1">
              <div className="flex items-center gap-2">
                <Badge className={severityColor(v.severity)}>{v.severity}</Badge>
                <span className="text-sm font-semibold">{v.rule_name}</span>
              </div>
              <p className="text-sm">{v.description}</p>
              {v.evidence.length > 0 && (
                <ul className="text-xs text-muted-foreground list-disc list-inside">
                  {v.evidence.map((e, j) => (
                    <li key={j}>{e}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>

        {/* Reasoning input */}
        <textarea
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
          placeholder="Add your reasoning for this decision (optional)..."
          rows={2}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
        />

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="destructive" onClick={handleReject} disabled={submitting}>
            {submitting ? 'Rejecting...' : 'Reject'}
          </Button>
          <Button onClick={handleApprove} disabled={submitting}>
            {submitting ? 'Approving...' : 'Approve with Risk'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
