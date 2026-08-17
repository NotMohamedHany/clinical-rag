"""Unit tests for multi-guideline ingestion: discovery, typing, metadata.

Run from the project root:

    python -m pytest tests/test_ingestion.py -v
"""

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.ingest import (  # noqa: E402
    chunk_ids,
    discover_guidelines,
    guideline_type,
    load_pdf,
    split_documents,
)


def make_pdf(path: Path, text: str = "Fasting plasma glucose threshold test content.") -> None:
    """Create a tiny one-page PDF with the given text (PyMuPDF, no deps).

    insert_textbox wraps long text across the page; insert_text would drop
    anything wider than the page, which breaks chunking tests.
    """
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), text, fontsize=8)
    document.save(str(path))
    document.close()


def test_type_from_directory_name(tmp_path: Path) -> None:
    pdf = tmp_path / "hypertension" / "guideline.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.touch()
    assert guideline_type(pdf, tmp_path) == "hypertension"


def test_type_from_filename_suffix(tmp_path: Path) -> None:
    pdf = tmp_path / "diabetes_guideline.pdf"
    pdf.touch()
    assert guideline_type(pdf, tmp_path) == "diabetes"


def test_type_from_plain_stem(tmp_path: Path) -> None:
    pdf = tmp_path / "covid19.pdf"
    pdf.touch()
    assert guideline_type(pdf, tmp_path) == "covid19"


def test_discover_guidelines_finds_all_pdfs(tmp_path: Path) -> None:
    (tmp_path / "hypertension").mkdir()
    (tmp_path / "hypertension" / "guideline.pdf").touch()
    (tmp_path / "diabetes_guideline.pdf").touch()
    (tmp_path / "notes.txt").touch()

    found = discover_guidelines(tmp_path)
    assert {(g.type, g.path.name) for g in found} == {
        ("hypertension", "guideline.pdf"),
        ("diabetes", "diabetes_guideline.pdf"),
    }


def test_discover_guidelines_empty_dir(tmp_path: Path) -> None:
    assert discover_guidelines(tmp_path) == []


def test_load_pdf_metadata_carries_type(tmp_path: Path) -> None:
    pdf = tmp_path / "diabetes_guideline.pdf"
    make_pdf(pdf)

    documents = load_pdf(pdf, "diabetes")
    assert documents, "PDF produced no documents"
    assert documents[0].metadata["type"] == "diabetes"
    assert documents[0].metadata["page"] == 1
    assert documents[0].metadata["source"] == str(pdf)


def test_chunks_inherit_type_and_have_stable_ids(tmp_path: Path) -> None:
    pdf = tmp_path / "diabetes_guideline.pdf"
    make_pdf(pdf, "Diagnosis of diabetes. " * 60)  # long enough to split

    chunks = split_documents(load_pdf(pdf, "diabetes"))
    assert len(chunks) > 1, "text should split into multiple chunks"
    assert all(chunk.metadata["type"] == "diabetes" for chunk in chunks)
    assert all(chunk.metadata["page"] == 1 for chunk in chunks)

    ids = chunk_ids(chunks, pdf)
    assert len(ids) == len(chunks)
    assert ids[0].startswith("diabetes_guideline-p001-c000")
    assert len(set(ids)) == len(ids), "chunk IDs must be unique"
