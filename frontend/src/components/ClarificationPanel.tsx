import { useState } from 'react'
import { api, type ReasoningResponse, type Conflict } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

function clean(text: string) {
  return text
    .replace(/\[NAME_(\d+)\]/g, 'Person $1')
    .replace(/\[EMAIL_(\d+)\]/g, 'Email $1')
    .replace(/\[PHONE_(\d+)\]/g, 'Phone $1')
    .replace(/\[ADDRESS_(\d+)\]/g, 'Address $1')
    .replace(/\[SSN_(\d+)\]/g, 'SSN $1')
    .replace(/NAME(\d+)/g, 'Person $1')
    .replace(/EMAIL(\d+)/g, 'Email $1')
    .replace(/PHONE(\d+)/g, 'Phone $1')
    .replace(/ADDRESS(\d+)/g, 'Address $1')
    .replace(/SSN(\d+)/g, 'SSN $1')
}

function fmtEntity(entity: Conflict['conflicting_entities'][0]) {
  const val = entity.value
  if (/^\[.*_\d+\]$/.test(val)) {
    return val.replace(/^\[(.+)\]$/, '$1')
  }
  return clean(val)
}

type ItemKind = 'conflict' | 'ambiguity'

interface Item {
  kind: ItemKind
  id: string
  type: string
  description: string
  question: string
  options: string[]
  evidence: string[]
}

interface Props {
  workflowId: string
  reasoning: ReasoningResponse
  onActionComplete: () => void
}

export default function ClarificationPanel({ workflowId, reasoning, onActionComplete }: Props) {
  const [answers, setAnswers] = useState<Record<string, { chosen: number | null; custom: string }>>({})
  const [submitting, setSubmitting] = useState(false)

  // Merge conflicts + ambiguities into one list, no duplicates
  const items: Item[] = []

  for (let i = 0; i < (reasoning.conflicts?.length ?? 0); i++) {
    const c = reasoning.conflicts[i]
    const options = c.conflicting_entities.map((e) => fmtEntity(e))
    items.push({
      kind: 'conflict',
      id: `conflict_${i}`,
      type: c.conflict_type.replace(/_/g, ' '),
      description: clean(c.description),
      question: `Which value is correct for this ${c.conflict_type.replace(/_/g, ' ')}?`,
      options,
      evidence: c.evidence.map(clean),
    })
  }

  for (let i = 0; i < reasoning.ambiguities.length; i++) {
    const a = reasoning.ambiguities[i]
    // Skip if this ambiguity looks like a duplicate of a conflict
    const isDuplicate = items.some((item) => {
      const descA = a.description.toLowerCase().replace(/[\s\[\]_]/g, '')
      const descB = item.description.toLowerCase().replace(/[\s\[\]_]/g, '')
      return descA === descB || descA.includes(descB) || descB.includes(descA)
    })
    if (isDuplicate) continue

    const options = a.possible_interpretations?.length
      ? a.possible_interpretations.map(clean)
      : []
    items.push({
      kind: 'ambiguity',
      id: `amb_${i}`,
      type: a.type.replace(/_/g, ' '),
      description: clean(a.description),
      question: clean(a.question),
      options,
      evidence: [],
    })
  }

  function getAnswer(id: string) {
    return answers[id] ?? { chosen: null, custom: '' }
  }

  function setAnswer(id: string, update: Partial<{ chosen: number | null; custom: string }>) {
    setAnswers((prev) => ({
      ...prev,
      [id]: { ...getAnswer(id), ...update },
    }))
  }

  // Can submit when every item has at least a chosen option OR custom text
  const canSubmit = items.length > 0 && items.every((item) => {
    const a = getAnswer(item.id)
    return a.chosen !== null || a.custom.trim().length > 0
  })

  async function handleSubmit() {
    setSubmitting(true)
    try {
      const clarifications = items.map((item) => {
        const a = getAnswer(item.id)
        let answer = ''
        if (a.chosen !== null) {
          answer = `Chose: ${item.options[a.chosen]}`
          if (a.custom.trim()) {
            answer += `. ${a.custom.trim()}`
          }
        } else {
          answer = a.custom.trim()
        }
        return { ambiguity_id: item.id, answer }
      })
      await api.clarify(workflowId, 'user@stitchflow.io', clarifications)
      onActionComplete()
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to submit')
    } finally {
      setSubmitting(false)
    }
  }

  if (items.length === 0) return null

  const conflictCount = items.filter((i) => i.kind === 'conflict').length
  const ambigCount = items.filter((i) => i.kind === 'ambiguity').length

  return (
    <Card className="border-yellow-300">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Badge className="bg-yellow-100 text-yellow-800">Your Input Needed</Badge>
          <span>
            {conflictCount > 0 && ambigCount > 0 && `${conflictCount} conflict${conflictCount > 1 ? 's' : ''} & ${ambigCount} question${ambigCount > 1 ? 's' : ''}`}
            {conflictCount > 0 && ambigCount === 0 && `${conflictCount} conflict${conflictCount > 1 ? 's' : ''} to resolve`}
            {conflictCount === 0 && ambigCount > 0 && `${ambigCount} question${ambigCount > 1 ? 's' : ''} to answer`}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.map((item) => {
          const a = getAnswer(item.id)
          const hasAnswer = a.chosen !== null || a.custom.trim().length > 0
          return (
            <div
              key={item.id}
              className={`border rounded-lg p-4 space-y-3 ${
                item.kind === 'conflict' ? 'border-orange-200 bg-orange-50/30' : 'border-yellow-200 bg-yellow-50/30'
              }`}
            >
              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className={item.kind === 'conflict' ? 'border-orange-300 text-orange-700' : 'border-yellow-300 text-yellow-700'}
                >
                  {item.type}
                </Badge>
                <span className="text-sm font-medium">{item.description}</span>
              </div>

              {/* Evidence (conflicts only) */}
              {item.evidence.length > 0 && (
                <div className="text-sm text-muted-foreground space-y-1">
                  {item.evidence.map((ev, j) => (
                    <p key={j} className="italic">"{ev}"</p>
                  ))}
                </div>
              )}

              <p className="text-sm font-medium">{item.question}</p>

              {/* Options to pick from */}
              {item.options.length > 0 && (
                <div className="space-y-2">
                  {item.options.map((opt, j) => {
                    const isSelected = a.chosen === j
                    return (
                      <label
                        key={j}
                        className={`flex items-center gap-2 p-2 rounded-md cursor-pointer transition-colors text-sm ${
                          isSelected ? 'bg-primary/10 border border-primary' : 'hover:bg-slate-50 border border-transparent'
                        }`}
                      >
                        <input
                          type="radio"
                          name={item.id}
                          checked={isSelected}
                          onChange={() => setAnswer(item.id, { chosen: j })}
                          className="mt-0.5"
                        />
                        <span>{opt}</span>
                      </label>
                    )
                  })}
                </div>
              )}

              {/* Free text — optional if picked an option, required if no options */}
              <textarea
                value={a.custom}
                onChange={(e) => setAnswer(item.id, { custom: e.target.value })}
                placeholder={
                  item.options.length > 0
                    ? 'Add your own answer (optional)...'
                    : 'Type your answer (required)...'
                }
                rows={2}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              />

              {!hasAnswer && (
                <p className="text-xs text-orange-600">
                  Please pick an option or type your answer to proceed.
                </p>
              )}
            </div>
          )
        })}

        <div className="flex justify-end gap-2 pt-2">
          <Button onClick={handleSubmit} disabled={submitting || !canSubmit}>
            {submitting ? 'Submitting...' : 'Submit & Continue'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
