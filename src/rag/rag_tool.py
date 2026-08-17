"""The whole RAG pipeline as a tool for supervisor agents.

clinical_guidelines_tool(session_id) builds the RAG tool bound to one
conversation session: it wraps run_chat (memory -> query rewrite -> hybrid
search -> rerank -> relevance grade -> generate) so an outer agent sees the
entire clinical RAG system as ONE tool call. It returns JSON so the outer
agent and the API layer both get the answer, the source citations, and the
retrieval debug trace.
"""

import json

from langchain_core.tools import BaseTool, tool

from src.memory.conversation import ConversationMemory
from src.rag.graph import RagAgent, run_chat

# Process-wide singletons: the RAG agent (and its indexes/models) loads once,
# and conversation memory persists across calls within this process.
_agent: RagAgent | None = None
_memory = ConversationMemory()

CLINICAL_GUIDELINES_DESCRIPTION = """Answer clinical questions using ONLY the guideline PDFs in data/ \
(e.g. diabetes, osteoporosis). Covers diagnosis, treatment, management, screening, urgent referral \
and dosing recommendations, cited by source file, guideline type and page. If the guidelines do not \
contain enough information, the answer says so explicitly. Returns JSON with "answer", "sources" \
(list of {"source", "type", "page"}) and "retrieval" (per-attempt queries and relevance scores). \
Use this tool for any medical/clinical question."""


def _get_agent() -> RagAgent:
    global _agent
    if _agent is None:
        _agent = RagAgent()
    return _agent


def clinical_guidelines_tool(session_id: str) -> BaseTool:
    """Build the RAG tool bound to one conversation session."""

    def run(question: str) -> str:
        state = run_chat(_get_agent(), _memory, session_id, question)
        return json.dumps(
            {
                "answer": state["final_answer"],
                "sources": state["sources"],
                "retrieval": [
                    {
                        "iteration": entry["iteration"],
                        "query": entry["query"],
                        "hybrid_results": len(state.get("candidates", [])),
                        "reranked_results": len(state.get("top_chunks", [])),
                        "relevance_score": entry["relevance_score"],
                    }
                    for entry in state["search_history"]
                ],
            },
            ensure_ascii=False,
        )

    return tool("clinical_guidelines", run, description=CLINICAL_GUIDELINES_DESCRIPTION)
