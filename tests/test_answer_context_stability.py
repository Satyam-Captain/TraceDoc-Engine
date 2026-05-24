"""End-to-end stability tests for unified AnswerContext extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document

STABILITY_DOCUMENT = (
    "Existing architectures\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "OpenEphyra embodied a modular implementation with question analysis, query generation, "
    "search, and answer extraction/selection.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
    "\n"
    "Design patterns for implementation\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
    "The fourth pattern is citation-first answer composition.\n"
    "The fifth pattern is symbolic enrichment.\n"
    "The sixth pattern is security and audit by design.\n"
)

ARCHITECTURE_QUESTION = "what are different architectures mentioned in the pdf?"
DESIGN_PATTERN_QUESTION = "what are different design patterns mentioned in the pdf?"

ARCHITECTURE_MARKERS = (
    "enterprise search stack",
    "ontology and knowledge-graph stack",
    "traceability and citation graph",
)

DESIGN_PATTERN_MARKERS = (
    "section-aware ingestion",
    "multi-granular indexing",
    "deterministic query interpretation",
    "citation-first answer composition",
    "symbolic enrichment",
    "security and audit by design",
)

ARCHITECTURE_FORBIDDEN_IN_DESIGN = (
    "enterprise search stack",
    "ontology and knowledge-graph stack",
    "traceability and citation graph",
)

DESIGN_FORBIDDEN_IN_ARCHITECTURE = (
    "section-aware ingestion",
    "multi-granular indexing",
    "citation-first answer composition",
)


@pytest.fixture
def stability_db(tmp_path: Path) -> tuple[Path, int]:
    source = tmp_path / "answer_context_stability.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(STABILITY_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    return db_path, processed.document_id


def _answer_body(answer: str | None) -> str:
    assert answer is not None
    return answer.split("Supporting evidence:")[0].lower()


def test_architecture_question_structured_extractive(stability_db: tuple[Path, int]) -> None:
    db_path, document_id = stability_db
    result = ask_document(ARCHITECTURE_QUESTION, document_id, db_path=str(db_path))

    assert result.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert result.retrieved_section_title == "Existing architectures"
    assert result.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    body = _answer_body(result.structured_answer)
    for marker in ARCHITECTURE_MARKERS:
        assert marker in body
    for forbidden in DESIGN_FORBIDDEN_IN_ARCHITECTURE:
        assert forbidden not in body

    trace = "\n".join(result.debug_trace)
    assert "structured_answer_generated=True" in trace
    assert "target_category=architecture" in trace
    for card in result.cards:
        assert card.section_title == "Existing architectures"


def test_design_pattern_question_structured_extractive(stability_db: tuple[Path, int]) -> None:
    db_path, document_id = stability_db
    result = ask_document(DESIGN_PATTERN_QUESTION, document_id, db_path=str(db_path))

    assert result.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert result.retrieved_section_title == "Design patterns for implementation"
    assert result.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    body = _answer_body(result.structured_answer)
    for marker in DESIGN_PATTERN_MARKERS:
        assert marker in body
    for forbidden in ARCHITECTURE_FORBIDDEN_IN_DESIGN:
        assert forbidden not in body

    trace = "\n".join(result.debug_trace)
    assert "structured_answer_generated=True" in trace
    assert "target_category=design_pattern" in trace
    for card in result.cards:
        assert card.section_title == "Design patterns for implementation"


def test_extraction_text_aligns_with_evidence_snippet(stability_db: tuple[Path, int]) -> None:
    db_path, document_id = stability_db
    result = ask_document(DESIGN_PATTERN_QUESTION, document_id, db_path=str(db_path))

    trace = "\n".join(result.debug_trace)
    assert "extraction_text_preview=" in trace
    assert "extraction_text_line_range=" in trace
    assert result.cards
    snippet_plain = result.cards[0].snippet.replace("[[", "").replace("]]", "").lower()
    assert "section-aware ingestion" in snippet_plain
