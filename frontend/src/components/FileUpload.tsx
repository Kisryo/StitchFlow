import { useCallback, useState, useRef } from 'react'
import { Button } from '@/components/ui/button'

const ACCEPTED_TYPES = new Set(['pdf', 'docx', 'txt', 'eml'])
const MAX_SIZE_MB = 10

interface FileUploadProps {
  onFileSelected: (file: File) => void
  uploading?: boolean
  error?: string | null
}

export default function FileUpload({ onFileSelected, uploading, error }: FileUploadProps) {
  const [dragOver, setDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const validate = useCallback((file: File): string | null => {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ACCEPTED_TYPES.has(ext) && ext !== 'email') {
      return `Unsupported file type: .${ext}. Accepted: PDF, DOCX, TXT, EML`
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum: ${MAX_SIZE_MB}MB`
    }
    return null
  }, [])

  const handleFile = useCallback(
    (file: File) => {
      const err = validate(file)
      setValidationError(err)
      if (!err) {
        setSelectedFile(file)
      } else {
        setSelectedFile(null)
      }
    },
    [validate],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const displayError = validationError ?? error

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        className={`relative flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-8 transition-colors cursor-pointer ${
          dragOver
            ? 'border-primary bg-primary/5'
            : selectedFile
              ? 'border-green-400 bg-green-50'
              : 'border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.eml,.email"
          className="hidden"
          onChange={handleInputChange}
        />

        {uploading ? (
          <div className="text-center space-y-2">
            <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-muted-foreground">Uploading and processing...</p>
          </div>
        ) : selectedFile ? (
          <div className="text-center space-y-1">
            <div className="text-green-600 text-4xl mb-2">&#10003;</div>
            <p className="font-medium">{selectedFile.name}</p>
            <p className="text-sm text-muted-foreground">
              {(selectedFile.size / 1024).toFixed(1)} KB
            </p>
          </div>
        ) : (
          <div className="text-center space-y-2">
            <div className="text-muted-foreground text-4xl mb-2">&#8682;</div>
            <p className="font-medium">Drop your file here, or click to browse</p>
            <p className="text-sm text-muted-foreground">
              PDF, DOCX, TXT, or EML — max {MAX_SIZE_MB}MB
            </p>
          </div>
        )}
      </div>

      {/* Error */}
      {displayError && (
        <p className="text-sm text-destructive">{displayError}</p>
      )}

      {/* Action Button */}
      {selectedFile && !uploading && (
        <Button className="w-full" onClick={() => onFileSelected(selectedFile)}>
          Upload & Process
        </Button>
      )}
    </div>
  )
}
