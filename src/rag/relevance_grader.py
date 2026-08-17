"""Relevance grader: does the retrieved context suffice? (Gemma, structured output)."""

import json
import logging
import re

from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field, ValidationError

from src import config
from src.rag import prompts
from src.rag.llm import call_llm, get_llm

logger = logging.getLogger("clinical_rag.grader")


class RelevanceGrade(BaseModel):
    """Structured output of the relevance grader."""

    relevant: bool = Field(description="Whether the context is sufficient to answer")
    score: float = Field(ge=0.0, le=1.0, description="Confidence between 0 and 1")
    reason: str = Field(description="Brief explanation of the grade")


def _extract_grade_from_text(text: str) -> RelevanceGrade:
    """Parse a RelevanceGrade from free text, tolerating JSON detritus.

    Handles code fences, surrounding prose, missing fields (relevant is
    derived from the score when absent) and malformed scores.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in grader response")
    data = json.loads(match.group(0))
    data.setdefault("relevant", data.get("score", 0.0) >= config.RELEVANCE_THRESHOLD)
    return RelevanceGrade(**data)


class RelevanceGrader:
    """Grades retrieved chunks against the question using structured output."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def grade(self, question: str, chunks) -> RelevanceGrade:
        """Grade the retrieved chunks. Score is 0-1; relevant = score >= threshold."""
        prompt = prompts.build_grade_prompt(question, chunks)
        try:
            response = call_llm(self._llm.with_structured_output(RelevanceGrade), prompt)
            return response
        except (ValidationError, OutputParserException, json.JSONDecodeError) as exc:
            # Structured output came back malformed - fall back to manual JSON
            # extraction so a single bad response does not break the request.
            logger.warning("structured grade failed (%s); using JSON fallback", exc)
            response = call_llm(self._llm, prompt)
            return _extract_grade_from_text(response.content)

    @property
    def threshold(self) -> float:
        return config.RELEVANCE_THRESHOLD
