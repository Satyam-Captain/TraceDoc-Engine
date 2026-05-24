"""Tests for deterministic pattern-based phrase extraction."""

from __future__ import annotations

from pathlib import Path

from app.evidence.pattern_extractor import (
    extract_enumerated_phrases,
    extract_enumerated_phrases_with_trace,
)
from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.evidence.structured_composer import compose_structured_answer
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document

ARCHITECTURE_SECTION = (
    "Existing architectures\n\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
)

QUESTION = "what are different architectures mentioned in the pdf?"


def test_most_common_architecture_pattern() -> None:
    text = (
        "The most common pre-generative architecture is the enterprise search stack."
    )
    assert extract_enumerated_phrases(text, "architecture") == ["Enterprise search stack"]


def test_second_architecture_pattern() -> None:
    text = "A second architecture is the classic QA pipeline."
    assert extract_enumerated_phrases(text, "architecture") == ["Classic QA pipeline"]


def test_third_architecture_pattern() -> None:
    text = "A third architecture is the ontology and knowledge-graph stack."
    assert extract_enumerated_phrases(text, "architecture") == [
        "Ontology and knowledge-graph stack"
    ]


def test_duplicate_phrases_removed_deterministically() -> None:
    text = (
        "A second architecture is the classic QA pipeline. "
        "A second architecture is the classic QA pipeline."
    )
    assert extract_enumerated_phrases(text, "architecture") == ["Classic QA pipeline"]


def test_url_and_citation_junk_rejected() -> None:
    text = (
        "A second architecture is https://example.com/bad. "
        "A third architecture is widget [1] et al."
    )
    assert extract_enumerated_phrases(text, "architecture") == []


def test_traceability_includes_source_sentence() -> None:
    sentence = "A second architecture is the classic QA pipeline."
    entries = extract_enumerated_phrases_with_trace(sentence, "architecture")

    assert len(entries) == 1
    assert entries[0].value == "Classic QA pipeline"
    assert entries[0].source_sentence == sentence


def test_unknown_category_returns_empty() -> None:
    assert extract_enumerated_phrases("A capability is X.", "capability") == []


def test_no_hardcoded_architecture_names_in_composer() -> None:
    content = (
        Path(__file__).resolve().parent.parent
        / "app"
        / "evidence"
        / "structured_composer.py"
    ).read_text(encoding="utf-8").lower()
    assert "enterprise search stack" not in content
    assert "classic qa pipeline" not in content
    assert "ontology and knowledge-graph stack" not in content
    assert "traceability and citation graph" not in content


def test_architecture_question_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "architectures_e2e.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(f"# {ARCHITECTURE_SECTION}", encoding="utf-8")

    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(QUESTION, processed.document_id, db_path=str(db_path))

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    lowered = answer.structured_answer.lower()
    assert "enterprise search stack" in lowered
    assert "classic qa pipeline" in lowered
    assert "ontology and knowledge-graph stack" in lowered
    assert "traceability and citation graph" in lowered


def test_compose_structured_answer_uses_pattern_extraction() -> None:
    from app.evidence.models import EvidenceCard

    card = EvidenceCard(
        chunk_id="c1",
        document_name="arch.txt",
        section_title="Existing architectures",
        start_line=1,
        end_line=8,
        snippet=ARCHITECTURE_SECTION,
        matched_terms=["architecture"],
        score=2.0,
        confidence="HIGH",
        why_matched="test",
        citation="arch.txt | lines 1-8",
    )
    answer = compose_structured_answer(QUESTION, [card])

    assert answer is not None
    assert "1. Enterprise search stack" in answer
    assert "2. Classic QA pipeline" in answer
    assert "3. Ontology and knowledge-graph stack" in answer
    assert "4. Traceability and citation graph" in answer
