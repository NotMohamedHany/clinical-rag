"""API request/response schemas. Kept separate from the internal RAG state."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(description="Identifier for the conversation")
    message: str = Field(description="The user's question")


class Source(BaseModel):
    source: str = Field(description="Name of the source document")
    page: int = Field(description="Page number in the source document")
    type: str | None = Field(
        default=None, description="Clinical guideline type (e.g. diabetes)"
    )


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[Source]


class IterationInfo(BaseModel):
    iteration: int
    query: str
    hybrid_results: int
    reranked_results: int
    relevance_score: float


class DebugResponse(BaseModel):
    """Full retrieval process for inspection - concise metadata only."""

    session_id: str
    original_query: str
    iterations: list[IterationInfo]
    final_answer: str
    sources: list[Source]
