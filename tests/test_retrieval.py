"""Manual retrieval-quality inspection (no LLM).

For each of five clinical questions, run the hybrid search (vector + BM25
+ RRF) followed by the local reranker, and print the top chunks with their
page numbers and rerank scores, so retrieval quality can be eyeballed.

Run from the project root:

    python -m pytest tests/test_retrieval.py -s -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.rag.hybrid_search import HybridSearch  # noqa: E402
from src.rag.reranker import rerank  # noqa: E402

EVALUATION_QUESTIONS = [
    "What physical activity is recommended for people with type 2 diabetes?",
    "What dietary recommendations are given for people with type 2 diabetes?",
    "What are the recommendations for blood glucose control?",
    "What medications are recommended for treating type 2 diabetes?",
    "How should cardiovascular risk be managed in people with diabetes?",
]


@pytest.fixture(scope="module")
def hybrid():
    return HybridSearch()


@pytest.mark.parametrize("question", EVALUATION_QUESTIONS)
def test_manual_retrieval_inspection(hybrid, question):
    candidates = hybrid.search(question)
    top_chunks, scores = rerank(question, candidates, top_n=config.RERANK_TOP_N)

    print(f"\n{'#' * 70}")
    print(f"QUERY: {question}")
    print(f"{'#' * 70}\n")

    assert top_chunks, "retrieval returned no chunks - is the collection built?"

    for position, (chunk, score) in enumerate(zip(top_chunks, scores), start=1):
        print("=" * 50)
        print(f"RESULT {position}")
        print("=" * 50)
        print(f"\nRerank score (higher = more relevant, same query only):")
        print(f"{score:.4f}")
        print(f"\nSource:")
        print(chunk.metadata.get("source", "unknown"))
        print(f"\nPage:")
        print(chunk.metadata.get("page", "unknown"))
        print(f"\nContent:")
        print(chunk.content)
        print()

    # Basic sanity checks; the real evaluation is the printed output.
    assert len(top_chunks) <= config.RERANK_TOP_N
    for chunk in top_chunks:
        assert chunk.metadata.get("source"), "chunk is missing its source metadata"
        assert chunk.metadata.get("page"), "chunk is missing its page metadata"
