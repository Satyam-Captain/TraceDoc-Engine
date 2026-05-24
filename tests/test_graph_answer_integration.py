"""End-to-end tests for graph-based QA answers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.models import (
    ANSWER_MODE_GRAPH_STRUCTURED,
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
)
from app.pipeline import process_document
from app.qa import ask_document

USES_DOCUMENT = (
    "Components\n"
    "Enterprise search stack uses repository connectors.\n"
)

STABILITY_DOCUMENT = (
    "Existing architectures\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
    "\n"
    "Design patterns for implementation\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
)


def test_uses_question_returns_graph_structured(tmp_path: Path) -> None:
    source = tmp_path / "uses_doc.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(USES_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))

    answer = ask_document(
        "What does Enterprise search stack use?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_GRAPH_STRUCTURED
    assert answer.structured_answer is not None
    assert "repository connectors" in answer.structured_answer.lower()
    assert answer.cards
    trace = "\n".join(answer.debug_trace)
    assert "graph_answer_used=True" in trace


def test_architecture_question_still_uses_section_structured(tmp_path: Path) -> None:
    source = tmp_path / "stability.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(STABILITY_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))

    answer = ask_document(
        "what are different architectures mentioned in the pdf?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "enterprise search stack" in answer.structured_answer.lower()
    trace = "\n".join(answer.debug_trace)
    assert "graph_answer_used=False" in trace


def test_design_pattern_question_still_uses_section_structured(tmp_path: Path) -> None:
    source = tmp_path / "patterns.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(STABILITY_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))

    answer = ask_document(
        "what are different design patterns mentioned in the pdf?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert "section-aware ingestion" in answer.structured_answer.lower()
