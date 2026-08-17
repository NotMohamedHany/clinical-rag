"""Free, local reranking with BAAI/bge-reranker-v2-m3 (sentence-transformers).

The reranker model is ~2.2 GB and is downloaded from the Hugging Face Hub
on first use, then cached. It is loaded lazily as a process-wide singleton
so it is only loaded when actually needed.

Reranker scores are NOT vector similarity scores: they are cross-encoder
logits produced by a dedicated reranking model and are only comparable
within one query's candidate set.
"""

from sentence_transformers import CrossEncoder

from src import config
from src.rag.state import RetrievedChunk

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(config.RERANKER_MODEL)
    return _model


def rerank(
    query: str,
    candidates: list[RetrievedChunk],
    top_n: int = config.RERANK_TOP_N,
) -> tuple[list[RetrievedChunk], list[float]]:
    """Score candidates with the cross-encoder and keep the top_n.

    Returns (top_chunks, scores) where scores[i] is the raw reranker score
    of top_chunks[i] (higher = more relevant, same query only).
    """
    if not candidates:
        return [], []

    model = _get_model()
    pairs = [(query, chunk.content) for chunk in candidates]
    scores = model.predict(pairs, show_progress_bar=False).tolist()

    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    top = ranked[:top_n]
    return [chunk for chunk, _ in top], [score for _, score in top]
