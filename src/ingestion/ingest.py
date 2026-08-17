"""Ingestion: guideline PDFs -> pages -> chunks -> ChromaDB + BM25 corpus.

Run from the project root:

    python -m src.ingestion.ingest

Every PDF under `data/` is ingested; the clinical `type` of each guideline
is resolved as follows and stored in every chunk's metadata:

    data/<type>/<file>.pdf        -> the directory name (e.g. "hypertension")
    data/<type>_guideline.pdf     -> the filename stem, minus the suffix
                                     (e.g. "diabetes_guideline.pdf" -> "diabetes")

Chroma ingestion is idempotent: every chunk gets a stable ID derived from
the file name, page and chunk position, and only missing IDs are added.
Chunks stored by an older version (without the `type` field) are
automatically backfilled. The BM25 corpus is rebuilt on every run, so both
indexes always match the same chunks.
"""

import pickle
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

import chromadb
import pymupdf
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import config
from src.rag.embeddings import build_embedding_model

SAMPLES_TO_PRINT = 3

# Suffixes stripped from a filename stem to derive the guideline type
# (e.g. data/hypertension_guideline.pdf -> "hypertension").
_GUIDELINE_SUFFIXES = ("_guideline", "-guideline")


@dataclass(frozen=True)
class Guideline:
    """One guideline PDF and the clinical type it is classified as."""

    path: Path
    type: str


def guideline_type(path: Path, data_dir: Path) -> str:
    """Resolve the clinical type of a guideline PDF (see module docstring)."""
    try:
        relative = path.resolve().relative_to(data_dir.resolve())
    except ValueError:
        relative = Path(path.name)
    if len(relative.parts) > 1:
        return relative.parts[0]

    stem = path.stem
    for suffix in _GUIDELINE_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def discover_guidelines(data_dir: Path = config.DATA_DIR) -> list[Guideline]:
    """All *.pdf files under data_dir, each with its resolved type."""
    if not data_dir.exists():
        return []
    return [
        Guideline(path=path, type=guideline_type(path, data_dir))
        for path in sorted(data_dir.rglob("*.pdf"))
    ]


def load_pdf(path: Path, guideline_type_name: str) -> list[Document]:
    """Extract text from each PDF page into a LangChain Document.

    Each Document carries metadata {"source", "page", "type"}. Pages with
    no extractable text are skipped.
    """
    documents: list[Document] = []
    with pymupdf.open(path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text().strip()
            if not text:
                continue
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": str(path),
                        "page": page_number,
                        "type": guideline_type_name,
                    },
                )
            )
    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """Split page Documents into overlapping chunks (size/overlap in config).

    Each chunk inherits the metadata (source, page, type) of its page.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    return splitter.split_documents(documents)


def chunk_ids(chunks: list[Document], pdf_path: Path) -> list[str]:
    """Stable chunk IDs of the form <pdf-name>-p<page>-c<position>.

    File names must be unique across data/, so the ID alone identifies the
    chunk (this keeps re-ingestion idempotent).
    """
    stem = pdf_path.stem
    return [
        f"{stem}-p{chunk.metadata['page']:03d}-c{index:03d}"
        for index, chunk in enumerate(chunks)
    ]


def print_chunk_statistics(chunks: list[Document]) -> None:
    """Print page/chunk counts and chunk length statistics."""
    lengths = [len(chunk.page_content) for chunk in chunks]
    print(f"Number of pages: {len({chunk.metadata['page'] for chunk in chunks})}")
    print(f"Number of chunks: {len(chunks)}")
    print(f"Average chunk length: {statistics.mean(lengths):.0f} characters")
    print(f"Minimum chunk length: {min(lengths)} characters")
    print(f"Maximum chunk length: {max(lengths)} characters")


def print_sample_chunks(chunks: list[Document], count: int = SAMPLES_TO_PRINT) -> None:
    """Print the first few chunks so the user can eyeball extraction quality."""
    for chunk in chunks[:count]:
        print("\n" + "-" * 60)
        print(f"Sample chunk (page {chunk.metadata['page']}):")
        print("-" * 60)
        preview = chunk.page_content[:300]
        print(preview + ("..." if len(chunk.page_content) > 300 else ""))


def get_or_create_collection() -> chromadb.Collection:
    """Open (or create) the persistent Chroma collection."""
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return client.get_or_create_collection(name=config.COLLECTION_NAME)


def store_chunks_in_chroma(
    collection: chromadb.Collection,
    chunks: list[Document],
    embeddings,
    ids: list[str],
) -> None:
    """Add only the chunks not already stored (idempotent).

    Also backfills the `type` metadata field on chunks that were stored by
    an older version of the ingestion script.
    """
    existing = collection.get(ids=ids, include=["metadatas"])
    existing_ids = set(existing["ids"])

    # Backfill: chunks from before the multi-guideline version lack "type".
    stale_ids = [
        chunk_id
        for chunk_id, metadata in zip(existing["ids"], existing["metadatas"])
        if "type" not in metadata
    ]
    if stale_ids:
        metadata_by_id = {chunk_id: chunk.metadata for chunk, chunk_id in zip(chunks, ids)}
        collection.update(
            ids=stale_ids,
            metadatas=[metadata_by_id[chunk_id] for chunk_id in stale_ids],
        )
        print(f"Backfilled 'type' metadata on {len(stale_ids)} existing chunks.")

    to_add = [
        (chunk, chunk_id)
        for chunk, chunk_id in zip(chunks, ids)
        if chunk_id not in existing_ids
    ]
    print(f"to add: {len(to_add)}")
    print(f"existing ids: {len(existing_ids)}")
    print(f"ids: {len(ids)}")
    if not to_add:
        print(f"\nNothing to add: all {len(ids)} chunks are already in Chroma.")
        return

    print(f"\nGenerating embeddings for {len(to_add)} new chunks...")
    vectors = embeddings.embed_documents([chunk.page_content for chunk, _ in to_add])

    collection.add(
        ids=[chunk_id for _, chunk_id in to_add],
        documents=[chunk.page_content for chunk, _ in to_add],
        metadatas=[chunk.metadata for chunk, _ in to_add],
        embeddings=vectors,
    )
    print(f"Stored {len(to_add)} new chunks (skipped {len(ids) - len(to_add)} already present).")


def persist_bm25_corpus(chunks: list[Document], ids: list[str]) -> None:
    """Write the chunk corpus (text + metadata + stable IDs) for BM25.

    The BM25 index itself is rebuilt from this file when the API starts,
    so it does not need to be rebuilt for every request.
    """
    config.BM25_DIR.mkdir(parents=True, exist_ok=True)
    corpus = [
        {"id": chunk_id, "text": chunk.page_content, "metadata": chunk.metadata}
        for chunk, chunk_id in zip(chunks, ids)
    ]
    with open(config.BM25_CORPUS_PATH, "wb") as f:
        pickle.dump(corpus, f)
    print(f"Persisted BM25 corpus ({len(corpus)} chunks) to {config.BM25_CORPUS_PATH}")


def main() -> None:
    guidelines = discover_guidelines()
    if not guidelines:
        print(f"ERROR: no PDF guidelines found under {config.DATA_DIR}.")
        print("Add a guideline file, e.g. data/hypertension_guideline.pdf")
        print("or data/hypertension/guideline.pdf, and run this script again.")
        sys.exit(1)

    # Chunk IDs are derived from the file name only, so file names must be
    # unique across data/ to keep ingestion idempotent.
    stems = [guideline.path.stem for guideline in guidelines]
    duplicates = sorted({stem for stem in stems if stems.count(stem) > 1})
    if duplicates:
        print(f"ERROR: duplicate guideline file names (rename to make unique): {duplicates}")
        sys.exit(1)

    print(f"Loading embedding model: {config.EMBEDDING_MODEL}")
    embeddings = build_embedding_model()

    collection = get_or_create_collection()
    print(f"Using collection '{config.COLLECTION_NAME}' at {config.CHROMA_DIR}")

    all_chunks: list[Document] = []
    all_ids: list[str] = []
    for guideline in guidelines:
        print(f"\n--- Guideline '{guideline.type}': {guideline.path} ---")
        pages = load_pdf(guideline.path, guideline.type)
        print(f"Extracted text from {len(pages)} pages.")

        chunks = split_documents(pages)
        print(
            f"Split into {len(chunks)} chunks "
            f"(chunk_size={config.CHUNK_SIZE}, chunk_overlap={config.CHUNK_OVERLAP})."
        )
        print_chunk_statistics(chunks)
        print_sample_chunks(chunks)

        ids = chunk_ids(chunks, guideline.path)
        store_chunks_in_chroma(collection, chunks, embeddings, ids)
        all_chunks.extend(chunks)
        all_ids.extend(ids)

    persist_bm25_corpus(all_chunks, all_ids)
    print(
        f"\nDone. Collection holds {collection.count()} chunks "
        f"from {len(guidelines)} guideline(s)."
    )


if __name__ == "__main__":
    main()
