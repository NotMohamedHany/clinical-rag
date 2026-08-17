"""FastAPI application: /health, /chat, /chat/debug.

The chat endpoints run the SUPERVISOR agent: one agent whose tools are the
whole RAG pipeline (clinical_guidelines) plus the n8n calendar webhook
(manage_calendar). Each conversation session gets its own supervisor
instance with tools bound to that session, so follow-up questions keep
their context end to end.

Run from the project root:

    uvicorn src.api.main:app --reload
"""

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_ollama import ChatOllama

from src import config
from src.agent.supervisor import build_supervisor
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    DebugResponse,
    IterationInfo,
    Source,
    ToolCallInfo,
)
from src.rag.llm import is_ollama_available, is_ollama_connection_error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("clinical_rag.api")

# One supervisor per conversation session: {"agent": ..., "messages": [...]}.
# In-memory for now - swap for Redis/PostgreSQL for horizontal scaling.
_sessions: dict[str, dict] = {}
_llm: ChatOllama | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare the shared LLM once at startup."""
    global _llm
    logger.info("initializing supervisor API")
    _llm = ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL)
    yield


app = FastAPI(title="Clinical Guidelines RAG API", version="0.3.0", lifespan=lifespan)

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
# Chat (supervisor agent)
# ---------------------------------------------------------------------------


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


def _get_session(session_id: str) -> dict:
    """The supervisor agent + message history for one conversation session."""
    session = _sessions.get(session_id)
    if session is None:
        if _llm is None:
            raise RuntimeError("LLM is not initialized - application startup failed")
        session = {"agent": build_supervisor(_llm, session_id), "messages": []}
        _sessions[session_id] = session
    return session


def _extract_trace(messages: list) -> tuple[list[dict], list[dict]]:
    """Collect (sources, retrieval iterations, tool calls) from the agent run.

    The clinical_guidelines tool returns JSON containing the answer's
    sources and the per-attempt retrieval trace; tool calls are read from
    the AIMessages.
    """
    sources: list[dict] = []
    iterations: list[dict] = []
    tool_calls: list[dict] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                tool_calls.append({"tool": call["name"], "args": json.dumps(call["args"])})
        elif isinstance(message, ToolMessage) and message.name == "clinical_guidelines":
            try:
                data = json.loads(message.content)
                sources.extend(data.get("sources", []))
                iterations.extend(data.get("retrieval", []))
            except (json.JSONDecodeError, TypeError):
                logger.warning("could not parse clinical_guidelines tool result")

    # Merge duplicate sources (same file + page) preserving order.
    merged: list[dict] = []
    seen: set[tuple] = set()
    for source in sources:
        key = (source.get("source"), source.get("page"))
        if key not in seen:
            seen.add(key)
            merged.append(source)
    return merged, iterations, tool_calls


async def _run(payload: ChatRequest, request: Request) -> dict:
    """Run the supervisor for one turn and return the extracted result."""
    assert _llm is not None
    session = _get_session(payload.session_id)
    start = time.monotonic()
    logger.info(
        "request_id=%s session=%s query=%r",
        request.state.request_id,
        payload.session_id,
        payload.message,
    )

    # The trace (sources/iterations/tool calls) must cover only THIS turn,
    # not earlier turns in the conversation history.
    turn_start = len(session["messages"])
    session["messages"].append(HumanMessage(content=payload.message))
    result = await session["agent"].ainvoke({"messages": session["messages"]})

    # Keep the full message history (message objects, not dicts) so the
    # supervisor has conversation context on the next turn.
    session["messages"] = result["messages"]
    final_messages = result["messages"]
    answer = final_messages[-1].content if final_messages else ""

    sources, iterations, tool_calls = _extract_trace(final_messages[turn_start:])
    latency_ms = (time.monotonic() - start) * 1000
    logger.info(
        "session=%s latency_ms=%.0f tool_calls=%d sources=%d",
        payload.session_id,
        latency_ms,
        len(tool_calls),
        len(sources),
    )
    return {
        "answer": answer,
        "sources": sources,
        "iterations": iterations,
        "tool_calls": tool_calls,
    }


def _to_response(session_id: str, result: dict) -> ChatResponse:
    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
    )


def _to_debug_response(session_id: str, result: dict) -> DebugResponse:
    return DebugResponse(
        session_id=session_id,
        original_query=result.get("original_query", ""),
        iterations=[IterationInfo(**entry) for entry in result["iterations"]],
        tool_calls=[ToolCallInfo(**call) for call in result["tool_calls"]],
        final_answer=result["answer"],
        sources=[Source(**s) for s in result["sources"]],
    )


async def _chat(payload: ChatRequest, request: Request, debug: bool) -> ChatResponse | DebugResponse:
    """Shared handler for /chat and /chat/debug."""
    _validate_request(payload)
    _check_indexes()
    try:
        result = await _run(payload, request)
    except Exception as exc:  # noqa: BLE001 - connection errors map to 503
        if is_ollama_connection_error(exc):
            raise HTTPException(
                status_code=503,
                detail=f"Ollama is unavailable at {config.OLLAMA_BASE_URL} "
                f"(model: {config.OLLAMA_MODEL}). Start it with `ollama serve` "
                f"and make sure the model is pulled.",
            ) from exc
        raise
    if debug:
        result["original_query"] = payload.message
        return _to_debug_response(payload.session_id, result)
    return _to_response(payload.session_id, result)


@app.post("/chat")
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    return await _chat(payload, request, debug=False)


@app.post("/chat/debug")
async def chat_debug(payload: ChatRequest, request: Request) -> DebugResponse:
    return await _chat(payload, request, debug=True)


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
