# StitchFlow V2

AI-powered Human-in-the-Loop (HITL) decision-support engine for document processing workflow automation.

## What It Does

StitchFlow V2 automates complex document processing workflows with AI reasoning while keeping humans in the loop for critical decisions. Here's the pipeline:

1. **Upload** a document (PDF, DOCX, TXT, or email)
2. **Ingest** - Text is extracted from the file
3. **Redact** - PII (emails, phone numbers, SSNs, names, addresses) is detected and masked with tokens, while keeping a reversible mapping so original data can be restored later
4. **Reason** - The AI agent (Z.AI GLM) analyzes the redacted document to classify it, extract entities, detect ambiguities and conflicts, and generate action recommendations
5. **Screen Policy** - Recommendations are checked against a configurable rule set for compliance violations and risk scoring
6. **Human Review** - If policy violations are found or clarification is needed, the workflow pauses for a human to approve, reject, or provide input
7. **Execute** - Approved recommendations are orchestrated

The system also supports **T&C document comparison** - uploading two contracts and getting an AI-powered clause-by-clause diff with similarity scoring.

Every action is recorded in a tamper-evident audit log with hash chaining for compliance.

## Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (Python 3.11) |
| AI Reasoning | Z.AI GLM-5.1 via Anthropic-compatible API |
| Workflow Orchestration | LangGraph (state machine with interrupt points) |
| AI Toolkit | LangChain |
| Database | SQLite (development), SQLAlchemy ORM, Alembic migrations |
| Validation | Pydantic v2, Pydantic Settings |
| Document Processing | PyPDF2, python-docx |
| External Integrations | Google Sheets API, Gmail API (OAuth2) |
| API Client | httpx |
| Testing | pytest, Hypothesis (property-based), pytest-asyncio |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript |
| Build Tool | Vite 8 |
| Styling | Tailwind CSS 4 |
| UI Components | shadcn/ui (Radix UI primitives) |
| Routing | React Router DOM 7 |
| Icons | Lucide React |

### DevOps
| Tool | Purpose |
|------|---------|
| Docker + Docker Compose | Containerized deployment |
| Nginx | Frontend production server |
| Alembic | Database schema migrations |

## Project Structure

```
UMHack/
├── backend/                    # FastAPI backend
│   ├── main.py                 # App entry point, CORS, lifespan
│   ├── config/
│   │   └── settings.py         # Pydantic Settings (env vars)
│   ├── models/                 # Pydantic domain models
│   │   ├── workflow.py         # WorkflowState, Workflow, state transitions
│   │   ├── document.py         # IngestionResult, PIIMatch, RedactionResult
│   │   ├── policy.py           # PolicyRule, Violation, PolicyScreeningResult
│   │   └── decision.py         # Decision, TaskResult, AuditEntry
│   ├── database/
│   │   ├── base.py             # SQLAlchemy engine, session, init_db
│   │   ├── models.py           # ORM models (6 tables)
│   │   └── utils.py            # CRUD helpers, audit logging
│   ├── components/
│   │   ├── glm_client.py       # Z.AI GLM API wrapper
│   │   ├── ingestion.py        # File upload + text extraction
│   │   ├── redaction.py        # PII detection + token masking
│   │   ├── reasoning.py        # Multi-step GLM reasoning chain
│   │   ├── policy_screening.py # Keyword-based policy matching
│   │   ├── google_sheets.py    # Sheets API sync
│   │   ├── gmail.py            # Gmail draft creation/approval
│   │   ├── task_orchestrator.py# Retry, dependency resolution
│   │   └── tc_comparison.py    # T&C clause extraction + diff
│   ├── workflows/
│   │   └── workflow_engine.py  # LangGraph state machine
│   ├── api/
│   │   └── workflows.py        # 13 REST API endpoints
│   ├── alembic/                # Database migrations
│   ├── seed_policy_rules.py    # Seed compliance rules
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.tsx             # Router setup
│   │   ├── api/client.ts       # Typed API client
│   │   ├── pages/              # Dashboard, WorkflowDetail, NewWorkflow, TCCompare
│   │   └── components/         # FileUpload, Clarification, PolicyReview, etc.
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── stitchflow-v2/              # Design 
  ├── requirements.md
  ├── design.md
  └── tasks.md               # Product requirements document
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/workflows` | Create a new workflow |
| POST | `/api/v1/workflows/{id}/upload` | Upload a document |
| GET | `/api/v1/workflows/{id}` | Get workflow details |
| GET | `/api/v1/workflows` | List workflows (filterable) |
| POST | `/api/v1/workflows/{id}/redact` | Redact PII |
| POST | `/api/v1/workflows/{id}/reason` | Run AI reasoning |
| POST | `/api/v1/workflows/{id}/screen` | Screen for policy violations |
| POST | `/api/v1/workflows/{id}/run` | Run full automated pipeline |
| POST | `/api/v1/workflows/{id}/clarify` | Provide human clarification |
| POST | `/api/v1/workflows/{id}/approve` | Approve recommendations |
| POST | `/api/v1/workflows/{id}/reject` | Reject recommendations |
| GET | `/api/v1/workflows/{id}/audit` | Get audit trail |
| GET | `/api/v1/dashboard/stats` | Dashboard statistics |
| POST | `/api/v1/workflows/tc-compare` | Compare two T&C documents |

---

## How to Run

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Z.AI API key** - Get one from [api.ilmu.ai](https://api.ilmu.ai) 
- **Docker** (optional, for containerized deployment)

---

### Option 1: Run Locally (Recommended for Development)

#### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create a virtual environment (if not using the existing .venv)
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (Git Bash):
source venv/Scripts/activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the example env file and configure it
cp .env.example .env
```

Now edit `backend/.env` and set **at minimum** these required values:

```ini
# Required - your Z.AI API key
ZHIPU_API_KEY=your_actual_api_key_here

# Required - GLM model to use
GLM_MODEL=ilmu-glm-5.1

# Required - API endpoint
GLM_BASE_URL=https://api.ilmu.ai/anthropic
```

```bash
# Clear Database
python clear_database.py

# Setup Database
python setup_database.py

# Start the backend server
python main.py
```

The backend will be running at **http://localhost:8000**

You can also access the interactive API docs at **http://localhost:8000/docs** (Swagger UI)

#### 2. Frontend Setup

Open a new terminal:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend will be running at **http://localhost:5173**

The Vite dev server is configured to proxy `/api` requests to the backend at `localhost:8000`, so both frontend and backend must be running simultaneously.

---

### Option 2: Run with Docker Compose

```bash
# From the project root directory (where docker-compose.yml is)

# Build and start all services
docker-compose up --build

# Or run in the background
docker-compose up --build -d
```

This starts:
- **Backend** on http://localhost:8000
- **Frontend** on http://localhost:3000 (commented out in compose file - uncomment the `frontend` service block in `docker-compose.yml` to enable)

To stop:
```bash
docker-compose down
```

---

### Quick Test After Starting

#### Test the health endpoint

```bash
curl http://localhost:8000/health
```

#### Create a workflow and upload a document

```bash
# Create a workflow
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Workflow", "description": "Testing the pipeline"}'

# Note the workflow_id from the response, then upload a file
curl -X POST http://localhost:8000/api/v1/workflows/{workflow_id}/upload \
  -F "file=@your_document.txt"

# Run the full automated pipeline
curl -X POST http://localhost:8000/api/v1/workflows/{workflow_id}/run
```

#### Or test through the frontend

1. Open http://localhost:5173 in your browser
2. Click "New Workflow" on the dashboard
3. Enter a name and upload a document
4. The pipeline will run step-by-step (ingest -> redact -> reason -> screen)
5. Review AI recommendations and approve/reject as needed

---

### Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Make sure you activated the virtual environment and installed dependencies |
| `ZHIPU_API_KEY` error | Set your API key in `backend/.env` |
| Database errors | Run `alembic upgrade head` to create tables |
| Frontend can't reach API | Make sure the backend is running on port 8000 before starting the frontend |
| Port already in use | Kill the process using the port or change the port in the config |
| PII redaction not finding patterns | Redaction uses regex patterns - test with documents containing clear PII (emails, phone numbers, SSNs) |

## Environment Variables Reference

See [backend/.env.example](backend/.env.example) for the full list. Key variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ZHIPU_API_KEY` | Yes | - | Z.AI GLM API key |
| `GLM_MODEL` | Yes | `ilmu-glm-5.1` | Model to use |
| `GLM_BASE_URL` | Yes | `https://api.ilmu.ai/anthropic` | API endpoint |
| `DATABASE_URL` | No | `sqlite:///./stitchflow.db` | Database connection string |
| `SECRET_KEY` | Yes | - | JWT signing key |
| `UPLOAD_DIR` | No | `./uploads` | File upload directory |
| `MAX_UPLOAD_SIZE_MB` | No | `10` | Max upload file size |
| `CORS_ORIGINS` | No | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins |
