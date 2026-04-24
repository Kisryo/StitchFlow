import { useState } from 'react'
import { api, type ReasoningResponse } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

function confidenceColor(confidence: number) {
  const pct = Math.round(confidence * 100)
  if (pct >= 80) return 'bg-green-100 text-green-800'
  if (pct >= 50) return 'bg-yellow-100 text-yellow-800'
  return 'bg-red-100 text-red-800'
}

interface Props {
  workflowId: string
  reasoning: ReasoningResponse
  onActionComplete: () => void
}

export default function RecommendationReviewPanel({ workflowId, reasoning, onActionComplete }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [reasoningText, setReasoningText] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function toggleRec(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAll() {
    if (selected.size === reasoning.recommendations.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(reasoning.recommendations.map((r) => r.id)))
    }
  }

  async function handleApprove() {
    setSubmitting(true)
    try {
      const approved = selected.size > 0 ? Array.from(selected) : reasoning.recommendations.map((r) => r.id)
      await api.approve(
        workflowId,
        'user@stitchflow.io',
        approved,
        undefined,
        reasoningText || `Approved ${approved.length} recommendations`,
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
      const rejected = selected.size > 0 ? Array.from(selected) : reasoning.recommendations.map((r) => r.id)
      const rejectionReasons: Record<string, string> = {}
      reasoning.recommendations
        .filter((r) => rejected.includes(r.id))
        .forEach((r) => {
          rejectionReasons[r.id] = `Rejected: ${r.description}`
        })
      await api.reject(
        workflowId,
        'user@stitchflow.io',
        rejected,
        rejectionReasons,
        reasoningText || `Rejected ${rejected.length} recommendations`,
      )
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Rejection failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="border-blue-300">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge className="bg-blue-100 text-blue-800">Ready for Review</Badge>
            <span>{reasoning.recommendations_generated} recommendations</span>
          </div>
          <Button variant="ghost" size="sm" onClick={selectAll}>
            {selected.size === reasoning.recommendations.length ? 'Deselect All' : 'Select All'}
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Recommendation list with checkboxes */}
        <div className="space-y-2">
          {reasoning.recommendations.map((r) => {
            const isSelected = selected.has(r.id)
            return (
              <div
                key={r.id}
                className={`flex items-start gap-3 text-sm border rounded-lg p-3 cursor-pointer transition-colors ${
                  isSelected ? 'border-primary bg-primary/5' : 'hover:bg-slate-50'
                }`}
                onClick={() => toggleRec(r.id)}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleRec(r.id)}
                  className="mt-0.5 shrink-0"
                />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="shrink-0">{r.action}</Badge>
                    <Badge className={confidenceColor(r.confidence)}>
                      {Math.round(r.confidence * 100)}%
                    </Badge>
                  </div>
                  <p>{r.description}</p>
                </div>
              </div>
            )
          })}
        </div>

        {/* Reasoning input */}
        <textarea
          value={reasoningText}
          onChange={(e) => setReasoningText(e.target.value)}
          placeholder="Add your reasoning for this decision (optional)..."
          rows={2}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
        />

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="destructive" onClick={handleReject} disabled={submitting}>
            {submitting ? 'Processing...' : `Reject${selected.size > 0 ? ` (${selected.size})` : ''}`}
          </Button>
          <Button onClick={handleApprove} disabled={submitting}>
            {submitting ? 'Processing...' : `Approve${selected.size > 0 ? ` (${selected.size})` : ' All'}`}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
