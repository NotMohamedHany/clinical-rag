"""Shared embedding model: factory plus process-wide lazy singleton.

The model is loaded once per process and reused by every caller, so
repeated searches never pay for re-loading it. The lock prevents
concurrent API requests from double-loading.
"""

import threading
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_cohere import CohereEmbeddings


from src import config

_embeddings: HuggingFaceEmbeddings | None = None
_load_lock = threading.Lock()


def build_embedding_model(cohere=os.getenv("COHERE",None)):
    """Create a fresh embedding model instance (used by ingestion)."""
    if cohere:  
        return CohereEmbeddings(
    model="jina-embeddings-v5-omni-small",
    cohere_api_key=os.getenv("COHERE_KEY"))
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)


def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the shared singleton, loading it on first use."""
    global _embeddings
    if _embeddings is None:
        with _load_lock:
            if _embeddings is None:
                _embeddings = build_embedding_model()
    return _embeddings
