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

export default function ConflictResolutionPanel({ workflowId, reasoning, onActionComplete }: Props) {
  const [resolutions, setResolutions] = useState<Record<string, { choice: string; reasoning: string }>>({})
  const [submitting, setSubmitting] = useState(false)

  // Extract conflicts from reasoning — they come through ambiguities when in NeedsClarification state
  // The reasoning.ambiguities may contain conflict-related items
  const conflictItems = reasoning.ambiguities.filter(
    (a) => a.type === 'missing_data' || a.type === 'unclear_reference' || a.type === 'multiple_interpretations',
  )

  async function handleSubmit() {
    setSubmitting(true)
    try {
      const clarifications = Object.entries(resolutions).map(([key, val]) => ({
        ambiguity_id: key,
        answer: `${val.choice}: ${val.reasoning}`,
      }))
      await api.clarify(
        workflowId,
        'user@stitchflow.io',
        clarifications,
        `Resolved ${clarifications.length} conflicts`,
      )
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to submit resolutions')
    } finally {
      setSubmitting(false)
    }
  }

  const allResolved = conflictItems.every((_, i) => {
    const key = `conflict_${i}`
    return resolutions[key]?.choice && resolutions[key]?.reasoning?.trim()
  })

  if (conflictItems.length === 0) {
    return null
  }

  return (
    <Card className="border-orange-300">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Badge className="bg-orange-100 text-orange-800">Conflicts Detected</Badge>
          <span>{conflictItems.length} conflicts need resolution</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {conflictItems.map((item, i) => {
          const key = `conflict_${i}`
          const current = resolutions[key] ?? { choice: '', reasoning: '' }
          return (
            <div key={key} className="border rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                <Badge variant="outline">{item.type}</Badge>
                <span className="text-sm font-medium">{item.description}</span>
              </div>
              <p className="text-sm text-muted-foreground">Q: {item.question}</p>

              {/* Resolution choices */}
              {item.possible_interpretations && item.possible_interpretations.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Select the correct interpretation:</p>
                  {item.possible_interpretations.map((interp, j) => (
                    <label
                      key={j}
                      className={`flex items-start gap-2 p-2 rounded-md cursor-pointer transition-colors text-sm ${
                        current.choice === interp ? 'bg-primary/10 border border-primary' : 'hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name={key}
                        checked={current.choice === interp}
                        onChange={() =>
                          setResolutions((prev) => ({
                            ...prev,
                            [key]: { ...prev[key], choice: interp },
                          }))
                        }
                        className="mt-0.5"
                      />
                      <span>{interp}</span>
                    </label>
                  ))}
                </div>
              ) : null}

              {/* Custom resolution if no interpretations or "Other" */}
              <textarea
                value={current.reasoning}
                onChange={(e) =>
                  setResolutions((prev) => ({
                    ...prev,
                    [key]: {
                      ...prev[key],
                      choice: prev[key]?.choice || e.target.value,
                      reasoning: e.target.value,
                    },
                  }))
                }
                placeholder="Explain your resolution..."
                rows={2}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              />
            </div>
          )
        })}

        <div className="flex justify-end gap-2 pt-2">
          <Button onClick={handleSubmit} disabled={submitting || !allResolved}>
            {submitting ? 'Submitting...' : 'Submit Resolutions'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
