"""Central configuration for the clinical guidelines RAG project.

Values are read from environment variables (see .env.example) with safe
defaults. All paths are computed relative to the project root so the
scripts work from any working directory.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root if present.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# All guideline PDFs are discovered under DATA_DIR - each PDF is typed by
# its location: data/<type>/<file>.pdf or data/<type>_guideline.pdf
# (see src/ingestion/ingest.py).
DATA_DIR = PROJECT_ROOT / "data"

CHROMA_DIR = PROJECT_ROOT / "chroma_db"
BM25_DIR = PROJECT_ROOT / "bm25"
BM25_CORPUS_PATH = BM25_DIR / "bm25_corpus.pkl"

# CSV user registry (username, name, role, salt, password_hash) - seeded
# with demo accounts on first run, see src/api/auth.py.
USERS_CSV_PATH = Path(os.getenv("USERS_CSV_PATH", str(PROJECT_ROOT / "users.csv")))

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------

COLLECTION_NAME = "clinical_guidelines"

# ---------------------------------------------------------------------------
# Embeddings (dense retrieval) — kept separate from the LLM
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "BAAI/bge-m3"

# ---------------------------------------------------------------------------
# LLM (Ollama)
# ---------------------------------------------------------------------------

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ---------------------------------------------------------------------------
# Reranker (free, local)
# ---------------------------------------------------------------------------

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

VECTOR_K = 30       # candidates from dense (Chroma) search
BM25_K = 30         # candidates from sparse (BM25) search
RRF_K = 60          # reciprocal-rank-fusion constant
RERANK_TOP_N = 8    # final documents after reranking

# ---------------------------------------------------------------------------
# Self-improving retrieval
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 2           # maximum retrieval/refinement attempts
RELEVANCE_THRESHOLD = 0.70   # relevance grade needed to generate

# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS = 6        # most recent user/assistant exchanges used for rewriting

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "0"))  # 0 = never expire
