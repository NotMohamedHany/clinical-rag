"""Final answer generation: answer strictly from the retrieved evidence."""

from src.rag import prompts
from src.rag.llm import call_llm, get_llm


class Generator:
    """Answers the question using only the supplied guideline chunks."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def generate(self, question: str, chunks) -> str:
        """Return the model's answer for the given evidence chunks."""
        if not chunks:
            return (
                "The provided clinical guideline does not contain sufficient "
                "information to answer this question."
            )
        prompt = prompts.build_generate_prompt(question, chunks)
        response = call_llm(self._llm, prompt)
        return response.content.strip()
