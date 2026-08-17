"""Query improvement agent: rewrite the user's question for retrieval."""

from src.rag import prompts
from src.rag.llm import call_llm, get_llm


class QueryRewriter:
    """Rewrites a question using conversation history, via Gemma on Ollama."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def rewrite(self, question: str, history: list[dict], feedback: str = "") -> str:
        """Return a search-friendly retrieval query.

        `history` is the recent conversation (role/content pairs).
        `feedback` (optional) is the previous relevance-grading reason.
        If the original question is already good, it is returned unchanged.
        """
        prompt = prompts.build_rewrite_prompt(question, history, feedback)
        response = call_llm(self._llm, prompt)

        rewritten = response.content.strip()
        if not rewritten:
            # The model must never make the query worse than the original.
            return question
        return rewritten
