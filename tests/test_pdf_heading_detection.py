"""Tests for PDF-friendly semantic heading detection."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.structure import detect_sections
from app.structure.heading_heuristics import is_probable_heading, score_heading_probability
from app.storage import get_sections_for_document

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "samples" / "pdf_style_document.txt"

PDF_STYLE_TEXT = (
    "What this kind of system really is\n\n"
    "A deterministic document question-answering system retrieves evidence.\n\n"
    "Existing architectures\n\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n\n"
    "Open-source building blocks\n\n"
    "For ingestion, the most useful open-source building blocks include parsers.\n"
)

QUESTION = "what are different architectures mentioned in the pdf?"


def test_score_heading_probability_for_architecture_line() -> None:
    score = score_heading_probability(
        "Existing architectures",
        previous_line="",
        next_line="The most common pre-generative architecture is the enterprise search stack.",
    )
    assert score >= 5.0
    assert is_probable_heading(
        "Existing architectures",
        previous_line="",
        next_line="The most common pre-generative architecture is the enterprise search stack.",
    )


def test_paragraph_line_is_not_heading() -> None:
    line = (
        "The most common pre-generative architecture is the enterprise search stack."
    )
    assert not is_probable_heading(
        line,
        previous_line="Existing architectures",
        next_line="A second architecture is the classic QA pipeline.",
    )


def test_detect_sections_from_pdf_style_text() -> None:
    sections = detect_sections(PDF_STYLE_TEXT)
    titles = [section.title for section in sections]

    assert "What this kind of system really is" in titles
    assert "Existing architectures" in titles
    assert "Open-source building blocks" in titles
    assert len(sections) >= 3


def test_pdf_style_sample_stores_many_sections(tmp_path: Path) -> None:
    source = tmp_path / "pdf_style.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(SAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    sections = get_sections_for_document(db_path, processed.document_id)

    assert len(sections) > 10
    assert any(section.title == "Existing architectures" for section in sections)


def test_architecture_question_uses_section_level_retrieval(tmp_path: Path) -> None:
    source = tmp_path / "pdf_style.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(PDF_STYLE_TEXT, encoding="utf-8")
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
