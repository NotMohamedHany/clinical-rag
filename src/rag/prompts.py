"""Prompt templates for the RAG agent. Kept separate from the graph logic."""


def _assemble(system: str, user: str) -> str:
    """Join the system and user halves of a prompt into one string."""
    return system + "\n\n" + user


# ---------------------------------------------------------------------------
# Query rewriting
# ---------------------------------------------------------------------------

REWRITE_SYSTEM_PROMPT = """\
You are a query-improvement agent for a clinical guideline retrieval system.

Your ONLY job is to rewrite the user's question into a better search query
for retrieving relevant sections from the supplied clinical guidelines.

Rules:
- Preserve the user's intent exactly.
- Resolve references such as "this", "that", "it", or "the medication
  mentioned earlier" using the conversation history.
- Add useful clinical terminology that would appear in the guideline.
- Remove ambiguity.
- Produce a search-friendly query (concise, keyword-rich).
- NEVER answer the question. NEVER add commentary or explanation.
- If the original question is already a good retrieval query, return it
  unchanged.

Output ONLY the rewritten query, with no quotes, prefixes, or punctuation
beyond the query itself."""

REWRITE_USER_PROMPT = """\
Conversation history:
{history}

Current question:
{question}

Improved retrieval query:"""


def build_rewrite_prompt(question: str, history: list[dict], feedback: str = "") -> str:
    """Assemble the rewrite prompt.

    `feedback` (optional) describes why the previous retrieval attempt was
    graded insufficient, so the second attempt can be more targeted.
    """
    if not history:
        history_text = "(no prior conversation)"
    else:
        history_text = "\n".join(
            f"{entry['role']}: {entry['content']}" for entry in history
        )

    feedback_text = (
        f"\n\nPrevious retrieval was graded insufficient ({feedback}). "
        "Improve the query so the next search finds better evidence.\n"
        if feedback
        else ""
    )

    user_prompt = REWRITE_USER_PROMPT.format(history=history_text, question=question)
    return _assemble(REWRITE_SYSTEM_PROMPT + feedback_text, user_prompt)


# ---------------------------------------------------------------------------
# Relevance grading
# ---------------------------------------------------------------------------

GRADE_SYSTEM_PROMPT = """\
You are a relevance grader for a clinical guideline retrieval system.

You receive a question and a set of retrieved guideline chunks. Judge
whether the retrieved chunks contain enough relevant evidence to answer
the question.

Respond with ONLY valid JSON matching exactly this schema - every field
is required:

{"relevant": true, "score": 0.91, "reason": "..."}

- "relevant": whether the chunks contain enough evidence to answer
- "score": confidence between 0 and 1 (1 = fully sufficient)
- "reason": one short sentence on what is present or missing

If the chunks contain partial or unrelated evidence, set "relevant" to
false, score below 0.70, and explain in the reason what is missing."""

GRADE_USER_PROMPT = """\
Question:
{question}

Retrieved chunks:
{chunks}

Relevance grade (JSON):"""


def build_grade_prompt(question: str, chunks) -> str:
    """Assemble the grading prompt from the top (reranked) chunks."""
    formatted = "\n\n".join(
        f"[page {chunk.metadata.get('page', '?')}]\n{chunk.content[:1200]}"
        for chunk in chunks
    )
    user_prompt = GRADE_USER_PROMPT.format(question=question, chunks=formatted)
    return _assemble(GRADE_SYSTEM_PROMPT, user_prompt)


# ---------------------------------------------------------------------------
# Final answer generation
# ---------------------------------------------------------------------------

GENERATE_SYSTEM_PROMPT = """\
You are a clinical guideline question-answering assistant.

Use ONLY the supplied retrieved guideline context.

Do not use outside medical knowledge to fill gaps.

If the retrieved evidence is insufficient, explicitly say that the provided
guideline does not contain enough information.

Do not diagnose patients.

Do not prescribe treatment.

Do not invent facts.

Cite the retrieved source and page.

If the provided evidence is insufficient to answer, respond with exactly:

The provided clinical guideline does not contain sufficient information to answer this question."""

GENERATE_USER_PROMPT = """\
User question:
{question}

Retrieved evidence:
{evidence}

Answer using the format:

Answer:
...

Sources:
- <guideline source file>, page X
- <guideline source file>, page Y"""


def build_generate_prompt(question: str, chunks) -> str:
    """Assemble the generation prompt from the final reranked chunks."""
    evidence = "\n\n".join(
        f"Source: {chunk.metadata.get('source', 'unknown')} "
        f"(page {chunk.metadata.get('page', '?')})\n{chunk.content}"
        for chunk in chunks
    )
    user_prompt = GENERATE_USER_PROMPT.format(question=question, evidence=evidence)
    return _assemble(GENERATE_SYSTEM_PROMPT, user_prompt)
