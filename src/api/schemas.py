"""API request/response schemas. Kept separate from internal RAG state."""

from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    username: str = Field(min_length=1, description="Desired username")
    password: str = Field(min_length=1, description="Plaintext password")
    name: str = Field(default="", description="Full name or display name")
    role: str = Field(default="patient", description="Role: 'patient' or 'doctor'")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, description="Registered username")
    password: str = Field(min_length=1, description="Plaintext password")


class LoginResponse(BaseModel):
    token: str = Field(description="Bearer token for /chat requests")
    username: str
    role: str = Field(description="'doctor' or 'patient'")
    name: str


class UserProfileResponse(BaseModel):
    username: str
    role: str
    name: str


class UserListItem(BaseModel):
    username: str
    role: str
    name: str


# ---------------------------------------------------------------------------
# Chat & RAG Schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str = Field(description="Identifier for the conversation session")
    message: str = Field(description="The user's question or message")


class Source(BaseModel):
    source: str = Field(description="Name of the source document")
    page: int = Field(description="Page number in the source document")
    type: str | None = Field(
        default=None, description="Clinical guideline type (e.g. diabetes)"
    )


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[Source] = Field(default_factory=list)
    tools_used_count: int = Field(default=0, description="Total number of tool calls executed")
    tools_used: list[str] = Field(default_factory=list, description="Names of tools executed")


class IterationInfo(BaseModel):
    iteration: int
    query: str
    hybrid_results: int
    reranked_results: int
    relevance_score: float


class ToolCallInfo(BaseModel):
    """One tool call made during agent execution."""

    tool: str
    args: str
    output_preview: str | None = None


class DebugResponse(BaseModel):
    """Supervisor execution trace for inspection - concise metadata only."""

    session_id: str
    original_query: str
    iterations: list[IterationInfo] = Field(default_factory=list)
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    final_answer: str
    sources: list[Source] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session Schemas
# ---------------------------------------------------------------------------


class SessionInfoResponse(BaseModel):
    session_id: str
    message_count: int
    created_at: str
    last_active: str
    role: str


class SessionListResponse(BaseModel):
    total: int
    sessions: list[SessionInfoResponse]


class SessionMessage(BaseModel):
    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[SessionMessage]


# ---------------------------------------------------------------------------
# Health & Error Schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = Field(description="'ok' or 'degraded'")
    llm: str
    vector_store: str
    active_sessions: int
    version: str = "0.4.0"


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any = None


class APIErrorResponse(BaseModel):
    error: ErrorDetail
