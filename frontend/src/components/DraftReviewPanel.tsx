import { useState } from 'react'
import { api } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface Props {
  workflowId: string
  metadata: Record<string, unknown> | null
  onActionComplete: () => void
}

export default function DraftReviewPanel({ workflowId, metadata, onActionComplete }: Props) {
  const [reasoningText, setReasoningText] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const draftInfo = (metadata?.draft_info ?? metadata) as Record<string, unknown> | null
  const recipient = (draftInfo?.recipient as string) ?? 'N/A'
  const subject = (draftInfo?.subject as string) ?? 'Draft Email'
  const body = (draftInfo?.body as string) ?? (metadata?.recommendations as string) ?? 'No draft content available.'

  async function handleApprove() {
    setSubmitting(true)
    try {
      await api.approve(
        workflowId,
        'user@stitchflow.io',
        [],
        undefined,
        reasoningText || 'Draft approved for sending',
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
      await api.reject(
        workflowId,
        'user@stitchflow.io',
        [],
        {},
        reasoningText || 'Draft rejected, needs revision',
      )
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Rejection failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="border-purple-300">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Badge className="bg-purple-100 text-purple-800">Draft Ready</Badge>
          <span>Email draft awaiting your review</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Draft preview */}
        <div className="border rounded-lg overflow-hidden">
          {/* Email header */}
          <div className="bg-slate-50 px-4 py-3 space-y-1 text-sm border-b">
            <div className="flex gap-2">
              <span className="text-muted-foreground w-16">To:</span>
              <span>{recipient}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-muted-foreground w-16">Subject:</span>
              <span className="font-medium">{subject}</span>
            </div>
          </div>
          {/* Email body */}
          <div className="px-4 py-3 text-sm whitespace-pre-wrap">
            {typeof body === 'string' ? body : JSON.stringify(body, null, 2)}
          </div>
        </div>

        {/* Reasoning input */}
        <textarea
          value={reasoningText}
          onChange={(e) => setReasoningText(e.target.value)}
          placeholder="Add feedback or reasoning (optional)..."
          rows={2}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
        />

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="destructive" onClick={handleReject} disabled={submitting}>
            {submitting ? 'Processing...' : 'Reject Draft'}
          </Button>
          <Button onClick={handleApprove} disabled={submitting}>
            {submitting ? 'Processing...' : 'Approve & Send'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
