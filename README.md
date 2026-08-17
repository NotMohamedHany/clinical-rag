# Clinical Guidelines RAG — Agentic RAG API

An agentic retrieval-augmented-generation backend for clinical guidelines
(bundled example: the WHO **HEARTS-D** guideline, "Diagnosis and Management
of Type 2 Diabetes"). It answers guideline questions strictly from the
retrieved evidence, with conversation memory, query improvement, hybrid
retrieval, local reranking, relevance grading with retry, and source
citations. Any guideline PDF can be added — see §5.

**Educational/research use only.** The system never diagnoses, never
prescribes, and explicitly says when the guideline does not contain enough
information.

---

## Quickstart

Start everything from scratch in six steps:

```bash
# 0. Prerequisites: Python 3.11+, and Ollama running with the model pulled
ollama list | grep gemma4:31b-cloud || ollama run gemma4:31b-cloud

# 1. Install dependencies (first time only)
cd clinical-rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. (Optional) add guideline PDFs - any number, any illness
#    cp my_guideline.pdf data/          or: mkdir data/<type> && cp ... data/<type>/

# 3. Ingest: PDFs -> chunks -> ChromaDB + BM25 index (idempotent)
python -m src.ingestion.ingest

# 4. Start the API
uvicorn src.api.main:app --reload        # http://localhost:8000/docs

# 5. (Optional) start the Streamlit chat UI
streamlit run frontend/app.py            # http://localhost:8501

# 6. Try it
curl -X POST "http://localhost:8000/chat" -H "Content-Type: application/json" \
  -d '{"session_id": "demo-1", "message": "What are the diagnostic criteria for diabetes?"}'
```

Steps 1–2 are one-time setup; steps 3–5 are what you run every time you
start the project. Details for each step follow below.

---

## 1. Architecture

```text
                         HTTP Request
                              │
                              ▼
                          FastAPI
                              │
                              ▼
                       RAG Agent Graph            (LangGraph)
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
             Conversation Memory   Query Analyzer (Gemma)
                    │                   │
                    │                   ▼
                    │             Query Rewriter
                    │                   │
                    │                   ▼
                    │             Hybrid Search
                    │            ┌──────┴──────┐
                    │            ▼             ▼
                    │         Vector          BM25
                    │            │             │
                    │            └──────┬──────┘
                    │                   ▼
                    │              RRF Fusion
                    │                   │
                    │                   ▼
                    │               Reranker
                    │                   │
                    │                   ▼
                    │             Top Documents
                    │                   │
                    │                   ▼
                    │            Relevance Grader (Gemma)
                    │             /           \
                    │          GOOD           BAD
                    │           │              │
                    │           │         Rewrite Query
                    │           │              │
                    │           │              └──→ Hybrid Search
                    │           │                (max 2 iterations)
                    │           ▼
                    │         Ollama (Gemma)
                    └───────────┤
                                ▼
                         Final Answer
                                │
                                ▼
                          Source Citations
```

Data flow per request:

```text
Conversation Memory ──► Query Understanding (rewrite with history)
Clinical Documents ──► Hybrid Retrieval (vector + BM25 + RRF + rerank)
                    ──► Relevance Grading ──► (retry if < 0.70, max 2)
                    ──► Gemma generation with citations
```

## 2. Installation

Requires Python 3.11+, a running [Ollama](https://ollama.com) server, and
network access for one-time model downloads (embeddings, reranker, and the
Ollama cloud model).

```bash
cd clinical-rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> On Linux, install the CPU-only torch first to avoid the large CUDA wheel:
> `pip install torch --index-url https://download.pytorch.org/whl/cpu`

## 3. Ollama setup

Install Ollama and make sure the server is running:

```bash
ollama serve          # (or start the Ollama app)
```

`gemma4:31b-cloud` is an **Ollama cloud model** — it is NOT a fully local
model. It is served by Ollama through ollama.com, so usage is billed by
Ollama's cloud tier. Obtain/use it with the standard registry command
(which auto-pulls if needed):

```bash
ollama run gemma4:31b-cloud
```

You can verify it is available with:

```bash
ollama list
```

## 4. Model setup

Three models are used; only the LLM needs Ollama:

| Purpose | Model | Runs | First-use download |
|---|---|---|---|
| Dense embeddings | `sentence-transformers/all-MiniLM-L6-v2` | local | ~90 MB |
| Reranker | `BAAI/bge-reranker-v2-m3` | local | ~2.2 GB |
| LLM (rewrite/grade/generate) | `gemma4:31b-cloud` | Ollama cloud | none (cloud) |

Configuration lives in `.env` (see `.env.example`):

```bash
OLLAMA_MODEL=gemma4:31b-cloud
OLLAMA_BASE_URL=http://localhost:11434
```

### Hugging Face access token (optional)

The two local models are public, so no token is required — but Hugging
Face throttles anonymous downloads, so setting a token makes the first
downloads faster. Get a read token at
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens),
then either:

- add `HF_TOKEN=hf_xxxxxx` to `.env` (project-scoped; `.env` is already
  loaded by `src/config.py`), or
- run `hf auth login` once (machine-wide; stored in `~/.cache/huggingface/`).

The embedding model, the reranker and the BM25 index are lazy singletons:
each is loaded/built **once per process** and reused by every request, so
repeated searches never reload them (first query pays the load, later
queries do not).

## 5. Ingestion

```bash
python -m src.ingestion.ingest
```

**Not tied to one illness.** Every `*.pdf` under `data/` is ingested — add
a new guideline at any time and re-run ingestion; the new chunks are added
incrementally and old ones are untouched.

Each guideline gets a clinical **`type`** that is stored in every chunk's
metadata (`{"source", "page", "type"}`) and shown in API sources. The type
is resolved automatically:

```text
data/hypertension/guideline.pdf      -> type "hypertension" (directory name)
data/diabetes_guideline.pdf          -> type "diabetes"     (filename stem)
data/covid19.pdf                     -> type "covid19"      (plain stem)
```

So adding a guideline is just:

```bash
cp hypertension_guideline.pdf data/          # or: mkdir data/hypertension && cp ... data/hypertension/
python -m src.ingestion.ingest
```

File names must be unique across `data/` (chunk IDs are derived from them);
the script errors on duplicates.

Ingestion extracts pages with PyMuPDF, splits them (1000 chars, 200
overlap), stores chunks + embeddings in ChromaDB (`chroma_db/`, collection
`clinical_guidelines`) — **idempotent**: stable chunk IDs mean re-runs add
nothing, and chunks stored by older versions are automatically backfilled
with the `type` field — and persists the chunk corpus for BM25 to
`bm25/bm25_corpus.pkl`.

To rebuild from scratch: `rm -rf chroma_db bm25` and re-run ingestion.

## 6. BM25 index creation

The BM25 index is built automatically from `bm25/bm25_corpus.pkl` when the
API starts (once per process), then reused for every request — it is not
rebuilt per request. Rebuild the corpus by re-running ingestion.

## 7. Running FastAPI

```bash
uvicorn src.api.main:app --reload
```

The API is then at `http://localhost:8000` (interactive docs at
`/docs`). Startup loads the RAG agent and both retrieval indexes.

## 8. API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service status (LLM + vector store) |
| `/chat` | POST | Ask a question; returns answer + sources |
| `/chat/debug` | POST | Same, plus concise retrieval metadata |

### `/health`

```json
{
  "status": "ok",
  "llm": "gemma4:31b-cloud",
  "vector_store": "connected (86 chunks)"
}
```

### `/chat`

Request:

```json
{
  "session_id": "abc123",
  "message": "What are the diagnostic criteria for diabetes?"
}
```

Response:

```json
{
  "session_id": "abc123",
  "answer": "...",
  "sources": [
    {"source": "diabetes_guideline.pdf", "page": 13, "type": "diabetes"}
  ]
}
```

### `/chat/debug`

Same request; response adds `original_query` and `iterations` with
`query`, `hybrid_results`, `reranked_results`, and `relevance_score` per
retrieval attempt. No chain-of-thought is exposed.

Errors: `400` invalid request (empty message/session), `503` for
unavailable Ollama or missing indexes, `500` for unexpected failures
(stack traces are logged server-side, never returned).

### Streamlit frontend

A simple chat UI lives in `frontend/app.py`. With the API running, start it
from the project root:

```bash
streamlit run frontend/app.py
```

It opens a chat at `http://localhost:8501` with a session-ID field, a
live `/health` indicator, and a **Debug mode** toggle that shows the
retrieval process (queries, candidate counts, relevance scores) per
question. Chat history is kept per session on the API side, so follow-up
questions like "What about HbA1c?" resolve against earlier turns.

## 9. Example curl requests

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "message": "What are the diagnostic criteria for diabetes?"
  }'
```

A follow-up that uses conversation memory:

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-1",
    "message": "What about HbA1c?"
  }'
```

## 10. Memory

Per-session, in-memory conversation memory (`src/memory/conversation.py`).
Each session keeps its last user/assistant exchanges; the query rewriter
uses them to resolve references ("this", "that", "HbA1c" after "diabetes
diagnosis"). Conversation history is **never** written into the vector
database — memory and document retrieval are separate. The
`ConversationMemory` class is the only interface the API depends on, so it
can later be swapped for Redis or PostgreSQL.

## 11. Hybrid search

Two independent retrieval methods run in parallel:

- **Dense** (`src/rag/vector_search.py`): ChromaDB + `all-MiniLM-L6-v2`,
  `VECTOR_K = 10`
- **Sparse** (`src/rag/bm25_search.py`): BM25 (`rank-bm25`) over the
  persisted corpus, `BM25_K = 10`

Each returns chunks with a stable `chunk_id`, content, and
`{source, page}` metadata.

## 12. RRF (Reciprocal Rank Fusion)

`src/rag/hybrid_search.py` merges both ranked lists:

```python
score(doc) = Σ 1 / (k + rank + 1)     # k = 60
```

Duplicates (chunks found by both methods) are merged into one entry with
the combined score. The result is ~10–20 candidates ordered best-first.

## 13. Reranking

`src/rag/reranker.py` scores the hybrid candidates with the free, local
cross-encoder `BAAI/bge-reranker-v2-m3` and keeps the top 5. Reranker
scores are cross-encoder logits, not vector similarity — they are only
comparable within one query's candidate set.

## 14. Query rewriting

`src/rag/query_rewriter.py` uses Gemma to turn the user's question (plus
conversation history, plus any grading feedback) into a search-friendly
retrieval query. It preserves intent, resolves references, adds clinical
terminology, never answers the question, and returns only the query. If the
original is already good, it is kept unchanged.

## 15. Relevance grading

`src/rag/relevance_grader.py` asks Gemma whether the reranked context is
sufficient, with structured output:

```python
class RelevanceGrade(BaseModel):
    relevant: bool
    score: float      # 0-1
    reason: str
```

`score >= 0.70` proceeds to generation.

## 16. Self-improving retrieval

```text
Original Query → Rewriter → Hybrid Search → Rerank → Grade
    score >= 0.70 → Generate
    score <  0.70 → Rewrite (with grader feedback) → Search again
```

`MAX_ITERATIONS = 2` bounds the loop — never infinite. The second attempt
sees the grader's reason and can target its query accordingly. If evidence
still grades below threshold, generation runs on the best available chunks
and must state that the guideline lacks sufficient information. Each
attempt is recorded in `search_history` (query + relevance score) and
surfaced by `/chat/debug`.

## Running the tests

Run the whole suite from the project root:

```bash
python -m pytest
```

Or individual files:

```bash
python -m pytest tests/test_ingestion.py -v     # ingestion unit tests (fast, no models)
python -m pytest tests/test_retrieval.py -s -v  # manual retrieval inspection (no LLM)
python -m pytest tests/test_dataset.py -s -v    # 8-question evaluation (baseline + agentic)
python -m pytest tests/test_memory.py -s -v     # conversational memory test
```

Useful flags:

```bash
python -m pytest tests/test_dataset.py -s    # -s: print the evaluation report
python -m pytest -k baseline -q              # run only tests matching "baseline"
```

Notes:

- **LLM tests skip when Ollama is down** — the agentic evaluation and the
  memory test are skipped automatically with a clear message if the Ollama
  server is unreachable. Everything else runs offline.
- **Cloud usage**: the non-skipped LLM tests make real calls to the Ollama
  cloud model (`gemma4:31b-cloud`) and take a few minutes; the rest of the
  suite is local.
- **First run** downloads the embedding model and the 2.2 GB reranker (see
  §4 for the optional HF token to speed this up).
- The test suite assumes ingestion has run (`python -m src.ingestion.ingest`)
  so `chroma_db/` and `bm25/` exist — except `tests/test_ingestion.py`,
  which is self-contained.

## 17. Evaluation metrics

```bash
python -m pytest tests/test_dataset.py -s -v
```

Runs 8 clinical questions through the real retrieval pipeline (hybrid
search + rerank, no LLM for judging) and reports:

- **Hit Rate@3 / Hit Rate@5** — fraction of questions with ≥1 chunk
  containing an expected evidence string in the top K
- **Recall@5** — fraction of expected evidence strings found
- **MRR@5** — mean reciprocal rank of the first hit

Two modes are evaluated so you can compare the query-improvement agent:

```
Baseline Hit Rate@5  vs  Agentic Hit Rate@5
Baseline MRR@5       vs  Agentic MRR@5
```

The agentic mode needs Ollama and is skipped (with a clear message) when
it is unavailable. Matching uses normalized text (lowercase, whitespace,
Unicode ≥/≤, dashes, `mL/minute` vs `ml/min`); the retrieved text is never
modified. For the full test suite and per-file commands see the
"Running the tests" section above.

## 18. Limitations

- **Supplied guidelines only**: the system answers from whatever guideline
  PDFs are in `data/` — no external medical knowledge, no web search. Each
  answer cites the source file, page and guideline `type`.
- **Cloud LLM**: `gemma4:31b-cloud` is an Ollama cloud model — responses
  depend on Ollama's cloud tier, availability, and billing. If Ollama is
  unreachable the API returns a clear 503.
- **Retrieval quality** depends on the embedding/reranker models and chunk
  size; short low-information chunks (title page, table of contents) can
  occasionally outrank substantive content for some queries.
- **In-memory memory**: sessions are lost on restart; swap
  `ConversationMemory` for Redis/PostgreSQL for production.
- **Not medical advice**: educational/research only. Answers cite the
  guideline and never replace a clinician. The generator is instructed to
  state when the guideline is insufficient and to never fabricate
  citations.

## 19. Calendar agent (ReAct + MCP)

A separate, standalone agent: a **ReAct** (reason + act) loop on the same
Ollama model (`gemma4:31b-cloud`) whose tools include **Google Calendar
via MCP**. Ask about your schedule, free time, or ask it to create events.

```bash
python calendar_agent.py                          # interactive chat
python calendar_agent.py --prompt "What events do I have today?"
python calendar_agent.py --mock                   # force the mock calendar
```

Files:

| File | Purpose |
|---|---|
| `calendar_agent.py` | The ReAct agent: `create_agent` (LangChain) + `get_current_time` + MCP calendar tools |
| `mcp_servers/mock_calendar.py` | Local MOCK MCP calendar server (stdio) mirroring Google's tool surface |
| `google_calendar_auth.py` | One-time OAuth helper to obtain a Google refresh token |

### Calendar modes

- **Mock (default, no setup):** without Google credentials the agent talks
  to the local mock server — same tool names, fake in-memory data. Good for
  testing the agent loop offline.
- **Real Google Calendar:** connects to Google's hosted Calendar MCP
  connector (`https://api.google.com/mcp/calendar/v1/sse`) with the same
  tool names — swapping mock → real is purely configuration.

### Real Google Calendar setup (one time, ~5 minutes)

1. In the [Google Cloud Console](https://console.cloud.google.com): create
   a project, enable the **Google Calendar API**, create an OAuth client of
   type **Desktop app** (redirect `http://127.0.0.1:8765`).
2. Obtain a refresh token:

   ```bash
   python google_calendar_auth.py --client-id <id> --client-secret <secret>
   ```

   (approve the consent screen in the browser; add `--write-env` to append
   the token to `.env` automatically)
3. Put the credentials in `.env`:

   ```bash
   GOOGLE_CALENDAR_REFRESH_TOKEN=...
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```

   The agent refreshes the access token automatically on every run.

Tools exposed by the calendar MCP (both mock and real): `get_calendar_list`,
`get_events`, `search_events`, `create_event`, `update_event`,
`delete_event`, `get_free_busy`.

The MCP connection logic is shared in `src/agent/calendar_mcp.py`
(`calendar_tools()` async context manager), so any agent can reuse it.

## 20. Supervisor agent (RAG as one tool)

The entire RAG pipeline is wrapped as **one LangChain tool** -
`clinical_guidelines` in `src/rag/rag_tool.py` - so a supervisor agent can
use it alongside anything else (here: the calendar MCP tools). The
supervisor LLM decides per question which tool(s) to call.

```text
         supervisor_agent.py (create_agent)
                     │
        ┌────────────┼─────────────┐
        ▼            ▼             ▼
 clinical_guidelines   get_current_time   calendar MCP tools
 (the whole RAG graph  │                    (mock or real Google)
  as one tool: memory→ │
  rewrite→hybrid→rerank│
  →grade→generate→cites)│
```

```bash
python supervisor_agent.py                        # interactive
python supervisor_agent.py --prompt "What are the diagnostic criteria for diabetes?"
python supervisor_agent.py --prompt "What events do I have today?"
python supervisor_agent.py --prompt "What are the diagnostic criteria for diabetes, and what events do I have tomorrow?"
```

Each `clinical_guidelines` call runs the complete RAG pipeline (conversation
memory, query rewrite, hybrid search, reranking, relevance grading with
retry, generation) and returns the answer with `[Retrieved sources:
<file> (<type>, page N)]`, so the supervisor gets cited evidence without
seeing any internals. Conversation memory persists per session across calls
in the same process.

Shared agent helpers: `src/agent/calendar_mcp.py` (MCP connection),
`src/agent/chat.py` (stream printing), `src/agent/tools.py`
(`get_current_time`). The calendar agent (`calendar_agent.py`) uses the
same modules.

## Data flow (recap)

```text
data/*.pdf (any number, typed by location/filename)
    → PyMuPDF pages → RecursiveCharacterTextSplitter (1000/200)
    → chunks carry {source, page, type} metadata
    → ChromaDB (dense) + bm25_corpus.pkl (sparse)
    → per request: memory → rewrite → vector + BM25 → RRF → rerank
    → grade → (retry ≤ 2) → Gemma → answer + {source, page, type} citations
```
