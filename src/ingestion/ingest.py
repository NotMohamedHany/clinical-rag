"""
Clinical guideline ingestion:

PDFs -> pages -> chunks -> ChromaDB + BM25 corpus

Run from the project root:

    python -m src.ingestion.ingest

Directory conventions:

    data/<type>/<file>.pdf
        -> type = directory name

    data/<type>_guideline.pdf
        -> type = filename stem without "_guideline"

Example:

    data/diabetes/type-1-diabetes.pdf
        -> type = "diabetes"

    data/hypertension_guideline.pdf
        -> type = "hypertension"

Important properties:

- Stable chunk IDs
- Idempotent ingestion
- Detects changed chunks and re-embeds them
- Removes stale chunks from Chroma when a PDF changes
- BM25 corpus always rebuilt from the current source documents
- Preserves existing metadata fields:
    source
    page
    type
- Adds useful clinical-RAG metadata
"""

import hashlib
import pickle
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import pymupdf
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import config
from src.rag.embeddings import build_embedding_model


SAMPLES_TO_PRINT = 3

# Number of documents embedded in one batch.
# Prevents large guideline collections from consuming too much memory.
EMBED_BATCH_SIZE = 64

_GUIDELINE_SUFFIXES = (
    "_guideline",
    "-guideline",
)


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Guideline:
    """One guideline PDF and its resolved clinical type."""

    path: Path
    type: str


# ---------------------------------------------------------------------------
# GUIDELINE DISCOVERY
# ---------------------------------------------------------------------------


def guideline_type(path: Path, data_dir: Path) -> str:
    """
    Resolve the clinical type of a guideline PDF.

    Examples:

        data/diabetes/type-1.pdf
        -> diabetes

        data/hypertension_guideline.pdf
        -> hypertension
    """

    try:
        relative = path.resolve().relative_to(data_dir.resolve())
    except ValueError:
        relative = Path(path.name)

    # data/<type>/<file>.pdf
    if len(relative.parts) > 1:
        return relative.parts[0]

    # data/<type>_guideline.pdf
    stem = path.stem

    for suffix in _GUIDELINE_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]

    return stem


def discover_guidelines(
    data_dir: Path = config.DATA_DIR,
) -> list[Guideline]:
    """Discover all PDF guidelines under data_dir."""

    if not data_dir.exists():
        return []

    return [
        Guideline(
            path=path,
            type=guideline_type(path, data_dir),
        )
        for path in sorted(data_dir.rglob("*.pdf"))
    ]


# ---------------------------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """
    Light text normalization.

    Intentionally conservative.

    We do NOT aggressively remove whitespace because formatting can
    sometimes carry useful information in clinical guidelines.
    """

    text = text.replace("\x00", " ")

    # Normalize different newline styles.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive spaces while preserving line breaks.
    lines = []

    for line in text.split("\n"):
        cleaned = " ".join(line.split())

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# CONTENT HASHING
# ---------------------------------------------------------------------------


def content_hash(text: str) -> str:
    """
    Stable SHA-256 hash for detecting changed chunks.
    """

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# PDF LOADING
# ---------------------------------------------------------------------------


def load_pdf(
    path: Path,
    guideline_type_name: str,
) -> list[Document]:
    """
    Extract text from each PDF page.

    Each page becomes a LangChain Document.

    Existing metadata is preserved:
        source
        page
        type

    Additional metadata:
        source_name
        guideline
        page_text_length
    """

    documents: list[Document] = []

    with pymupdf.open(path) as pdf:

        total_pages = len(pdf)

        for page_number, page in enumerate(pdf, start=1):

            # Use block extraction to preserve reading order, tabular layouts,
            # and distinct section headers.
            blocks = page.get_text("blocks")
            text_blocks = []
            for b in blocks:
                if len(b) >= 5 and b[4]:
                    block_text = b[4].strip()
                    if block_text:
                        text_blocks.append(block_text)
            raw_text = "\n\n".join(text_blocks) if text_blocks else page.get_text("text", sort=True)
            text = normalize_text(raw_text)

            if not text:
                continue

            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        # KEEP EXISTING KEYS
                        "source": str(path),
                        "page": page_number,
                        "type": guideline_type_name,

                        # NEW METADATA
                        "source_name": path.name,
                        "guideline": guideline_type_name,
                        "page_text_length": len(text),
                        "total_pages": total_pages,
                    },
                )
            )

    return documents


# ---------------------------------------------------------------------------
# CHUNKING
# ---------------------------------------------------------------------------


def split_documents(
    documents: list[Document],
) -> list[Document]:
    """
    Split page-level documents into overlapping chunks.

    Keeps chunks page-aware so citations can still point to the source page.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,

        # Explicit separators are useful for clinical guidelines.
        #
        # We prefer:
        #   paragraph
        #   line
        #   sentence-ish boundaries
        #   whitespace
        #
        # before splitting in the middle of text.
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
            "",
        ],
    )

    chunks = splitter.split_documents(documents)

    # Add chunk-level metadata.
    #
    # We do this AFTER splitting because chunk_index is only meaningful
    # within the complete guideline.
    chunk_counts: dict[str, int] = {}

    enriched_chunks: list[Document] = []

    for chunk in chunks:

        source = chunk.metadata["source"]

        current_index = chunk_counts.get(source, 0)
        chunk_counts[source] = current_index + 1

        text = chunk.page_content.strip()

        chunk.metadata.update(
            {
                "chunk_index": current_index,
                "chunk_length": len(text),
                "content_hash": content_hash(text),
            }
        )

        enriched_chunks.append(chunk)

    return enriched_chunks


# ---------------------------------------------------------------------------
# STABLE IDS
# ---------------------------------------------------------------------------


def chunk_ids(
    chunks: list[Document],
    pdf_path: Path,
) -> list[str]:
    """
    Generate stable chunk IDs.

    Existing format is preserved:

        <pdf-name>-p<page>-c<position>

    This prevents breaking existing references.
    """

    stem = pdf_path.stem

    return [
        f"{stem}-p{chunk.metadata['page']:03d}-c{index:03d}"
        for index, chunk in enumerate(chunks)
    ]


# ---------------------------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------------------------


def print_chunk_statistics(
    chunks: list[Document],
) -> None:
    """Print useful chunk statistics."""

    if not chunks:
        print("Number of pages: 0")
        print("Number of chunks: 0")
        print("No chunks generated.")
        return

    lengths = [
        len(chunk.page_content)
        for chunk in chunks
    ]

    pages = {
        chunk.metadata["page"]
        for chunk in chunks
    }

    print(f"Number of pages represented: {len(pages)}")
    print(f"Number of chunks: {len(chunks)}")
    print(
        f"Average chunk length: "
        f"{statistics.mean(lengths):.0f} characters"
    )
    print(
        f"Median chunk length: "
        f"{statistics.median(lengths):.0f} characters"
    )
    print(
        f"Minimum chunk length: "
        f"{min(lengths)} characters"
    )
    print(
        f"Maximum chunk length: "
        f"{max(lengths)} characters"
    )


# ---------------------------------------------------------------------------
# SAMPLE CHUNKS
# ---------------------------------------------------------------------------


def print_sample_chunks(
    chunks: list[Document],
    count: int = SAMPLES_TO_PRINT,
) -> None:
    """Print sample chunks for manual quality inspection."""

    for chunk in chunks[:count]:

        print("\n" + "-" * 70)

        print(
            f"Sample chunk | "
            f"page={chunk.metadata['page']} | "
            f"chunk={chunk.metadata.get('chunk_index')} | "
            f"length={chunk.metadata.get('chunk_length')}"
        )

        print("-" * 70)

        preview = chunk.page_content[:500]

        print(
            preview
            + ("..." if len(chunk.page_content) > 500 else "")
        )


# ---------------------------------------------------------------------------
# CHROMA
# ---------------------------------------------------------------------------


def get_or_create_collection() -> chromadb.Collection:
    """Open or create the persistent Chroma collection."""

    client = chromadb.PersistentClient(
        path=str(config.CHROMA_DIR)
    )

    return client.get_or_create_collection(
        name=config.COLLECTION_NAME
    )


def embed_texts_in_batches(
    embeddings,
    texts: list[str],
    batch_size: int = EMBED_BATCH_SIZE,
) -> list[list[float]]:
    """
    Generate embeddings in batches.

    This avoids embedding a huge guideline collection in one call.
    """

    all_vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):

        batch = texts[
            start:start + batch_size
        ]

        print(
            f"Embedding batch "
            f"{start + 1}-{start + len(batch)} "
            f"of {len(texts)}..."
        )

        vectors = embeddings.embed_documents(batch)

        all_vectors.extend(vectors)

    return all_vectors


def store_chunks_in_chroma(
    collection: chromadb.Collection,
    chunks: list[Document],
    embeddings,
    ids: list[str],
) -> None:
    """
    Synchronize chunks with Chroma.

    Handles:

    1. New chunks
    2. Existing unchanged chunks
    3. Existing changed chunks
    4. Stale chunks removed from a guideline

    This makes Chroma match the current PDF.
    """

    if not chunks:
        return

    # ------------------------------------------------------------------
    # Retrieve current records
    # ------------------------------------------------------------------

    existing = collection.get(
        ids=ids,
        include=[
            "metadatas",
            "documents",
        ],
    )

    existing_ids = set(
        existing.get("ids", [])
    )

    existing_metadata_by_id: dict[str, dict[str, Any]] = {
        record_id: metadata or {}
        for record_id, metadata in zip(
            existing.get("ids", []),
            existing.get("metadatas", []),
        )
    }

    existing_documents_by_id: dict[str, str] = {
        record_id: document or ""
        for record_id, document in zip(
            existing.get("ids", []),
            existing.get("documents", []),
        )
    }

    # ------------------------------------------------------------------
    # Determine new / changed chunks
    # ------------------------------------------------------------------

    to_add: list[tuple[Document, str]] = []
    to_update: list[tuple[Document, str]] = []

    for chunk, chunk_id in zip(chunks, ids):

        if chunk_id not in existing_ids:

            to_add.append(
                (chunk, chunk_id)
            )
            continue

        new_hash = chunk.metadata.get(
            "content_hash"
        )

        old_hash = existing_metadata_by_id.get(
            chunk_id,
            {},
        ).get("content_hash")

        # Old ingestion versions don't have content_hash.
        # Compare the actual document as a safe fallback.
        if old_hash is None:

            old_document = (
                existing_documents_by_id.get(
                    chunk_id,
                    "",
                )
            )

            if old_document != chunk.page_content:

                to_update.append(
                    (chunk, chunk_id)
                )

        elif old_hash != new_hash:

            to_update.append(
                (chunk, chunk_id)
            )

        # If hash is identical, nothing needs to be changed.

    print(f"\nChroma synchronization:")
    print(f"  New chunks:     {len(to_add)}")
    print(f"  Changed chunks: {len(to_update)}")
    print(
        f"  Unchanged:      "
        f"{len(chunks) - len(to_add) - len(to_update)}"
    )

    # ------------------------------------------------------------------
    # ADD NEW CHUNKS
    # ------------------------------------------------------------------

    if to_add:

        print(
            f"\nGenerating embeddings for "
            f"{len(to_add)} new chunks..."
        )

        vectors = embed_texts_in_batches(
            embeddings,
            [
                chunk.page_content
                for chunk, _ in to_add
            ],
        )

        collection.add(
            ids=[
                chunk_id
                for _, chunk_id in to_add
            ],
            documents=[
                chunk.page_content
                for chunk, _ in to_add
            ],
            metadatas=[
                chunk.metadata
                for chunk, _ in to_add
            ],
            embeddings=vectors,
        )

        print(
            f"Added {len(to_add)} new chunks."
        )

    # ------------------------------------------------------------------
    # UPDATE CHANGED CHUNKS
    # ------------------------------------------------------------------

    if to_update:

        print(
            f"\nRe-embedding "
            f"{len(to_update)} changed chunks..."
        )

        vectors = embed_texts_in_batches(
            embeddings,
            [
                chunk.page_content
                for chunk, _ in to_update
            ],
        )

        collection.update(
            ids=[
                chunk_id
                for _, chunk_id in to_update
            ],
            documents=[
                chunk.page_content
                for chunk, _ in to_update
            ],
            metadatas=[
                chunk.metadata
                for chunk, _ in to_update
            ],
            embeddings=vectors,
        )

        print(
            f"Updated {len(to_update)} changed chunks."
        )

    # ------------------------------------------------------------------
    # BACKWARD COMPATIBILITY
    # ------------------------------------------------------------------

    # Old chunks may exist without the new metadata.
    # If the content hasn't changed, update metadata without
    # unnecessarily regenerating embeddings.
    metadata_only_updates: list[tuple[Document, str]] = []

    for chunk, chunk_id in zip(chunks, ids):

        if chunk_id not in existing_ids:
            continue

        if any(
            chunk_id == updated_id
            for _, updated_id in to_update
        ):
            continue

        old_metadata = existing_metadata_by_id.get(
            chunk_id,
            {},
        )

        required_keys = [
            "type",
            "source_name",
            "guideline",
            "chunk_index",
            "chunk_length",
            "content_hash",
        ]

        missing_keys = [
            key
            for key in required_keys
            if key not in old_metadata
        ]

        if missing_keys:

            metadata_only_updates.append(
                (chunk, chunk_id)
            )

    if metadata_only_updates:

        collection.update(
            ids=[
                chunk_id
                for _, chunk_id in metadata_only_updates
            ],
            metadatas=[
                chunk.metadata
                for chunk, _ in metadata_only_updates
            ],
        )

        print(
            f"Updated metadata on "
            f"{len(metadata_only_updates)} "
            f"existing chunks."
        )


def remove_stale_chunks_for_guideline(
    collection: chromadb.Collection,
    source_path: Path,
    current_ids: set[str],
) -> None:
    """
    Remove Chroma chunks that belonged to an older version of a PDF
    but are no longer present.

    Example:

        Old PDF -> 100 chunks
        New PDF -> 92 chunks

    The 8 obsolete chunks are deleted.
    """

    source = str(source_path)

    existing = collection.get(
        where={
            "source": source
        },
        include=[
            "metadatas"
        ],
    )

    old_ids = set(
        existing.get("ids", [])
    )

    stale_ids = old_ids - current_ids

    if not stale_ids:
        return

    collection.delete(
        ids=list(stale_ids)
    )

    print(
        f"Removed {len(stale_ids)} stale Chroma "
        f"chunks for {source_path.name}."
    )


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------


def persist_bm25_corpus(
    chunks: list[Document],
    ids: list[str],
) -> None:
    """
    Persist the complete current chunk corpus for BM25.

    BM25 is rebuilt from this file by the API.
    """

    config.BM25_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    corpus = [
        {
            "id": chunk_id,
            "text": chunk.page_content,
            "metadata": chunk.metadata,
        }
        for chunk, chunk_id in zip(
            chunks,
            ids,
        )
    ]

    with open(
        config.BM25_CORPUS_PATH,
        "wb",
    ) as f:

        pickle.dump(
            corpus,
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    print(
        f"Persisted BM25 corpus "
        f"({len(corpus)} chunks) to "
        f"{config.BM25_CORPUS_PATH}"
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main() -> None:

    guidelines = discover_guidelines()

    if not guidelines:

        print(
            f"ERROR: no PDF guidelines found under "
            f"{config.DATA_DIR}."
        )

        print(
            "Add a guideline file, e.g. "
            "data/hypertension_guideline.pdf"
        )

        print(
            "or "
            "data/hypertension/guideline.pdf"
        )

        sys.exit(1)

    # ------------------------------------------------------------------
    # Validate duplicate file stems
    # ------------------------------------------------------------------

    stems = [
        guideline.path.stem
        for guideline in guidelines
    ]

    duplicates = sorted(
        {
            stem
            for stem in stems
            if stems.count(stem) > 1
        }
    )

    if duplicates:

        print(
            "ERROR: duplicate guideline file names "
            f"(rename to make unique): {duplicates}"
        )

        sys.exit(1)

    # ------------------------------------------------------------------
    # Embedding model
    # ------------------------------------------------------------------

    print(
        f"Loading embedding model: "
        f"{config.EMBEDDING_MODEL}"
    )

    embeddings = build_embedding_model()

    # ------------------------------------------------------------------
    # Chroma
    # ------------------------------------------------------------------

    collection = get_or_create_collection()

    print(
        f"Using collection "
        f"'{config.COLLECTION_NAME}' "
        f"at {config.CHROMA_DIR}"
    )

    # ------------------------------------------------------------------
    # Process all guidelines
    # ------------------------------------------------------------------

    all_chunks: list[Document] = []
    all_ids: list[str] = []

    for guideline in guidelines:

        print(
            f"\n{'=' * 70}"
        )

        print(
            f"Guideline: {guideline.type}"
        )

        print(
            f"File: {guideline.path}"
        )

        print(
            f"{'=' * 70}"
        )

        # --------------------------------------------------------------
        # PDF -> pages
        # --------------------------------------------------------------

        pages = load_pdf(
            guideline.path,
            guideline.type,
        )

        print(
            f"Extracted text from "
            f"{len(pages)} pages."
        )

        if not pages:

            print(
                "WARNING: No extractable text found."
            )

            continue

        # --------------------------------------------------------------
        # pages -> chunks
        # --------------------------------------------------------------

        chunks = split_documents(
            pages
        )

        print(
            f"Split into {len(chunks)} chunks "
            f"(chunk_size={config.CHUNK_SIZE}, "
            f"chunk_overlap={config.CHUNK_OVERLAP})."
        )

        print_chunk_statistics(
            chunks
        )

        print_sample_chunks(
            chunks
        )

        # --------------------------------------------------------------
        # IDs
        # --------------------------------------------------------------

        ids = chunk_ids(
            chunks,
            guideline.path,
        )

        if len(ids) != len(set(ids)):

            print(
                f"ERROR: duplicate chunk IDs detected "
                f"for {guideline.path}"
            )

            sys.exit(1)

        # --------------------------------------------------------------
        # Chroma synchronization
        # --------------------------------------------------------------

        store_chunks_in_chroma(
            collection=collection,
            chunks=chunks,
            embeddings=embeddings,
            ids=ids,
        )

        # --------------------------------------------------------------
        # Remove chunks no longer present in PDF
        # --------------------------------------------------------------

        remove_stale_chunks_for_guideline(
            collection=collection,
            source_path=guideline.path,
            current_ids=set(ids),
        )

        # --------------------------------------------------------------
        # BM25 corpus
        # --------------------------------------------------------------

        all_chunks.extend(chunks)
        all_ids.extend(ids)

    # ------------------------------------------------------------------
    # Rebuild BM25 corpus from current source of truth
    # ------------------------------------------------------------------

    persist_bm25_corpus(
        all_chunks,
        all_ids,
    )

    print(
        f"\n{'=' * 70}"
    )

    print(
        "INGESTION COMPLETE"
    )

    print(
        f"{'=' * 70}"
    )

    print(
        f"Guidelines:       {len(guidelines)}"
    )

    print(
        f"Current chunks:   {len(all_chunks)}"
    )

    print(
        f"Chroma collection:{collection.count()}"
    )

    print(
        f"BM25 corpus:      {config.BM25_CORPUS_PATH}"
    )

    print(
        f"{'=' * 70}"
    )


if __name__ == "__main__":
    main()