"""The RAG agent graph (LangGraph).

Workflow per request:

    original query
      -> rewrite_query (Gemma: resolve history, improve query)
      -> hybrid_search (vector + BM25 -> RRF -> BGE rerank -> top N)
      -> grade_relevance (Gemma: structured 0-1 score)
      -> relevant?  -> generate (Gemma: answer + citations)
      -> not relevant and iterations left? -> rewrite_query again

MAX_ITERATIONS bounds the loop: after the last attempt the best available
evidence is used, and the generator states insufficiency if needed.
"""

import logging
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from src import config
from src.rag.generator import Generator
from src.rag.hybrid_search import HybridSearch
from src.rag.query_rewriter import QueryRewriter
from src.rag.relevance_grader import RelevanceGrader
from src.rag.reranker import rerank
from src.rag.state import RagState

logger = logging.getLogger("clinical_rag.graph")


def _source_name(source: str) -> str:
    return Path(source).name


def _attempt_number(state: RagState) -> int:
    """1-based retrieval attempt number (logged with every node outcome)."""
    return state.get("iteration", 0) + 1


def _log_attempt(state: RagState, message: str, *args) -> None:
    """Log a node outcome with the shared session/attempt prefix.

    `message` uses %-style placeholders filled by `args`, e.g.
    _log_attempt(state, "hybrid_candidates=%d", len(candidates)).
    """
    logger.info(
        "session=%s iteration=%d " + message,
        state.get("session_id", "?"),
        _attempt_number(state),
        *args,
    )


def _build_sources(chunks) -> list[dict]:
    """Distinct {source, page, type} entries from the reranked chunks.

    Chunks from the same page are merged; the filename is used as source
    and the guideline `type` (e.g. "diabetes") is kept alongside.
    """
    sources: list[dict] = []
    seen: set[tuple] = set()
    for chunk in chunks:
        key = (chunk.metadata.get("source", ""), chunk.metadata.get("page"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "source": _source_name(chunk.metadata.get("source", "unknown")),
                "page": chunk.metadata.get("page"),
                "type": chunk.metadata.get("type"),
            }
        )
    return sources


def _initial_state(session_id: str, message: str, history: list[dict]) -> dict:
    """Full input state for one graph invocation."""
    return {
        "session_id": session_id,
        "original_query": message,
        "current_query": message,
        "messages": history,
        "iteration": 0,
        "search_history": [],
        "top_chunks": [],
        "relevance_ok": False,
        "relevance_score": 0.0,
        "relevance_reason": "",
        "insufficient_evidence": False,
        "final_answer": "",
        "sources": [],
    }


class RagAgent:
    """Wires the RAG components into one compiled LangGraph agent."""

    def __init__(self) -> None:
        self.rewriter = QueryRewriter()
        self.grader = RelevanceGrader()
        self.generator = Generator()
        self.hybrid_search = HybridSearch()

        builder = StateGraph(RagState)
        builder.add_node("rewrite_query", self._rewrite_query)
        builder.add_node("hybrid_search", self._hybrid_search)
        builder.add_node("grade_relevance", self._grade_relevance)
        builder.add_node("generate", self._generate)
        builder.add_edge(START, "rewrite_query")
        builder.add_edge("rewrite_query", "hybrid_search")
        builder.add_edge("hybrid_search", "grade_relevance")
        builder.add_conditional_edges(
            "grade_relevance",
            self._route,
            {"generate": "generate", "rewrite_query": "rewrite_query"},
        )
        builder.add_edge("generate", END)
        self.graph = builder.compile()

    # ------------------------------------------------------------------ nodes

    def _rewrite_query(self, state: RagState) -> dict:
        feedback = ""
        if state.get("search_history"):
            last = state["search_history"][-1]
            feedback = (
                f"score {last['relevance_score']:.2f}; {state.get('relevance_reason', '')}"
            )
        rewritten = self.rewriter.rewrite(
            state["original_query"],
            history=state.get("messages", []),
            feedback=feedback,
        )
        _log_attempt(
            state, "original=%r rewritten=%r", state["original_query"], rewritten
        )
        return {"current_query": rewritten}

    def _hybrid_search(self, state: RagState) -> dict:
        query = state["current_query"]
        candidates = self.hybrid_search.search(query)
        new_top_chunks, scores = rerank(query, candidates, top_n=config.RERANK_TOP_N)

        existing = list(state.get("top_chunks", []))
        seen_ids = {c.chunk_id for c in existing}
        combined = list(existing)
        for c in new_top_chunks:
            if c.chunk_id not in seen_ids:
                seen_ids.add(c.chunk_id)
                combined.append(c)

        _log_attempt(
            state,
            "hybrid_candidates=%d reranked=%d accumulated=%d top_scores=%s",
            len(candidates),
            len(new_top_chunks),
            len(combined),
            [round(s, 3) for s in scores[:3]],
        )
        return {
            "candidates": candidates,
            "top_chunks": combined,
            "rerank_scores": scores,
        }

    def _grade_relevance(self, state: RagState) -> dict:
        grade = self.grader.grade(state["original_query"], state["top_chunks"])
        iteration = _attempt_number(state)

        search_history = list(state.get("search_history", []))
        search_history.append(
            {
                "iteration": iteration,
                "query": state["current_query"],
                "relevance_score": grade.score,
            }
        )
        is_ok = grade.score >= config.RELEVANCE_THRESHOLD
        is_last_iteration = iteration >= config.MAX_ITERATIONS
        insufficient = not is_ok and is_last_iteration

        _log_attempt(
            state,
            "relevance_score=%.2f relevant=%s insufficient=%s",
            grade.score,
            grade.relevant,
            insufficient,
        )
        return {
            "iteration": iteration,
            "search_history": search_history,
            "relevance_ok": is_ok,
            "relevance_score": grade.score,
            "relevance_reason": grade.reason,
            "insufficient_evidence": insufficient,
        }

    def _generate(self, state: RagState) -> dict:
        insufficient = state.get("insufficient_evidence", False)
        answer = self.generator.generate(
            state["original_query"], state["top_chunks"], insufficient=insufficient
        )
        sources = _build_sources(state["top_chunks"]) if not insufficient else []
        _log_attempt(
            state,
            "generated answer (%d chars), %d sources (insufficient=%s)",
            len(answer),
            len(sources),
            insufficient,
        )
        return {"final_answer": answer, "sources": sources}

    # ------------------------------------------------------------- routing

    def _route(self, state: RagState) -> str:
        """Go to generation when relevance is good or iterations are exhausted."""
        if state.get("relevance_ok") or state.get("iteration", 0) >= config.MAX_ITERATIONS:
            return "generate"
        return "rewrite_query"


def run_chat(agent: RagAgent, memory, session_id: str, message: str) -> dict:
    """Run one full chat turn for a session, updating conversation memory.

    Returns the final graph state, including final_answer, sources and
    search_history (for /chat/debug).
    """
    history = memory.get_history(session_id)
    state = agent.graph.invoke(_initial_state(session_id, message, history))
    memory.add_exchange(session_id, message, state["final_answer"])
    return state
