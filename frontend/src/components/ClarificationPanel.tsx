import { useState } from 'react'
import { api, type ReasoningResponse } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface Props {
  workflowId: string
  reasoning: ReasoningResponse
  onActionComplete: () => void
}

export default function ClarificationPanel({ workflowId, reasoning, onActionComplete }: Props) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    setSubmitting(true)
    try {
      const clarifications = reasoning.ambiguities.map((_, i) => ({
        ambiguity_id: `amb_${i}`,
        answer: answers[`amb_${i}`] ?? '',
      }))
      await api.clarify(workflowId, 'user@stitchflow.io', clarifications)
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to submit clarifications')
    } finally {
      setSubmitting(false)
    }
  }

  const allAnswered = reasoning.ambiguities.every((_, i) =>
    answers[`amb_${i}`]?.trim()
  )

  return (
    <Card className="border-yellow-300">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Badge className="bg-yellow-100 text-yellow-800">Clarification Needed</Badge>
          <span>{reasoning.ambiguities_found} ambiguities detected</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {reasoning.ambiguities.map((a, i) => {
          const key = `amb_${i}`
          return (
            <div key={key} className="border-l-4 border-yellow-400 pl-4 py-2 space-y-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="shrink-0">{a.type}</Badge>
                <span className="text-sm font-medium text-yellow-800">{a.description}</span>
              </div>
              <p className="text-sm text-muted-foreground">{a.question}</p>
              <textarea
                value={answers[key] ?? ''}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder="Type your clarification..."
                rows={2}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              />
            </div>
          )
        })}

        <div className="flex justify-end gap-2 pt-2">
          <Button
            onClick={handleSubmit}
            disabled={submitting || !allAnswered}
          >
            {submitting ? 'Submitting...' : 'Submit Clarifications'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
