"""Retrieval evaluation over the clinical test dataset.

Runs BOTH retrieval modes and reports Hit Rate@3 / Hit Rate@5 / Recall /
MRR@5:

    baseline = original query  -> hybrid search -> rerank
    agentic  = rewritten query -> hybrid search -> rerank   (needs Ollama)

Correctness is judged by matching expected strings in the retrieved chunk
text (normalized) - never by an LLM. The agentic mode is skipped when
Ollama is unavailable.

Run from the project root:

    python -m pytest tests/test_dataset.py -s -v
"""

import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.rag.hybrid_search import HybridSearch  # noqa: E402
from src.rag.llm import is_ollama_available  # noqa: E402
from src.rag.query_rewriter import QueryRewriter  # noqa: E402
from src.rag.reranker import rerank  # noqa: E402

# ---------------------------------------------------------------------------
# Test dataset: 8 clinical questions with expected evidence (match strings)
# ---------------------------------------------------------------------------


@dataclass
class QueryCase:
    """One evaluation question and the evidence its retrieval must surface."""

    name: str
    question: str
    match_strings: list[str]
    target_pages: list[int]


TEST_CASES = [
    QueryCase(
        name="Test 1",
        question=(
            "What are the diagnostic cut-off values for fasting plasma glucose, "
            "random plasma glucose, and HbA1c for diabetes diagnosis?"
        ),
        match_strings=["≥7.0 mmol/L", "≥11.1 mmol/L", "HbA1c 6.5%"],
        target_pages=[13],
    ),
    QueryCase(
        name="Test 2",
        question=(
            "What are the contraindications for prescribing metformin in type 2 "
            "diabetes patients?"
        ),
        match_strings=[
            "Metformin is contraindicated in:",
            "eGFR <30",
            "lactic acidosis",
        ],
        target_pages=[15],
    ),
    QueryCase(
        name="Test 3",
        question=(
            "How should severe hypoglycaemia be managed if the patient is "
            "unconscious or unable to swallow?"
        ),
        match_strings=[
            "Unconscious patients",
            "hypertonic glucose",
            "20-50 mL of 50% glucose",
        ],
        target_pages=[19],
    ),
    QueryCase(
        name="Test 4",
        question=(
            "What are the biochemical differences in plasma glucose and urine "
            "ketones between DKA and HHS measurable in primary care?"
        ),
        match_strings=[
            "Biochemical characteristics of DKA and HHS",
            "≥13.9 mmol/L",
            "≥33.3 mmol/L",
            "Urine ketones",
        ],
        target_pages=[19],
    ),
    QueryCase(
        name="Test 5",
        question=(
            "How is diabetic kidney disease diagnosed and what are the screening "
            "criteria?"
        ),
        match_strings=[
            "eGFR <60",
            "albuminuria",
            "two urine samples",
            "1 to 3 months apart",
        ],
        target_pages=[21, 22],
    ),
    QueryCase(
        name="Test 6",
        question=(
            "Under what specific blood pressure and clinical conditions should a "
            "patient with diabetes be urgently referred on the same day?"
        ),
        match_strings=[
            "Urgent (same day) referral",
            "blood pressure >200/>110 mmHg",
            "blood pressure >180/>110 mmHg with headache",
        ],
        target_pages=[26],
    ),
    QueryCase(
        name="Test 7",
        question=(
            "How is the light touch test (Ipswich Touch Test) performed to screen "
            "for loss of protective sensation in the foot?"
        ),
        match_strings=[
            "Ipswich Touch Test",
            "first, third, and fifth toes",
            "1-2 seconds",
            "≥2 sites",
        ],
        target_pages=[33],
    ),
    QueryCase(
        name="Test 8",
        question=(
            "What is the starting dosage and titration protocol for "
            "intermediate-acting insulin (NPH) in type 2 diabetes?"
        ),
        match_strings=[
            "START with 10 units",
            "NPH",
            "1-2 units",
            "3-day intervals",
            "FBG = 4-7 mmol/L",
        ],
        target_pages=[29],
    ),
]

# ---------------------------------------------------------------------------
# Normalization (does not modify the retrieved text, only the comparison)
# ---------------------------------------------------------------------------

_FULLWIDTH_RE = re.compile(r"[！-～]")


def normalize_text(text: str) -> str:
    """Normalize for substring matching.

    - Unicode NFKC (fold superscripts: m² -> m2, fullwidth chars)
    - lowercase
    - map >= / <= symbols to ASCII forms
    - remove all whitespace and slashes (so "mL/minute" == "ml/min")
    """
    text = unicodedata.normalize("NFKC", text)
    text = _FULLWIDTH_RE.sub(lambda m: chr(ord(m.group(0)) - 0xFEE0), text)
    text = text.lower()
    text = text.replace("≥", ">=").replace("≤", "<=")
    text = text.replace("–", "-").replace("—", "-")  # unicode dashes -> hyphen
    text = re.sub(r"\bto\b", "-", text)               # "1 to 3" -> "1-3"
    # PDF table extraction artifacts: footnote markers ("HbA1c***") and
    # parenthetical abbreviations ("(eGFR) <30") should not break matching.
    text = text.replace("*", "").replace("(", "").replace(")", "")
    text = re.sub(r"[\s/]", "", text)                 # "mL/minute" == "ml/min"
    return text


def matched_strings(chunk_text: str, match_strings: list[str]) -> list[str]:
    """Which expected match strings appear (normalized) in the chunk."""
    normalized = normalize_text(chunk_text)
    return [s for s in match_strings if normalize_text(s) in normalized]


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

# One shared search instance: the embedding model, BM25 index and Chroma
# client are loaded once and reused for every query in the evaluation.
_HYBRID = HybridSearch()


def evaluate_query(question: str, match_strings: list[str], top_k: int) -> dict:
    """Run hybrid search + reranker for one question, return evaluation info.

    Order of the top_k results follows the reranker (as in the real
    pipeline). Retrieval is judged against the case's own match strings.
    """
    candidates = _HYBRID.search(question)
    top_chunks, _ = rerank(question, candidates, top_n=top_k)

    hits = []        # ranks (1-based) of chunks containing >=1 match string
    matched = set()  # match strings found across the top_k chunks
    for rank, chunk in enumerate(top_chunks, start=1):
        found = matched_strings(chunk.content, match_strings)
        if found:
            hits.append(rank)
            matched.update(found)

    return {
        "chunks": top_chunks,
        "hit_ranks": hits,
        "matched_strings": sorted(matched),
    }


@dataclass
class QueryResult:
    """Per-question evaluation outcome, used for the printed report."""

    name: str
    hit: bool
    first_rank: int | None
    recall: float
    matched: list[str]


def compute_metrics(queries: list[str] | None = None, top_k: int = 5) -> dict:
    """Hit Rate@K, Recall@K (string-level) and MRR@K over all test cases.

    `queries` pairs with TEST_CASES by index: pass rewritten queries to
    evaluate the agentic mode, or None to use the original questions.
    """
    queries = queries or [case.question for case in TEST_CASES]
    hits = 0
    mrr_sum = 0.0
    recall_sum = 0.0
    per_query: list[QueryResult] = []

    for case, question in zip(TEST_CASES, queries):
        info = evaluate_query(question, case.match_strings, top_k)
        hit = bool(info["hit_ranks"])
        first_rank = info["hit_ranks"][0] if info["hit_ranks"] else None
        recall = len(info["matched_strings"]) / len(case.match_strings)

        hits += int(hit)
        mrr_sum += (1.0 / first_rank) if first_rank else 0.0
        recall_sum += recall
        per_query.append(
            QueryResult(
                name=case.name,
                hit=hit,
                first_rank=first_rank,
                recall=recall,
                matched=info["matched_strings"],
            )
        )

    n = len(TEST_CASES)
    hit_rate_3 = sum(1 for row in per_query if row.first_rank and row.first_rank <= 3) / n
    return {
        "hit_rate_3": hit_rate_3,
        "hit_rate": hits / n,          # Hit Rate@K (K = top_k)
        "mrr": mrr_sum / n,            # MRR@K
        "recall": recall_sum / n,
        "per_query": per_query,
    }


# ---------------------------------------------------------------------------
# The two evaluation modes
# ---------------------------------------------------------------------------


def rewritten_questions() -> list[str]:
    """Rewrite each dataset question once (agentic mode). Requires Ollama."""
    rewriter = QueryRewriter()
    return [rewriter.rewrite(case.question, history=[]) for case in TEST_CASES]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_SANITY_HIT_RATE = 0.5  # at least half the questions must retrieve evidence


def _print_evaluation(title: str, metrics: dict) -> None:
    print(f"\n{'=' * 50}")
    print(f"Clinical RAG Retrieval Evaluation - {title}")
    print(f"{'=' * 50}")
    for row in metrics["per_query"]:
        status3 = "PASS" if row.first_rank and row.first_rank <= 3 else "FAIL"
        status5 = "PASS" if row.hit else "FAIL"
        print(f"\n{row.name}:")
        print(f"  Hit@3: {status3} (first hit at rank {row.first_rank})")
        print(f"  Hit@5: {status5}")
        print(f"  Recall: {row.recall:.2f}")
        print(f"  Matched: {row.matched}")
    print("\n" + "-" * 50)
    print(f"Hit Rate@3: {metrics['hit_rate_3']:.3f}")
    print(f"Hit Rate@5: {metrics['hit_rate']:.3f}")
    print(f"Recall@5:  {metrics['recall']:.3f}")
    print(f"MRR@5:      {metrics['mrr']:.3f}")
    print("-" * 50)


def _run_mode(title: str, queries: list[str] | None) -> dict:
    """Run one evaluation mode: compute metrics, print the report, assert sanity."""
    metrics = compute_metrics(queries=queries, top_k=config.RERANK_TOP_N)
    _print_evaluation(title, metrics)
    assert metrics["hit_rate"] >= _SANITY_HIT_RATE, (
        f"{title} hit rate too low: {metrics['hit_rate']:.2f}"
    )
    return metrics


def test_baseline_evaluation():
    """Baseline: original queries through hybrid search + rerank (no LLM)."""
    _run_mode("Baseline (original queries)", queries=None)


@pytest.mark.skipif(
    not is_ollama_available(), reason="Ollama is not running; agentic mode skipped"
)
def test_agentic_evaluation():
    """Agentic: query-rewritten queries through the same pipeline (needs Ollama).

    Each dataset question is rewritten once by the query-improvement agent,
    then evaluated with the same hybrid search + rerank pipeline and the
    same match strings, so the numbers are directly comparable.
    """
    _run_mode("Agentic (rewritten queries)", queries=rewritten_questions())
