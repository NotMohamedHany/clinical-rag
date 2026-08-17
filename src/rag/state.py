"""Shared types for the RAG agent graph and the retrieval modules."""

from typing import NamedTuple, TypedDict


class RetrievedChunk(NamedTuple):
    """One retrieved chunk. `distance` is only meaningful for vector search."""

    chunk_id: str
    content: str
    metadata: dict
    distance: float = 0.0


class RagState(TypedDict, total=False):
    """State carried through the LangGraph agent.

    Only the fields needed by nodes and for debugging are tracked; no
    chain-of-thought is ever stored or exposed.
    """

    session_id: str              # conversation identifier (for logging)
    original_query: str          # the user's question, unchanged
    current_query: str           # the (possibly rewritten) retrieval query
    messages: list[dict]         # conversation history (role/content pairs)
    iteration: int               # retrieval attempts so far
    search_history: list[dict]   # debug: query + relevance score per attempt
    candidates: list[RetrievedChunk]   # hybrid (vector + BM25) candidates
    top_chunks: list[RetrievedChunk]   # reranked final documents
    rerank_scores: list[float]         # scores assigned by the reranker
    relevance_ok: bool           # grade result vs RELEVANCE_THRESHOLD
    relevance_score: float       # grade score (0-1)
    relevance_reason: str        # grader's reason, used to guide the rewrite
    final_answer: str            # generated answer
    sources: list[dict]          # [{"source": ..., "page": ...}] from top chunks
