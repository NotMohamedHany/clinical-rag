"""Health & Diagnostics API Router."""

import logging
import chromadb

from fastapi import APIRouter, HTTPException

from src import config
from src.api.schemas import HealthResponse
from src.api.session_manager import session_manager
from src.rag.llm import is_ollama_available

logger = logging.getLogger("clinical_rag.api.health")

router = APIRouter(prefix="", tags=["Health & Diagnostics"])


@router.get("/health", response_model=HealthResponse, summary="Service health status")
def health() -> HealthResponse:
    """Report overall service status: LLM, vector store, active sessions."""
    try:
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        collection = client.get_collection(name=config.COLLECTION_NAME)
        vector_store = f"connected ({collection.count()} chunks)"
    except Exception as exc:  # noqa: BLE001
        logger.exception("vector store health check failed")
        vector_store = f"disconnected ({exc.__class__.__name__})"

    llm = config.OLLAMA_MODEL if is_ollama_available() else "unavailable"
    active_count = session_manager.get_active_session_count()

    return HealthResponse(
        status="ok" if vector_store.startswith("connected") else "degraded",
        llm=llm,
        vector_store=vector_store,
        active_sessions=active_count,
        version="0.4.0",
    )


@router.get("/health/liveness", summary="Kubernetes liveness probe")
def liveness() -> dict:
    """Basic liveness probe returning HTTP 200 if server is running."""
    return {"status": "alive"}


@router.get("/health/readiness", summary="Kubernetes readiness probe")
def readiness() -> dict:
    """Readiness check validating local storage and index existence."""
    if not config.BM25_CORPUS_PATH.exists():
        raise HTTPException(status_code=503, detail="BM25 index missing")
    return {"status": "ready", "llm": is_ollama_available()}
