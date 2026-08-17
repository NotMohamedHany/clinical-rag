"""FastAPI application: /health, /chat, /chat/debug.

Run from the project root:

    uvicorn src.api.main:app --reload
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import config
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    DebugResponse,
    IterationInfo,
    Source,
)
from src.memory.conversation import ConversationMemory
from src.rag.graph import RagAgent, run_chat
from src.rag.llm import OllamaUnavailableError, is_ollama_available

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("clinical_rag.api")

memory = ConversationMemory()
agent: RagAgent | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Load the RAG agent (and its indexes) once at startup."""
    global agent
    logger.info("initializing RAG agent")
    agent = RagAgent()
    yield


app = FastAPI(title="Clinical Guidelines RAG API", version="0.2.0", lifespan=lifespan)

# CORS: allow the future frontend during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request ID and log latency for every request."""
    request.state.request_id = uuid.uuid4().hex[:8]
    start = time.monotonic()
    response = await call_next(request)
    latency_ms = (time.monotonic() - start) * 1000
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%d latency_ms=%.0f",
        request.state.request_id,
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    """Report service status: LLM and vector store connectivity."""
    try:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        collection = client.get_collection(name=config.COLLECTION_NAME)
        vector_store = f"connected ({collection.count()} chunks)"
    except Exception as exc:  # noqa: BLE001
        logger.exception("vector store health check failed")
        vector_store = f"disconnected ({exc.__class__.__name__})"

    llm = config.OLLAMA_MODEL if is_ollama_available() else "unavailable"

    return {
        "status": "ok" if vector_store.startswith("connected") else "degraded",
        "llm": llm,
        "vector_store": vector_store,
    }


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def _get_agent() -> RagAgent:
    """The agent created at startup; a missing one is a server fault."""
    if agent is None:
        raise RuntimeError("RAG agent is not initialized - application startup failed")
    return agent


def _validate_request(payload: ChatRequest) -> None:
    if not payload.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id must not be empty")
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")


def _check_indexes() -> None:
    """Fail fast with a clear error when the retrieval layer is not ready."""
    try:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        client.get_collection(name=config.COLLECTION_NAME)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Vector store unavailable: run `python -m src.ingestion.ingest` first.",
        ) from exc
    if not config.BM25_CORPUS_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="BM25 index missing: run `python -m src.ingestion.ingest` first.",
        )


def _to_response(session_id: str, state: dict) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        answer=state["final_answer"],
        sources=[Source(**s) for s in state["sources"]],
    )


def _to_debug_response(session_id: str, state: dict) -> DebugResponse:
    iterations = [
        IterationInfo(
            iteration=entry["iteration"],
            query=entry["query"],
            hybrid_results=len(state.get("candidates", [])),
            reranked_results=len(state.get("top_chunks", [])),
            relevance_score=entry["relevance_score"],
        )
        for entry in state["search_history"]
    ]
    return DebugResponse(
        session_id=session_id,
        original_query=state["original_query"],
        iterations=iterations,
        final_answer=state["final_answer"],
        sources=[Source(**s) for s in state["sources"]],
    )


def _run(payload: ChatRequest, request: Request) -> dict:
    """Shared execution path for /chat and /chat/debug."""
    start = time.monotonic()
    logger.info(
        "request_id=%s session=%s query=%r",
        request.state.request_id,
        payload.session_id,
        payload.message,
    )
    state = run_chat(_get_agent(), memory, payload.session_id, payload.message)
    latency_ms = (time.monotonic() - start) * 1000
    logger.info(
        "session=%s latency_ms=%.0f iterations=%d",
        payload.session_id,
        latency_ms,
        len(state["search_history"]),
    )
    return state


def _chat(payload: ChatRequest, request: Request, debug: bool) -> ChatResponse | DebugResponse:
    """Shared handler for /chat and /chat/debug."""
    _validate_request(payload)
    _check_indexes()
    try:
        state = _run(payload, request)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if debug:
        return _to_debug_response(payload.session_id, state)
    return _to_response(payload.session_id, state)


@app.post("/chat")
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    return _chat(payload, request, debug=False)


@app.post("/chat/debug")
def chat_debug(payload: ChatRequest, request: Request) -> DebugResponse:
    return _chat(payload, request, debug=True)


# ---------------------------------------------------------------------------
# Error handling: log server-side, never expose stack traces
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "unhandled error request_id=%s path=%s: %s",
        getattr(request.state, "request_id", "?"),
        request.url.path,
        exc,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
