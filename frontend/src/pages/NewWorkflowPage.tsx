import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import FileUpload from '@/components/FileUpload'

export default function NewWorkflowPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFileSelected(file: File) {
    setUploading(true)
    setError(null)
    try {
      const creatorName = name.trim() || 'Anonymous'
      const wf = await api.createWorkflow(creatorName)

      // Step 2: Upload document
      await api.uploadDocument(wf.workflow_id, file)

      // Step 3: Navigate to workflow detail
      navigate(`/workflows/${wf.workflow_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create workflow')
      setUploading(false)
    }
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/')}>&larr; Back</Button>
          <h1 className="text-xl font-bold tracking-tight">New Workflow</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Create a Workflow</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Creator Name */}
            <div>
              <label className="block text-sm font-medium mb-1.5">Your Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium mb-1.5">Upload Document</label>
              <FileUpload
                onFileSelected={handleFileSelected}
                uploading={uploading}
                error={error}
              />
            </div>

            {/* Info text */}
            <div className="bg-slate-50 rounded-lg p-4 text-sm text-muted-foreground space-y-1">
              <p><strong>How it works:</strong></p>
              <ol className="list-decimal list-inside space-y-0.5">
                <li>Enter your name and upload a document</li>
                <li>The system extracts text and redacts PII</li>
                <li>AI analyzes the document and generates recommendations</li>
                <li>You review and approve/reject the AI suggestions</li>
              </ol>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
