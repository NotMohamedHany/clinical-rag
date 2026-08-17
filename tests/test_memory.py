"""Conversational memory test.

Exchange 1 asks about diagnostic criteria; exchange 2 ("What about HbA1c?")
must be resolved against the conversation context into something like
"What is the HbA1c diagnostic criterion for diabetes?" and then retrieve
the correct section (page 13).

Requires Ollama (the query rewriter and generator are LLM-based); skipped
when the Ollama server is unreachable.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.graph import RagAgent, run_chat  # noqa: E402
from src.rag.llm import is_ollama_available  # noqa: E402

pytestmark = pytest.mark.skipif(
    not is_ollama_available(), reason="Ollama is not running; memory test skipped"
)


@pytest.fixture(scope="module")
def agent():
    return RagAgent()


@pytest.fixture(scope="module")
def memory():
    from src.memory.conversation import ConversationMemory

    return ConversationMemory()


def test_conversation_memory_resolves_references(agent, memory):
    session_id = "mem-test-1"

    # Exchange 1: full pipeline run, answer is stored in memory.
    state1 = run_chat(agent, memory, session_id, "What are the diagnostic criteria for diabetes?")
    assert state1["final_answer"], "first exchange produced no answer"

    history = memory.get_history(session_id)
    assert len(history) == 2, "memory should hold the user + assistant exchange"
    assert history[0]["role"] == "user" and history[1]["role"] == "assistant"

    # Exchange 2: "What about HbA1c?" - must use the conversation context.
    state2 = run_chat(agent, memory, session_id, "What about HbA1c?")

    # The rewritten query must resolve the reference: mention HbA1c and the
    # diagnostic context. Exact wording is not required.
    rewritten = state2["search_history"][0]["query"].lower()
    assert "hba1c" in rewritten, f"rewritten query lost the HbA1c topic: {rewritten!r}"
    assert any(
        word in rewritten for word in ("diagnostic", "criteria", "criterion", "diagnosis")
    ), f"rewritten query lost the diagnostic context: {rewritten!r}"

    # The correct section (page 13, diagnostic criteria table) must be retrieved.
    pages = {chunk.metadata.get("page") for chunk in state2.get("top_chunks", [])}
    assert 13 in pages, f"diagnostic criteria section (page 13) not retrieved: {pages}"

    # And the memory now contains both exchanges.
    assert len(memory.get_history(session_id)) == 4
