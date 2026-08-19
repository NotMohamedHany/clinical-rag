# Clinical Guidelines RAG — Agentic Clinical Assistant & API Platform

An enterprise-grade, production-ready **Agentic Retrieval-Augmented Generation (RAG) platform and Multi-Agent Clinical Assistant**. Built to query medical guidelines (including WHO **HEARTS-D**, NICE Type 1 & 2 Diabetes, Hypertension, Osteoporosis, and Gastroenterology guidelines), perform bilingual symptom/vital sign triage, and automate doctor calendar management.

The platform integrates:
- **Agentic RAG Engine**: Self-improving hybrid retrieval (ChromaDB Dense Vector + BM25 Sparse search, Reciprocal Rank Fusion, Cross-Encoder reranking, iterative query rewriting, and LLM relevance grading).
- **Multi-Role Supervisor Assistant**: Role-based supervisor agents (`doctor` vs `patient`) with strict server-side tool permissions.
- **Bilingual Triage Checkers**: Dedicated tools for English & Arabic symptom analysis and vital sign evaluation with emergency red-flag warnings.
- **Calendar Integration**: Doctor schedule automation via an n8n cloud webhook workflow.
- **FastAPI Backend Services**: OAuth/Bearer token authentication with PBKDF2 hashing, session management, real-time Server-Sent Events (SSE) streaming, debug tracing, and Kubernetes probes.
- **Dual Frontends**:
  - **Gastro AI Web App** (`frontweb/gastro-ai`): Premium React 18 + TypeScript + Vite web application with dark glassmorphism UI, Web Speech API voice interaction (TTS/STT), source citation drawers, and configurable API links.
  - **Streamlit Clinical Inspector** (`frontend/app.py`): Python dashboard with live health diagnostics, multi-session management, SSE streaming, and retrieval trace inspection.

> ⚠️ **Educational & Research Use Only:** The system generates answers strictly from ingested clinical guideline PDFs in `data/`. It never diagnoses, never prescribes, includes safety disclaimers, and explicitly states when guidelines lack sufficient information.

---

## Table of Contents

- [1. System Architecture](#1-system-architecture)
- [2. Feature Highlights](#2-feature-highlights)
- [3. Repository Directory Map](#3-repository-directory-map)
- [4. Technology Stack & Models](#4-technology-stack--models)
- [5. Environment & Configuration](#5-environment--configuration)
- [6. Prerequisites & Installation](#6-prerequisites--installation)
- [7. Ingestion Pipeline](#7-ingestion-pipeline)
- [8. Quickstart & How to Run](#8-quickstart--how-to-run)
- [9. Role-Based Access Control (RBAC)](#9-role-based-access-control-rbac)
- [10. API Endpoint Reference](#10-api-endpoint-reference)
- [11. Specialized Agent Tools](#11-specialized-agent-tools)
- [12. Frontend Applications](#12-frontend-applications)
- [13. Testing & Evaluation](#13-testing--evaluation)
- [14. Limitations & Safety Disclaimers](#14-limitations--safety-disclaimers)

---

## 1. System Architecture

```text
                                  ┌───────────────────────────┐
                                  │      Client Interface     │
                                  └─────────────┬─────────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     │                                                     │
                     ▼                                                     ▼
      ┌─────────────────────────────┐                       ┌─────────────────────────────┐
      │  Gastro AI React/Vite App   │                       │  Streamlit Debug Chat UI    │
      │   (http://localhost:5173)   │                       │   (http://localhost:8501)   │
      └──────────────┬──────────────┘                       └──────────────┬──────────────┘
                     │                                                     │
                     └──────────────────────────┬──────────────────────────┘
                                                │ HTTP / REST / SSE Stream
                                                ▼
                                  ┌───────────────────────────┐
                                  │    FastAPI Gateway API    │
                                  │   (http://localhost:8000) │
                                  └─────────────┬─────────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     │ Authorization (Bearer Token) & Session Manager      │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │   Role-Based Supervisor   │
                                  │     (Doctor vs Patient)   │
                                  └─────────────┬─────────────┘
                                                │
         ┌──────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                      ▼                                      ▼
┌──────────────────┐                  ┌──────────────────┐                  ┌──────────────────┐
│ Clinical RAG     │                  │ Signs & Symptoms │                  │ Calendar Webhook │
│ Graph Tool       │                  │ Checkers         │                  │ Sub-Agent (n8n)  │
└────────┬─────────┘                  └────────┬─────────┘                  └────────┬─────────┘
         │                                     │                                     │
         │ (Self-Improving Loop)               │ (Bilingual Eng/Arab                 │ (Doctor Role Only)
         ▼                                     │  Triage & Warnings)                 ▼
┌────────────────────────────────┐             └─────────────────┬───────────────────┘
│  Conversation Memory           │                               │
│  Query Analyzer & Rewriter     │                               ▼
│  Hybrid Search (Vector + BM25) │                        ┌──────────────┐
│  RRF Fusion & Cross Reranker   │                        │ Ollama LLM   │
│  Relevance Grader (Score >=.70)│───────────────────────►│ (Gemma 31B) │
│  Generator with Citations      │                        └──────────────┘
└────────────────────────────────┘
```

### Self-Improving RAG Execution Loop

```text
Original User Query ──► Query Rewriter (Resolves context & adds clinical terms)
                             │
                             ▼
                  Parallel Hybrid Search
               ┌─────────────┴─────────────┐
               ▼                           ▼
        Vector Search (Chroma)      Sparse Search (BM25)
               │                           │
               └─────────────┬─────────────┘
                             ▼
                Reciprocal Rank Fusion (RRF)
                             │
                             ▼
              Cross-Encoder Reranker (BAAI)
                             │
                             ▼
                  Relevance Grader (Gemma)
                   /                 \
        Score >= 0.70               Score < 0.70
             │                           │
             ▼                           ▼
      Response Generator       Rewrite with Feedback
     (with exact citations)     (Max 2 iterations loop)
```

---

## 2. Feature Highlights

1. **Self-Improving Retrieval Loop**:
   - Hybrid Search combining dense vector similarity (`sentence-transformers/all-MiniLM-L6-v2`) and sparse keyword matching (`rank-bm25`).
   - Merging with Reciprocal Rank Fusion (RRF, $k=60$).
   - Precision reranking using `BAAI/bge-reranker-v2-m3` Cross-Encoder.
   - Iterative feedback loop: Structured LLM relevance grader re-triggers query rewriting if relevance score falls below `0.70` (max 2 iterations).

2. **Multi-Role Supervisor Assistant**:
   - **Doctor Role**: Access to clinical RAG graph, symptoms/signs checkers, calendar webhook (`manage_calendar`), and user directory.
   - **Patient Role**: Access to clinical RAG graph and bilingual symptoms/signs triage. Calendar management tools are completely omitted server-side to prevent unauthorized scheduling.

3. **Bilingual Clinical Triage Checkers**:
   - `symptoms_checker`: Parses patient-reported symptoms, extracts structured attributes (location, duration, severity), provides non-diagnostic causes, emergency warnings, and Arabic/English language matching.
   - `signs_checker`: Evaluates vital signs, lab results, and physical measurements against clinical reference ranges.

4. **Real-Time Streaming & Debug Tracing**:
   - SSE streaming endpoint (`/chat/stream`) emitting real-time tokens, tool invocation start events, and final responses.
   - Trace endpoint (`/chat/debug`) exposing query iterations, candidate retrieval numbers, relevance scores, and tool argument call logs.

5. **Production Backend & Authentication**:
   - Password security with PBKDF2 (100,000 iterations + salt).
   - CSV user registry (`users.csv`) and persistent bearer token storage (`.tokens_registry.json`).
   - Thread-safe session manager with automatic stale session eviction (24h TTL).
   - Kubernetes liveness (`/health/liveness`) and readiness (`/health/readiness`) probes.

---

## 3. Repository Directory Map

```text
clinical-rag/
├── README.md                          # Main repository documentation
├── pyproject.toml                     # Python project metadata
├── requirements.txt                   # Backend dependencies
├── users.csv                          # CSV user registry (auto-seeded)
├── .tokens_registry.json              # Active bearer tokens registry
├── .env.example                       # Environment template
├── bm25/                              # Persisted BM25 corpus & index
│   └── bm25_corpus.pkl
├── chroma_db/                         # Persistent ChromaDB vector database
├── data/                              # Guideline PDF storage directory
│   ├── diabetes_guideline.pdf         # Guideline (type: "diabetes")
│   ├── osteoporosis.pdf               # Guideline (type: "osteoporosis")
│   ├── Stomach1.pdf                   # Guideline (type: "Stomach1")
│   ├── hypertension-in-adults-diagnosis-and-management.pdf
│   ├── type-1-diabetes-in-adults-diagnosis-and-management.pdf
│   └── type-2-diabetes-in-adults-management.pdf
├── frontend/                          # Streamlit Application
│   └── app.py                         # Streamlit chat & debug dashboard
├── frontweb/                          # Web Frontend Application
│   └── gastro-ai/                     # React 18 + Vite + TypeScript application
│       ├── package.json
│       ├── vite.config.ts
│       └── src/
│           ├── api/                   # API client service & mock handlers
│           ├── components/            # React UI components (Auth, Chat, Voice, Modal)
│           ├── context/               # Context providers (Auth, Theme, Chat)
│           ├── hooks/                 # Web Speech API & UI custom hooks
│           ├── pages/                 # React router pages
│           └── styles/                # CSS variable design system
└── src/                               # Python Backend Source
    ├── config.py                      # System configuration & hyperparameters
    ├── agent/                         # Multi-role supervisor & agent tools
    │   ├── supervisor.py              # Supervisor builder (Doctor vs Patient)
    │   ├── patient.py                 # Bilingual symptoms_checker & signs_checker
    │   └── tools.py                   # Calendar n8n webhook tool & time helper
    ├── api/                           # FastAPI gateway services
    │   ├── main.py                    # FastAPI application setup & middleware
    │   ├── auth.py                    # PBKDF2 password security & CLI manager
    │   ├── schemas.py                 # Pydantic v2 schemas
    │   ├── session_manager.py         # Session state manager & thread locks
    │   └── routers/                   # Endpoint routers
    │       ├── auth.py                # Authentication router
    │       ├── chat.py                # Chat, streaming SSE & debug router
    │       └── health.py              # Health check & k8s probes router
    ├── ingestion/                     # Guideline PDF ingestion pipeline
    │   └── ingest.py                  # PyMuPDF parser, chunker & indexer
    ├── memory/                        # Session memory
    │   └── conversation.py            # Conversational memory buffer
    └── rag/                           # Agentic RAG implementation
        ├── bm25_search.py             # Sparse BM25 retrieval
        ├── embeddings.py              # Dense MiniLM embedding wrapper
        ├── generator.py               # Citation-bound response generator
        ├── graph.py                   # LangGraph agentic RAG workflow
        ├── hybrid_search.py           # Parallel hybrid search & RRF fusion
        ├── llm.py                     # Ollama LLM client instance wrapper
        ├── prompts.py                 # System & query rewriting prompts
        ├── query_rewriter.py          # Clinical query transformer
        ├── rag_tool.py                # RAG graph wrapped as LangChain tool
        ├── relevance_grader.py        # Structured relevance evaluator
        ├── reranker.py                # Cross-Encoder reranker
        ├── state.py                   # LangGraph state schema
        └── vector_search.py           # ChromaDB dense retriever
```

---

## 4. Technology Stack & Models

| Component | Technology / Model | Deployment / Details |
|---|---|---|
| **LLM Reasoning & Generation** | `gemma4:31b-cloud` | Served via Ollama Cloud API |
| **Dense Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | 384-d dense vectors (local execution) |
| **Reranker Engine** | `BAAI/bge-reranker-v2-m3` | Deep Cross-Encoder scoring (local execution) |
| **Vector Database** | ChromaDB | Persistent collection `clinical_guidelines` |
| **Sparse Keyword Search** | `rank-bm25` | Saved corpus in `bm25/bm25_corpus.pkl` |
| **Backend Gateway** | FastAPI, Uvicorn, Pydantic v2 | Async REST, SSE streams, JSON schemas |
| **Authentication & Auth Security** | PBKDF2 (100k iterations), Bearer Tokens | Salted password hashing, bearer auth |
| **Web Frontend** | React 18, TypeScript, Vite | Modern glassmorphism UI, Web Speech API |
| **Debug Dashboard** | Streamlit | Real-time SSE streaming, retrieval trace inspector |
| **Calendar Automation** | n8n Cloud Webhook Workflow | Live calendar sub-agent integration |

---

## 5. Environment & Configuration

Environment configuration is read from `.env` (loaded automatically by [`src/config.py`](clinical-rag/src/config.py)).

### Environment Variables Template (`.env`)

```bash
# LLM Configuration
OLLAMA_MODEL=gemma4:31b-cloud
OLLAMA_BASE_URL=http://localhost:11434

# Security & Authentication
TOKEN_TTL_SECONDS=0                              # 0 = tokens never expire automatically
USERS_CSV_PATH=clinical-rag/users.csv

# Hugging Face Access Token (Optional: Speeds up model downloads)
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Web Frontend Configuration (in frontweb/gastro-ai/.env)
VITE_API_URL=http://localhost:8000
VITE_USE_MOCK_API=false
```

### Core Configuration Parameters ([`src/config.py`](clinical-rag/src/config.py))

| Parameter | Value | Description |
|---|---|---|
| `CHUNK_SIZE` | `1000` | Target character size for PDF document splitting |
| `CHUNK_OVERLAP` | `200` | Overlap characters between consecutive chunks |
| `VECTOR_K` | `30` | Top candidates retrieved from ChromaDB vector search |
| `BM25_K` | `30` | Top candidates retrieved from BM25 keyword search |
| `RRF_K` | `60` | Constant for Reciprocal Rank Fusion scoring ($1 / (k + rank)$) |
| `RERANK_TOP_N` | `8` | Top reranked context chunks sent to relevance grader |
| `MAX_ITERATIONS` | `2` | Maximum query refinement iterations in self-improving loop |
| `RELEVANCE_THRESHOLD`| `0.70` | Min relevance grade needed to pass to generation step |
| `MAX_HISTORY_TURNS` | `6` | Recent user/assistant dialogue turns used for query rewriting |

---

## 6. Prerequisites & Installation

### Requirements
- **Python**: 3.11+
- **Node.js**: v18+ (for Gastro AI React Web App)
- **Ollama**: Installed and running

### Step 1: Install Ollama & Pull LLM Model

```bash
# Start Ollama service
ollama serve

# Verify/pull LLM model
ollama run gemma4:31b-cloud
```

### Step 2: Set Up Backend Environment

```bash
cd clinical-rag

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

> **CPU PyTorch Tip (Linux):** To avoid downloading CUDA wheels:
> `pip install torch --index-url https://download.pytorch.org/whl/cpu`

### Step 3: Set Up React Web Frontend (`frontweb/gastro-ai`)

```bash
cd frontweb/gastro-ai
npm install
cp .env.example .env
```

---

## 7. Ingestion Pipeline

The ingestion pipeline ([`src/ingestion/ingest.py`](clinical-rag/src/ingestion/ingest.py)) parses and indexes all PDF files placed under `data/`.

```bash
python -m src.ingestion.ingest
```

### Automatic Guideline Typing
Each document chunk is assigned a clinical `type` metadata tag:
- Folder path mapping: `data/hypertension/guideline.pdf` $\rightarrow$ `type: "hypertension"`
- File stem mapping: `data/diabetes_guideline.pdf` $\rightarrow$ `type: "diabetes"`
- Plain stem fallback: `data/Stomach1.pdf` $\rightarrow$ `type: "Stomach1"`

### Pipeline Characteristics
- **PyMuPDF Extraction**: Extracts page text with exact page numbering.
- **Recursive Character Splitting**: 1000 characters per chunk, 200 overlap.
- **Idempotent Storage**: Hashes `(filename, page, chunk_index)` to prevent duplicate entries on re-runs.
- **Dual Index Generation**: Updates ChromaDB vector collection `clinical_guidelines` and writes `bm25/bm25_corpus.pkl`.

---

## 8. Quickstart & How to Run

### 1. Launch FastAPI Backend Gateway

```bash
cd clinical-rag
source .venv/bin/activate
uvicorn src.api.main:app --reload --port 8000
```
- API Base URL: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

### 2. Launch Gastro AI React Web Application

```bash
cd clinical-rag/frontweb/gastro-ai
npm run dev
```
- Web Application URL: `http://localhost:5173`

### 3. Launch Streamlit Debug & Chat Inspector

```bash
cd clinical-rag
source .venv/bin/activate
streamlit run frontend/app.py
```
- Streamlit Dashboard URL: `http://localhost:8501`

---

## 9. Role-Based Access Control (RBAC)

RBAC is enforced on the server ([`src/agent/supervisor.py`](clinical-rag/src/agent/supervisor.py)).

### Role Matrix

| Role | Guidelines RAG | Symptoms & Signs Checkers | Calendar Integration | View Registered Users |
|---|---|---|---|---|
| **Doctor** (`doctor`) | ✅ Yes | ✅ Yes | ✅ Yes (n8n Webhook) | ✅ Yes (`/auth/users`) |
| **Patient** (`patient`) | ✅ Yes | ✅ Yes (Bilingual Triage) | ❌ Excluded Server-Side | ❌ Excluded |

### Default Demo Accounts (Seeded automatically into `users.csv`)
- **Doctor Account**: `username: doctor` / `password: doctor123`
- **Patient Account**: `username: patient` / `password: patient123`

### CLI Account Management ([`src/api/auth.py`](clinical-rag/src/api/auth.py))

```bash
# List all registered accounts
python -m src.api.auth list

# Add a doctor user account
python -m src.api.auth add dr_alice doctor --name "Dr. Alice" --password "doctorpassword123"

# Add a patient user account (prompts interactively for password)
python -m src.api.auth add john_patient patient --name "John Doe"
```

---

## 10. API Endpoint Reference

### Health & Diagnostics

#### `GET /health`
Returns system status, active vector count, LLM status, and active session numbers.
```json
{
  "status": "ok",
  "llm": "gemma4:31b-cloud",
  "vector_store": "connected (86 chunks)",
  "active_sessions": 2,
  "version": "0.4.0"
}
```

#### `GET /health/liveness`
Kubernetes liveness probe. Returns `{"status": "alive"}`.

#### `GET /health/readiness`
Kubernetes readiness probe. Validates index existence. Returns `{"status": "ready", "llm": true}`.

---

### Authentication (`/auth`)

#### `POST /auth/signup`
Registers a new user account and returns an initial bearer token.
- **Request Body**:
  ```json
  {
    "username": "dr_smith",
    "password": "Password123!",
    "name": "Dr. Smith",
    "role": "doctor"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "token": "a3f8c7...",
    "username": "dr_smith",
    "role": "doctor",
    "name": "Dr. Smith"
  }
  ```

#### `POST /auth/login`
Exchanges user credentials for a bearer token.
- **Request Body**: `{"username": "doctor", "password": "doctor123"}`
- **Response** (`200 OK`): Returns `token`, `username`, `role`, `name`.

#### `POST /auth/logout`
Revokes presented bearer token. Requires `Authorization: Bearer <token>`.

#### `GET /auth/me`
Fetches authenticated user profile. Requires `Authorization: Bearer <token>`.

#### `GET /auth/users`
Lists registered accounts in `users.csv`. Restricted to `doctor` role.

---

### Clinical Chat & RAG (`/chat`)

#### `POST /chat`
Sends a prompt to the supervisor agent. Returns final answer and source citations.
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "session_id": "session-101",
    "message": "What are the diagnostic criteria for Type 2 Diabetes?"
  }
  ```
- **Response**:
  ```json
  {
    "session_id": "session-101",
    "answer": "According to the HEARTS-D guideline, Type 2 Diabetes is diagnosed when...",
    "sources": [
      {
        "source": "type-2-diabetes-in-adults-management.pdf",
        "page": 14,
        "type": "diabetes"
      }
    ],
    "tools_used_count": 1,
    "tools_used": ["clinical_guidelines"]
  }
  ```

#### `POST /chat/stream`
Streams supervisor agent responses in real time via Server-Sent Events (SSE).
- **Headers**: `Authorization: Bearer <token>`
- **Emitted Event Types**:
  - `event: token`: `{"token": "chunk text..."}`
  - `event: tool_start`: `{"tool": "clinical_guidelines", "args": {...}}`
  - `event: final`: `{"session_id": "...", "answer": "...", "sources": [...]}`
  - `event: error`: `{"error": "message"}`

#### `POST /chat/debug`
Same as `/chat`, but returns detailed retrieval metadata (per-iteration queries, candidate counts, relevance grades) and tool call history.

#### `GET /chat/sessions`
Returns active chat sessions for the authenticated user.

#### `GET /chat/sessions/{session_id}/history`
Fetches conversation message history for a specific session.

#### `DELETE /chat/sessions/{session_id}`
Clears memory and resets supervisor state for the specified session.

---

## 11. Specialized Agent Tools

The platform provides specialized tools ([`src/agent/patient.py`](clinical-rag/src/agent/patient.py), [`src/agent/tools.py`](clinical-rag/src/agent/tools.py)):

1. **`clinical_guidelines`**:
   - LangChain tool wrapping the complete agentic RAG pipeline.
   - Executes hybrid retrieval, RRF fusion, cross-encoder reranking, relevance grading, and citation generation.

2. **`symptoms_checker(symptoms: str)`**:
   - Analyzes patient-reported symptoms.
   - Extracts structured details: symptom type, location, severity, and duration.
   - Provides safe recommendations and emergency red-flag warnings.
   - Responds in **English or Arabic** matching the input language.
   - Appends medical disclaimer: *"This is not medical advice. Consult a doctor."*

3. **`signs_checker(vital: str)`**:
   - Evaluates vital signs, physical measurements, and laboratory values (e.g. blood pressure, blood glucose, heart rate).
   - Detects abnormal clinical ranges and provides recommendations.

4. **`manage_calendar(text: str)`**:
   - Sends calendar queries to the n8n sub-agent webhook (`https://yacine105.app.n8n.cloud/webhook/cal-subagent`).
   - Doctor role only.

5. **`get_current_time()`**:
   - Returns ISO current timestamp for resolving relative time queries ("today", "tomorrow").

---

## 12. Frontend Applications

### 1. Gastro AI React Web App (`frontweb/gastro-ai`)
- Built with React 18, TypeScript, and Vite.
- Dark glassmorphic design system with CSS variables.
- Voice Interaction: Web Speech API recognition and text-to-speech synthesis with animated voice orb.
- Configurable environment (`VITE_API_URL` and `VITE_USE_MOCK_API`).

### 2. Streamlit Clinical Inspector (`frontend/app.py`)
- Python web application with Streamlit.
- Features dual-tab login & signup forms.
- Real-time SSE streaming toggle and debug trace expander.
- Live API health diagnostics indicator in sidebar.

---

## 13. Testing & Evaluation

### Running Pytest Test Suite

```bash
# Run all unit and integration tests
python -m pytest

# Ingestion unit tests (Offline, fast)
python -m pytest tests/test_ingestion.py -v

# Conversational memory tests
python -m pytest tests/test_memory.py -s -v

# Retrieval inspection (Dense, BM25, Hybrid, Reranking without LLM)
python -m pytest tests/test_retrieval.py -s -v

# Evaluation benchmark (8 clinical questions comparing Baseline vs Agentic RAG)
python -m pytest tests/test_dataset.py -s -v
```

### Benchmark Metrics (`tests/test_dataset.py`)
- **Hit Rate@3 / Hit Rate@5**: Fraction of test queries where at least 1 expected evidence chunk appears in top $K$.
- **Recall@5**: Fraction of expected evidence strings retrieved.
- **MRR@5 (Mean Reciprocal Rank)**: Reciprocal rank of the first hit.

---

## 14. Limitations & Safety Disclaimers

- **Guideline Bound**: System responses are restricted to PDF documents in `data/`. The assistant does not invent medical facts or query external web sources.
- **Ollama Cloud Dependency**: LLM generation depends on Ollama cloud service availability (`gemma4:31b-cloud`).
- **Memory Lifetime**: Sessions are stored in-memory (`SessionManager`). Restarting the server clears active session state unless replaced by Redis/PostgreSQL.
- **Educational Use Warning**: This system is designed exclusively for research and educational purposes. It does not provide medical diagnoses or replace qualified medical professionals.