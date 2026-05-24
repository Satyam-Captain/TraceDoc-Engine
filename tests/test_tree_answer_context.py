"""End-to-end tests for QA with document semantic tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.qa_context import EXTRACTION_SOURCE_TREE

TREE_DOCUMENT = (
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
    "The fourth pattern is citation-first answer composition.\n"
    "The fifth pattern is symbolic enrichment.\n"
    "The sixth pattern is security and audit by design.\n"
)

ARCHITECTURE_QUESTION = "what are different architectures mentioned in the pdf?"
DESIGN_PATTERN_QUESTION = "what are different design patterns mentioned in the pdf?"


@pytest.fixture
def tree_db(tmp_path: Path) -> tuple[Path, int]:
    source = tmp_path / "tree_qa.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(TREE_DOCUMENT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    return db_path, processed.document_id


def _body(answer: str | None) -> str:
    assert answer is not None
    return answer.split("Supporting evidence:")[0].lower()


def test_architecture_question_uses_tree_and_lists_all_items(tree_db: tuple[Path, int]) -> None:
    db_path, document_id = tree_db
    result = ask_document(ARCHITECTURE_QUESTION, document_id, db_path=str(db_path))

    assert result.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert result.retrieved_section_title == "Existing architectures"
    assert result.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    body = _body(result.structured_answer)
    assert "enterprise search stack" in body
    assert "classic qa pipeline" in body
    assert "ontology and knowledge-graph stack" in body
    assert "traceability and citation graph" in body
    assert "section-aware ingestion" not in body

    trace = "\n".join(result.debug_trace)
    assert f"extraction_source={EXTRACTION_SOURCE_TREE}" in trace
    assert "tree_loaded=True" in trace
    assert "structured_answer_generated=True" in trace


def test_design_pattern_question_uses_tree_and_lists_all_items(tree_db: tuple[Path, int]) -> None:
    db_path, document_id = tree_db
    result = ask_document(DESIGN_PATTERN_QUESTION, document_id, db_path=str(db_path))

    assert result.retrieved_section_title == "Design patterns for implementation"
    assert result.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    body = _body(result.structured_answer)
    for marker in (
        "section-aware ingestion",
        "multi-granular indexing",
        "deterministic query interpretation",
        "citation-first answer composition",
        "symbolic enrichment",
        "security and audit by design",
    ):
        assert marker in body
    assert "enterprise search stack" not in body

    trace = "\n".join(result.debug_trace)
    assert f"extraction_source={EXTRACTION_SOURCE_TREE}" in trace


def test_evidence_snippet_matches_structured_extraction_source(tree_db: tuple[Path, int]) -> None:
    db_path, document_id = tree_db
    result = ask_document(DESIGN_PATTERN_QUESTION, document_id, db_path=str(db_path))

    assert result.cards
    snippet = result.cards[0].snippet.replace("[[", "").replace("]]", "").lower()
    assert "section-aware ingestion" in snippet
    assert "symbolic enrichment" in snippet
    assert "enterprise search stack" not in snippet
