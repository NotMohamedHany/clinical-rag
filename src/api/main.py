"""FastAPI application entry point.

Assembles modular routers (Health, Auth, Clinical Chat & RAG), configures CORS and request-ID
tracing middleware, and provides standardized error handlers.

Run from project root:

    uvicorn src.api.main:app --reload
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import config
from src.api.auth import ensure_users_csv
from src.api.routers import auth as auth_router
from src.api.routers import chat as chat_router
from src.api.routers import health as health_router
from src.api.schemas import APIErrorResponse, ErrorDetail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("clinical_rag.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup & shutdown lifecycle."""
    logger.info("Initializing Clinical Guidelines RAG API v0.4.0")
    ensure_users_csv()
    logger.info("Users registry ready at %s", config.USERS_CSV_PATH)
    yield
    logger.info("Shutting down Clinical Guidelines RAG API")


tags_metadata = [
    {
        "name": "Health & Diagnostics",
        "description": "System health, container probes, readiness, and active statistics.",
    },
    {
        "name": "Authentication",
        "description": "Role-based authentication, token issuance, user profile, and user management.",
    },
    {
        "name": "Clinical Chat & RAG",
        "description": "Agentic RAG queries, SSE real-time streaming, trace debugging, and session management.",
    },
]

app = FastAPI(
    title="Clinical Guidelines RAG API",
    description=(
        "Production-ready API for Clinical Guidelines RAG and Supervisor Assistant. "
        "Supports doctor & patient roles, real-time SSE streaming, hybrid vector+BM25 search, "
        "and multi-tool agent traces."
    ),
    version="0.4.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# CORS middleware for development frontends (Streamlit, Next.js, Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request ID and log latency for every HTTP request."""
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    start = time.monotonic()
    
    response = await call_next(request)
    
    latency_ms = (time.monotonic() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    
    logger.info(
        "request_id=%s method=%s path=%s status=%d latency_ms=%.0f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Format HTTP exceptions into standard API error schema."""
    req_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=APIErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                request_id=req_id,
            )
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler preventing stack trace leaks."""
    req_id = getattr(request.state, "request_id", "?")
    logger.exception(
        "unhandled error request_id=%s path=%s: %s",
        req_id,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content=APIErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred.",
                request_id=req_id,
            )
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Router Composition
# ---------------------------------------------------------------------------

app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(chat_router.router)
