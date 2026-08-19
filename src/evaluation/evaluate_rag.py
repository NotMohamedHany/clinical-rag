"""Clinical RAG Evaluation Script.

Evaluates the Clinical RAG system against the ground truth dataset in
`src/evaluation/clinical_rag_test_set.json`.

Metrics calculated:
  - Concept Recall / Coverage Rate: Percentage of ground truth concepts present in generated answers.
  - Document Retrieval Hit Rate: Whether the ground truth source document is retrieved in top chunks.
  - Answer Semantic Similarity: Cosine similarity using the shared BGE-M3 embedding model.
  - Lexical Overlap (Token F1): Word-level token precision, recall, and F1 score.
  - RAG System Health: Relevance grader pass rate, average score, iteration count, insufficient evidence flags, and latency.
  - Category Breakdown: Performance sliced by question category (direct, safety, clinical_reasoning, etc.).

Usage:
  python -m src.evaluation.evaluate_rag
  python -m src.evaluation.evaluate_rag --limit 5
  python -m src.evaluation.evaluate_rag --category safety --verbose
  python -m src.evaluation.evaluate_rag --output custom_results.json
"""

import argparse
import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Any

from src import config
from src.rag.embeddings import get_embeddings
from src.rag.graph import RagAgent, _initial_state

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("clinical_rag.evaluate")

DEFAULT_TEST_SET = config.PROJECT_ROOT / "src" / "evaluation" / "clinical_rag_test_set.json"
DEFAULT_OUTPUT_FILE = config.PROJECT_ROOT / "src" / "evaluation" / "eval_results.json"


# ---------------------------------------------------------------------------
# METRIC HELPER FUNCTIONS
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Normalize text for concept and token matching."""
    text = text.lower()
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    # Replace punctuation except numbers/hyphens/percents/decimals
    text = re.sub(r"[^\w\s\.\-%/>=<]", " ", text)
    return " ".join(text.split())


def check_concept_match(concept: str, text: str) -> bool:
    """Check if a required concept is present in the text with flexible matching."""
    norm_concept = normalize_text(concept)
    norm_text = normalize_text(text)

    if norm_concept in norm_text:
        return True

    # Handle numeric and symbol variations (e.g., "7.0 mmol/l" vs "7 mmol/l" or ">=11.1" vs "11.1")
    # Remove leading operators like >=, <=
    clean_concept = re.sub(r"^[>=<\s]+", "", norm_concept)
    if clean_concept and clean_concept in norm_text:
        return True

    # Check word tokens subset matching for multi-word concepts
    concept_words = norm_concept.split()
    if len(concept_words) > 1 and all(w in norm_text for w in concept_words):
        return True

    return False


def calculate_concept_coverage(required_concepts: list[str], answer: str) -> dict[str, Any]:
    """Calculate concept recall for a question."""
    if not required_concepts:
        return {"score": 1.0, "matched": [], "missing": []}

    matched = []
    missing = []
    for concept in required_concepts:
        if check_concept_match(concept, answer):
            matched.append(concept)
        else:
            missing.append(concept)

    score = len(matched) / len(required_concepts)
    return {
        "score": score,
        "total": len(required_concepts),
        "matched_count": len(matched),
        "matched": matched,
        "missing": missing,
    }


def calculate_token_f1(expected: str, actual: str) -> dict[str, float]:
    """Calculate word token overlap Precision, Recall, and F1."""
    exp_tokens = set(normalize_text(expected).split())
    act_tokens = set(normalize_text(actual).split())

    if not exp_tokens or not act_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    overlap = len(exp_tokens & act_tokens)
    precision = overlap / len(act_tokens)
    recall = overlap / len(exp_tokens)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def check_source_hit(expected_source: str, retrieved_sources: list[dict], top_chunks: list[Any]) -> bool:
    """Check if the ground truth source document is present in the retrieved chunks/sources."""
    expected_stem = Path(expected_source).stem.lower()

    # Check sources list
    for s in retrieved_sources:
        src_name = str(s.get("source", "")).lower()
        if expected_stem in src_name or expected_source.lower() in src_name:
            return True

    # Check top_chunks metadata
    for chunk in top_chunks:
        meta = getattr(chunk, "metadata", {}) or {}
        src_val = str(meta.get("source", "") or meta.get("source_name", "")).lower()
        if expected_stem in src_val or expected_source.lower() in src_val:
            return True

    return False


# ---------------------------------------------------------------------------
# EVALUATOR CLASS
# ---------------------------------------------------------------------------


class ClinicalRAGEvaluator:
    """Evaluates the RAG system performance using clinical_rag_test_set.json."""

    def __init__(self, test_set_path: Path = DEFAULT_TEST_SET) -> None:
        self.test_set_path = test_set_path
        self.test_set = self._load_test_set()
        self.embeddings = get_embeddings()
        logger.info("Initializing RAG Agent for evaluation...")
        self.agent = RagAgent()

    def _load_test_set(self) -> dict[str, Any]:
        if not self.test_set_path.exists():
            raise FileNotFoundError(f"Test set file not found at: {self.test_set_path}")
        with open(self.test_set_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_item(self, item: dict[str, Any], item_idx: int, total_items: int, verbose: bool = False) -> dict[str, Any]:
        """Evaluate a single test question."""
        question_id = item.get("id", f"q_{item_idx}")
        question = item["question"]
        expected_answer = item["expected_answer"]
        required_concepts = item.get("required_concepts", [])
        expected_source = item.get("source", "")
        category = item.get("category", "uncategorized")

        print(f"[{item_idx}/{total_items}] Evaluating ({category}): {question[:65]}...")

        start_time = time.time()
        session_id = f"eval_{question_id}"
        input_state = _initial_state(session_id, question, history=[])
        
        # Invoke RAG agent
        graph_output = self.agent.graph.invoke(input_state)
        latency = round(time.time() - start_time, 3)

        generated_answer = graph_output.get("final_answer", "")
        retrieved_sources = graph_output.get("sources", [])
        top_chunks = graph_output.get("top_chunks", [])
        relevance_ok = graph_output.get("relevance_ok", False)
        relevance_score = graph_output.get("relevance_score", 0.0)
        insufficient_evidence = graph_output.get("insufficient_evidence", False)
        iteration = graph_output.get("iteration", 1)

        # 1. Concept Coverage
        concept_res = calculate_concept_coverage(required_concepts, generated_answer)

        # 2. Source Document Hit
        source_hit = check_source_hit(expected_source, retrieved_sources, top_chunks)

        # 3. Semantic Answer Similarity
        exp_vector = self.embeddings.embed_query(expected_answer)
        gen_vector = self.embeddings.embed_query(generated_answer)
        sem_sim = cosine_similarity(exp_vector, gen_vector)

        # 4. Lexical Overlap
        token_overlap = calculate_token_f1(expected_answer, generated_answer)

        item_result = {
            "id": question_id,
            "category": category,
            "question": question,
            "expected_answer": expected_answer,
            "generated_answer": generated_answer,
            "expected_source": expected_source,
            "retrieved_sources": [s.get("source") for s in retrieved_sources],
            "source_hit": source_hit,
            "concept_coverage": concept_res["score"],
            "matched_concepts": concept_res["matched"],
            "missing_concepts": concept_res["missing"],
            "semantic_similarity": round(sem_sim, 4),
            "token_precision": round(token_overlap["precision"], 4),
            "token_recall": round(token_overlap["recall"], 4),
            "token_f1": round(token_overlap["f1"], 4),
            "relevance_ok": relevance_ok,
            "relevance_score": round(relevance_score, 4),
            "insufficient_evidence": insufficient_evidence,
            "iterations": iteration,
            "latency_seconds": latency,
        }

        if verbose:
            print(f"  -> Concept Recall: {concept_res['score']*100:.1f}% ({len(concept_res['matched'])}/{len(required_concepts)})")
            print(f"  -> Source Hit: {source_hit} (Expected: {expected_source})")
            print(f"  -> Semantic Sim: {sem_sim:.4f} | Token F1: {token_overlap['f1']:.4f}")
            print(f"  -> Relevance Pass: {relevance_ok} (Score: {relevance_score:.2f}) | Latency: {latency}s")
            if concept_res["missing"]:
                print(f"  -> Missing Concepts: {concept_res['missing']}")
            print()

        return item_result

    def run_evaluation(
        self,
        limit: int | None = None,
        category_filter: str | None = None,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Run evaluation over the dataset."""
        questions = self.test_set.get("questions", [])

        if category_filter:
            questions = [q for q in questions if q.get("category", "").lower() == category_filter.lower()]
            print(f"Filtered dataset to category '{category_filter}': {len(questions)} questions.")

        if limit and limit > 0:
            questions = questions[:limit]
            print(f"Limiting evaluation to first {limit} questions.")

        total_questions = len(questions)
        if total_questions == 0:
            print("No questions found matching criteria.")
            return {}

        print(f"\n=======================================================")
        print(f" Starting Clinical RAG Evaluation ({total_questions} Questions)")
        print(f"=======================================================\n")

        results = []
        for idx, item in enumerate(questions, start=1):
            res = self.evaluate_item(item, idx, total_questions, verbose=verbose)
            results.append(res)

        summary = self._aggregate_results(results)

        report = {
            "metadata": {
                "dataset": self.test_set_path.name,
                "total_questions_evaluated": total_questions,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "summary": summary,
            "itemized_results": results,
        }

        return report

    def _aggregate_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate per-question metrics into overall summary statistics and category breakdowns."""
        n = len(results)
        if n == 0:
            return {}

        avg_concept_coverage = sum(r["concept_coverage"] for r in results) / n
        perfect_concept_questions = sum(1 for r in results if r["concept_coverage"] == 1.0)
        source_hit_rate = sum(1 for r in results if r["source_hit"]) / n
        avg_semantic_sim = sum(r["semantic_similarity"] for r in results) / n
        avg_token_f1 = sum(r["token_f1"] for r in results) / n
        relevance_pass_rate = sum(1 for r in results if r["relevance_ok"]) / n
        avg_relevance_score = sum(r["relevance_score"] for r in results) / n
        insufficient_rate = sum(1 for r in results if r["insufficient_evidence"]) / n
        avg_iterations = sum(r["iterations"] for r in results) / n
        avg_latency = sum(r["latency_seconds"] for r in results) / n

        # Category Breakdown
        categories: dict[str, list[dict[str, Any]]] = {}
        for r in results:
            cat = r["category"]
            categories.setdefault(cat, []).append(r)

        category_summary = {}
        for cat, items in categories.items():
            cn = len(items)
            category_summary[cat] = {
                "count": cn,
                "concept_coverage": round(sum(i["concept_coverage"] for i in items) / cn, 4),
                "source_hit_rate": round(sum(1 for i in items if i["source_hit"]) / cn, 4),
                "semantic_similarity": round(sum(i["semantic_similarity"] for i in items) / cn, 4),
                "token_f1": round(sum(i["token_f1"] for i in items) / cn, 4),
                "relevance_pass_rate": round(sum(1 for i in items if i["relevance_ok"]) / cn, 4),
            }

        return {
            "total_questions": n,
            "overall_metrics": {
                "concept_coverage": round(avg_concept_coverage, 4),
                "perfect_concept_coverage_rate": round(perfect_concept_questions / n, 4),
                "source_hit_rate": round(source_hit_rate, 4),
                "semantic_similarity": round(avg_semantic_sim, 4),
                "token_f1": round(avg_token_f1, 4),
                "relevance_pass_rate": round(relevance_pass_rate, 4),
                "avg_relevance_score": round(avg_relevance_score, 4),
                "insufficient_evidence_rate": round(insufficient_rate, 4),
                "avg_search_iterations": round(avg_iterations, 2),
                "avg_latency_seconds": round(avg_latency, 2),
            },
            "category_breakdown": category_summary,
        }

    def print_summary_table(self, report: dict[str, Any]) -> None:
        """Print clean ASCII summary report to terminal."""
        if not report or "summary" not in report:
            print("No report data to print.")
            return

        summary = report["summary"]
        overall = summary["overall_metrics"]
        categories = summary["category_breakdown"]

        print("\n" + "=" * 70)
        print("               CLINICAL RAG EVALUATION REPORT               ")
        print("=" * 70)
        print(f"Total Questions Evaluated : {report['metadata']['total_questions_evaluated']}")
        print(f"Evaluation Timestamp      : {report['metadata']['timestamp']}")
        print("-" * 70)
        print("OVERALL METRICS:")
        print(f"  • Concept Recall / Coverage     : {overall['concept_coverage']*100:.1f}%")
        print(f"  • 100% Concept Coverage Rate    : {overall['perfect_concept_coverage_rate']*100:.1f}%")
        print(f"  • Source Document Retrieval Hit : {overall['source_hit_rate']*100:.1f}%")
        print(f"  • Answer Semantic Similarity    : {overall['semantic_similarity']:.4f}")
        print(f"  • Word Token Overlap F1 Score   : {overall['token_f1']:.4f}")
        print(f"  • Relevance Grader Pass Rate    : {overall['relevance_pass_rate']*100:.1f}%")
        print(f"  • Average Relevance Score       : {overall['avg_relevance_score']:.4f}")
        print(f"  • Insufficient Evidence Rate    : {overall['insufficient_evidence_rate']*100:.1f}%")
        print(f"  • Average Search Iterations     : {overall['avg_search_iterations']:.2f}")
        print(f"  • Average Query Latency         : {overall['avg_latency_seconds']:.2f}s")
        print("-" * 70)
        print("CATEGORY BREAKDOWN:")
        header = f"{'Category':<24} | {'Count':<5} | {'Concept %':<9} | {'Source Hit':<10} | {'Sem Sim':<7} | {'Token F1':<8}"
        print(header)
        print("-" * len(header))

        for cat, stats in sorted(categories.items()):
            print(
                f"{cat:<24} | {stats['count']:<5} | "
                f"{stats['concept_coverage']*100:>8.1f}% | "
                f"{stats['source_hit_rate']*100:>9.1f}% | "
                f"{stats['semantic_similarity']:>7.4f} | "
                f"{stats['token_f1']:>8.4f}"
            )

        print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Clinical RAG system using test set data.")
    parser.add_argument(
        "--test-set",
        type=Path,
        default=DEFAULT_TEST_SET,
        help="Path to the test set JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Path to output evaluation results JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of test questions to evaluate (for fast runs).",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter evaluation to a specific question category.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed outputs for each question.",
    )

    args = parser.parse_args()

    evaluator = ClinicalRAGEvaluator(test_set_path=args.test_set)
    report = evaluator.run_evaluation(
        limit=args.limit,
        category_filter=args.category,
        verbose=args.verbose,
    )

    if report:
        evaluator.print_summary_table(report)

        # Save results JSON
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Evaluation report saved to: [eval_results.json](file://{output_path.resolve()})")


if __name__ == "__main__":
    main()
