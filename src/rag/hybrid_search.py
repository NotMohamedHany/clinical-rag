"""Hybrid search: dense + sparse results merged with Reciprocal Rank Fusion."""

from src import config
from src.rag.bm25_search import get_bm25_search
from src.rag.state import RetrievedChunk
from src.rag.vector_search import VectorSearch


def reciprocal_rank_fusion(
    vector_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
    k: int = 60,
) -> list[RetrievedChunk]:
    """Merge two ranked lists with Reciprocal Rank Fusion.

    Each document gets score = sum(1 / (k + rank + 1)) over the lists it
    appears in. Duplicate chunks (present in both lists) are merged into a
    single entry with the combined score. The result is sorted best-first.

    `k` is the RRF smoothing constant (default 60).
    """
    scores: dict[str, float] = {}
    chunks_by_id: dict[str, RetrievedChunk] = {}

    for ranked_list in (vector_results, bm25_results):
        for rank, chunk in enumerate(ranked_list):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank + 1)
            chunks_by_id[chunk.chunk_id] = chunk

    return sorted(chunks_by_id.values(), key=lambda c: scores[c.chunk_id], reverse=True)


class HybridSearch:
    """Combines dense (Chroma) and sparse (BM25) retrieval via RRF."""

    def __init__(self, vector_search: VectorSearch | None = None) -> None:
        self._vector = vector_search or VectorSearch()
        # Shared process-wide BM25 index (built once, reused by all searches).
        self._bm25 = get_bm25_search()

    def search(self, query: str) -> list[RetrievedChunk]:
        """Return fused candidates (roughly 10-20) ordered best-first."""
        vector_results = self._vector.search(query, top_k=config.VECTOR_K)
        bm25_results = self._bm25.search(query, top_k=config.BM25_K)
        return reciprocal_rank_fusion(vector_results, bm25_results, k=config.RRF_K)
