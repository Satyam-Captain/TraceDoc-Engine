"""Tests for PDF layout reconstruction and section recovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.ingestion.pdf_extractor import extract_pdf
from app.ingestion.pdf_layout import reconstruct_pdf_layout
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.structure import detect_sections
from app.storage import get_sections_for_document

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "samples" / "pdf_style_document.txt"

FLAT_ARCHITECTURE_SNIPPET = (
    "A deterministic control mechanism. Existing architectures "
    "The most common pre-generative architecture is the enterprise search stack. "
    "A second architecture is the classic QA pipeline. "
    "A third architecture is the ontology and knowledge-graph stack. "
    "A fourth architecture is the traceability and citation graph."
)

QUESTION = "what are different architectures mentioned in the pdf?"


def test_reconstruct_isolates_existing_architectures_heading() -> None:
    reconstructed = reconstruct_pdf_layout(FLAT_ARCHITECTURE_SNIPPET)

    assert "Existing architectures" in reconstructed
    lines = [line.strip() for line in reconstructed.splitlines() if line.strip()]
    assert "Existing architectures" in lines


def test_reconstruct_flattened_pdf_style_document_yields_many_sections() -> None:
    original = SAMPLE_PATH.read_text(encoding="utf-8")
    flattened = " ".join(
        line.strip() for line in original.splitlines() if line.strip()
    )
    reconstructed = reconstruct_pdf_layout(flattened)
    sections = detect_sections(reconstructed)

    assert len(sections) > 10
    assert any(section.title == "Existing architectures" for section in sections)


def test_pdf_extractor_applies_layout_reconstruction(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = FLAT_ARCHITECTURE_SNIPPET

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]
    mock_reader.metadata = {}

    with patch("app.ingestion.pdf_extractor.PdfReader", return_value=mock_reader):
        text, page_count, metadata, warnings = extract_pdf(str(pdf_path))

    assert page_count == 1
    assert "Existing architectures" in text
    assert "\n\nExisting architectures\n\n" in text or any(
        line.strip() == "Existing architectures"
        for line in text.splitlines()
    )


def test_reconstructed_sample_stored_section_count(tmp_path: Path) -> None:
    original = SAMPLE_PATH.read_text(encoding="utf-8")
    flattened = " ".join(
        line.strip() for line in original.splitlines() if line.strip()
    )
    reconstructed = reconstruct_pdf_layout(flattened)
    source = tmp_path / "reconstructed.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(reconstructed, encoding="utf-8")

    processed = process_document(str(source), db_path=str(db_path))
    sections = get_sections_for_document(db_path, processed.document_id)

    assert len(sections) > 10
    assert any(section.title == "Existing architectures" for section in sections)


def test_architecture_question_after_layout_reconstruction(tmp_path: Path) -> None:
    source = tmp_path / "arch_flat.txt"
    db_path = tmp_path / "tracedoc.db"
    reconstructed = reconstruct_pdf_layout(FLAT_ARCHITECTURE_SNIPPET)
    source.write_text(reconstructed, encoding="utf-8")

    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(QUESTION, processed.document_id, db_path=str(db_path))

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.retrieved_section_title == "Existing architectures"
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    lowered = answer.structured_answer.lower()
    assert "enterprise search stack" in lowered
    assert "classic qa pipeline" in lowered
    assert "ontology and knowledge-graph stack" in lowered
    assert "traceability and citation graph" in lowered
