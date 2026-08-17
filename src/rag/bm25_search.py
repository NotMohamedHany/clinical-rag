"""Sparse retrieval with BM25 (rank-bm25).

The chunk corpus is persisted to bm25/bm25_corpus.pkl by the ingestion
script. The BM25 index is built from that file ONCE per process and reused
by every search, so it is never rebuilt per request.
"""

import pickle
import re
import threading
from pathlib import Path

from rank_bm25 import BM25Okapi

from src import config
from src.rag.state import RetrievedChunk

# Process-wide singleton (same pattern as the embedding model and reranker).
_instance: "BM25Search | None" = None
_instance_lock = threading.Lock()


def get_bm25_search() -> "BM25Search":
    """Return the shared BM25 index, building it on first use."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = BM25Search()
    return _instance


def tokenize(text: str) -> list[str]:
    """Simple lowercase, non-alphanumeric-split tokenizer for BM25."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Search:
    """BM25Okapi over the persisted chunk corpus."""

    def __init__(self, corpus_path: Path = config.BM25_CORPUS_PATH) -> None:
        if not corpus_path.exists():
            raise FileNotFoundError(
                f"BM25 corpus not found at {corpus_path}. "
                "Run `python -m src.ingestion.ingest` first."
            )
        with open(corpus_path, "rb") as f:
            self._corpus = pickle.load(f)

        tokenized_docs = [tokenize(entry["text"]) for entry in self._corpus]
        self._bm25 = BM25Okapi(tokenized_docs)

    def search(self, query: str, top_k: int = config.BM25_K) -> list[RetrievedChunk]:
        """Return the top_k chunks by BM25 score (higher score = better)."""
        tokenized_query = tokenize(query)
        top_indices = self._bm25.get_top_n(tokenized_query, range(len(self._corpus)), n=top_k)
        return [
            RetrievedChunk(
                chunk_id=self._corpus[index]["id"],
                content=self._corpus[index]["text"],
                metadata=self._corpus[index]["metadata"],
            )
            for index in top_indices
        ]
