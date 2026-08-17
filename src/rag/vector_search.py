"""Dense retrieval over the Chroma collection (all-MiniLM-L6-v2)."""

import chromadb

from src import config
from src.rag.embeddings import get_embeddings
from src.rag.state import RetrievedChunk


class VectorSearch:
    """Chroma-backed dense search over the shared embedding model."""

    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        self._collection = self._client.get_collection(name=config.COLLECTION_NAME)

    def search(self, query: str, top_k: int = config.VECTOR_K) -> list[RetrievedChunk]:
        """Return the top_k chunks nearest to the query.

        Chroma's default metric is L2 distance: a LOWER distance means a
        more similar chunk. Results are ordered best-first.
        """
        query_vector = get_embeddings().embed_query(query)
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                content=text,
                metadata=metadata,
                distance=distance,
            )
            for chunk_id, text, metadata, distance in zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
