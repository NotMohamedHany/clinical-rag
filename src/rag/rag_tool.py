"""The whole RAG pipeline as a single LangChain tool for supervisor agents.

The tool wraps run_chat (memory -> query rewrite -> hybrid search -> rerank
-> relevance grade -> generate) so an outer agent sees the entire clinical
RAG system as ONE tool node: it passes a question and receives the answer
with source citations.
"""

from langchain_core.tools import tool

from src.memory.conversation import ConversationMemory
from src.rag.graph import RagAgent, run_chat

# Process-wide singletons: the RAG agent (and its indexes/models) loads once,
# and conversation memory persists across calls within this process.
_agent: RagAgent | None = None
_memory = ConversationMemory()


def _get_agent() -> RagAgent:
    global _agent
    if _agent is None:
        _agent = RagAgent()
    return _agent


@tool
def clinical_guidelines(question: str, session_id: str = "supervisor") -> str:
    """Answer clinical questions using ONLY the guideline PDFs in data/ (e.g. diabetes, hypertension).

    Covers diagnosis, treatment, management, screening, urgent referral and
    dosing recommendations, cited by source file, guideline type and page.
    If the guidelines do not contain enough information, the answer says so
    explicitly. Use this tool for any medical/clinical question.
    """
    state = run_chat(_get_agent(), _memory, session_id, question)
    citations = "; ".join(
        f"{source['source']} ({source['type']}, page {source['page']})"
        for source in state["sources"]
    )
    return f"{state['final_answer']}\n\n[Retrieved sources: {citations}]"
