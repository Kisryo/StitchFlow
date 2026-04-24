import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DashboardPage from '@/pages/DashboardPage'
import WorkflowDetailPage from '@/pages/WorkflowDetailPage'
import NewWorkflowPage from '@/pages/NewWorkflowPage'
import TCComparePage from '@/pages/TCComparePage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background text-foreground">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/workflows/new" element={<NewWorkflowPage />} />
          <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
          <Route path="/tc-compare" element={<TCComparePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
