"""Clinical Chat & RAG API Router."""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

import chromadb
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_ollama import ChatOllama

from src import config
from src.api.auth import User, require_role
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    DebugResponse,
    IterationInfo,
    SessionHistoryResponse,
    SessionInfoResponse,
    SessionListResponse,
    SessionMessage,
    Source,
    ToolCallInfo,
)
from src.api.session_manager import session_manager
from src.rag.llm import is_ollama_connection_error

logger = logging.getLogger("clinical_rag.api.chat")

router = APIRouter(prefix="/chat", tags=["Clinical Chat & RAG"])

_llm: ChatOllama | None = None


def get_shared_llm() -> ChatOllama:
    """Lazy initialize the shared ChatOllama instance."""
    global _llm
    if _llm is None:
        _llm = ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL)
    return _llm


def _validate_request(payload: ChatRequest) -> None:
    if not payload.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id must not be empty")
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")


def _check_indexes() -> None:
    """Fail fast with a clear 503 if vectors or BM25 index are missing."""
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


def _extract_trace(messages: list) -> tuple[list[dict], list[dict], list[dict]]:
    """Extract sources, retrieval iterations, and tool call traces across all tools."""
    sources: list[dict] = []
    iterations: list[dict] = []
    tool_calls: list[dict] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                tool_calls.append({"tool": call["name"], "args": json.dumps(call["args"])})
        elif isinstance(message, ToolMessage):
            try:
                data = json.loads(message.content)
                if isinstance(data, dict):
                    if "sources" in data and isinstance(data["sources"], list):
                        sources.extend(data["sources"])
                    if "retrieval" in data and isinstance(data["retrieval"], list):
                        iterations.extend(data["retrieval"])
            except (json.JSONDecodeError, TypeError):
                pass

    # Deduplicate sources preserving order
    merged: list[dict] = []
    seen: set[tuple] = set()
    for source in sources:
        key = (source.get("source"), source.get("page"))
        if key not in seen:
            seen.add(key)
            merged.append(source)
    return merged, iterations, tool_calls


async def _run(payload: ChatRequest, request: Request, user: User) -> dict:
    """Execute supervisor agent for one conversation turn."""
    llm = get_shared_llm()
    session = session_manager.get_or_create_session(
        user.username, payload.session_id, user.role, llm
    )
    start = time.monotonic()

    turn_start = len(session["messages"])
    session["messages"].append(HumanMessage(content=payload.message))

    result = await session["agent"].ainvoke({"messages": session["messages"]})

    session["messages"] = result["messages"]
    final_messages = result["messages"]
    answer = final_messages[-1].content if final_messages else ""

    sources, iterations, tool_calls = _extract_trace(final_messages[turn_start:])
    latency_ms = (time.monotonic() - start) * 1000

    logger.info(
        "session=%s user=%s latency_ms=%.0f tool_calls=%d sources=%d",
        payload.session_id,
        user.username,
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


@router.post("", response_model=ChatResponse, summary="Send question to Supervisor Agent")
async def chat(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(require_role("doctor", "patient")),
) -> ChatResponse:
    """Send a prompt to the supervisor agent (returns final answer + citations)."""
    _validate_request(payload)
    _check_indexes()
    try:
        res = await _run(payload, request, user)
        return ChatResponse(
            session_id=payload.session_id,
            answer=res["answer"],
            sources=[Source(**s) for s in res["sources"]],
        )
    except Exception as exc:
        if is_ollama_connection_error(exc):
            raise HTTPException(
                status_code=503,
                detail=f"Ollama is unavailable at {config.OLLAMA_BASE_URL} (model: {config.OLLAMA_MODEL}).",
            ) from exc
        raise


@router.post("/debug", response_model=DebugResponse, summary="Send question with full debug trace")
async def chat_debug(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(require_role("doctor", "patient")),
) -> DebugResponse:
    """Send a prompt and return the detailed tool & retrieval execution trace."""
    _validate_request(payload)
    _check_indexes()
    try:
        res = await _run(payload, request, user)
        return DebugResponse(
            session_id=payload.session_id,
            original_query=payload.message,
            iterations=[IterationInfo(**i) for i in res["iterations"]],
            tool_calls=[ToolCallInfo(**c) for c in res["tool_calls"]],
            final_answer=res["answer"],
            sources=[Source(**s) for s in res["sources"]],
        )
    except Exception as exc:
        if is_ollama_connection_error(exc):
            raise HTTPException(
                status_code=503,
                detail=f"Ollama is unavailable at {config.OLLAMA_BASE_URL}.",
            ) from exc
        raise


@router.post("/stream", summary="Stream agent response via Server-Sent Events (SSE)")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    user: User = Depends(require_role("doctor", "patient")),
):
    """Stream supervisor agent response in real time via SSE events (`event: token`, `event: final`)."""
    _validate_request(payload)
    _check_indexes()

    llm = get_shared_llm()
    session = session_manager.get_or_create_session(
        user.username, payload.session_id, user.role, llm
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            turn_start = len(session["messages"])
            session["messages"].append(HumanMessage(content=payload.message))

            async for event in session["agent"].astream({"messages": session["messages"]}):
                for payload_data in event.values():
                    message = payload_data["messages"][-1]
                    if isinstance(message, AIMessage):
                        if message.content:
                            data = json.dumps({"token": message.content})
                            yield f"event: token\ndata: {data}\n\n"
                        for call in message.tool_calls:
                            tool_data = json.dumps({"tool": call["name"], "args": call["args"]})
                            yield f"event: tool_start\ndata: {tool_data}\n\n"

            final_res = await _run(payload, request, user)
            final_data = json.dumps(
                {
                    "session_id": payload.session_id,
                    "answer": final_res["answer"],
                    "sources": final_res["sources"],
                }
            )
            yield f"event: final\ndata: {final_data}\n\n"

        except Exception as exc:
            err_data = json.dumps({"error": str(exc)})
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Session Management Routes
# ---------------------------------------------------------------------------


@router.get("/sessions", response_model=SessionListResponse, summary="List active user sessions")
def list_sessions(user: User = Depends(require_role("doctor", "patient"))) -> SessionListResponse:
    """Return all active chat sessions belonging to the authenticated user."""
    sessions = session_manager.list_user_sessions(user.username)
    return SessionListResponse(
        total=len(sessions),
        sessions=[SessionInfoResponse(**s) for s in sessions],
    )


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse, summary="Get session message history")
def get_session_history(
    session_id: str,
    user: User = Depends(require_role("doctor", "patient")),
) -> SessionHistoryResponse:
    """Fetch conversation message history for a specific session."""
    llm = get_shared_llm()
    session_manager.get_or_create_session(user.username, session_id, user.role, llm)
    history = session_manager.get_session_history(user.username, session_id) or []
    return SessionHistoryResponse(
        session_id=session_id,
        messages=[SessionMessage(**m) for m in history],
    )


@router.delete("/sessions/{session_id}", summary="Reset or clear session")
def clear_session(
    session_id: str,
    user: User = Depends(require_role("doctor", "patient")),
) -> dict:
    """Clear memory and reset supervisor state for a session."""
    session_manager.clear_session(user.username, session_id)
    return {"ok": True, "message": f"Session {session_id} cleared"}
