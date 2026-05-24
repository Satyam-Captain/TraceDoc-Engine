"""Tests for deterministic structured extractive answers."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import (
    ANSWER_MODE_EVIDENCE_ONLY,
    ANSWER_MODE_NO_EVIDENCE,
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
    EvidenceCard,
)
from app.evidence.structured_composer import (
    compose_structured_answer,
    is_list_enumeration_question,
)
from app.pipeline import process_document
from app.qa import ask_document


def _card(snippet: str, *, chunk_id: str = "c1") -> EvidenceCard:
    return EvidenceCard(
        chunk_id=chunk_id,
        document_name="arch.txt",
        section_title="Architectures",
        start_line=1,
        end_line=5,
        snippet=snippet,
        matched_terms=["architecture"],
        score=2.0,
        confidence="HIGH",
        why_matched="test",
        citation="arch.txt | lines 1-5",
    )


def test_list_enumeration_question_detection() -> None:
    assert is_list_enumeration_question("different architectures?") is True
    assert is_list_enumeration_question("what are the storage types") is True
    assert is_list_enumeration_question("explain memory policy") is False


def test_architecture_answer_includes_only_evidence_phrases() -> None:
    cards = [
        _card(
            "Options include the enterprise search stack and the classic QA pipeline."
        ),
    ]
    answer = compose_structured_answer("different architectures?", cards)

    assert answer is not None
    assert "Enterprise search stack" in answer
    assert "Classic QA pipeline" in answer
    assert "Ontology and knowledge-graph stack" not in answer
    assert "Traceability and citation graph" not in answer


def test_architecture_answer_all_four_when_present() -> None:
    snippet = (
        "The enterprise search stack, classic QA pipeline, "
        "ontology and knowledge-graph stack, and traceability and citation graph."
    )
    answer = compose_structured_answer("what are the architectures", [_card(snippet)])

    assert answer is not None
    assert "Enterprise search stack" in answer
    assert "Classic QA pipeline" in answer
    assert "Ontology and knowledge-graph stack" in answer
    assert "Traceability and citation graph" in answer


def test_unknown_list_question_returns_none() -> None:
    cards = [_card("Widgets are described as alpha and beta components.")]
    answer = compose_structured_answer("different widgets?", cards)

    assert answer is None


def test_generic_enumeration_from_ordinal_sentences() -> None:
    snippet = (
        "The first rule is memory isolation.\n"
        "The second rule is CPU binding."
    )
    answer = compose_structured_answer("list the rules", [_card(snippet)])

    assert answer is not None
    assert "memory isolation" in answer.lower()
    assert "cpu binding" in answer.lower()


def test_no_structured_answer_without_cards() -> None:
    assert compose_structured_answer("different architectures?", []) is None


def test_ask_document_structured_extractive_mode(tmp_path: Path) -> None:
    source = tmp_path / "architectures.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "SYSTEM ARCHITECTURES\n\n"
        "The enterprise search stack supports keyword retrieval.\n"
        "The classic QA pipeline uses BM25 and evidence cards.\n"
        "The ontology and knowledge-graph stack links document entities.\n"
        "The traceability and citation graph stores line citations.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "Enterprise search stack" in answer.structured_answer
    assert answer.cards
    assert len(answer.cards) >= 1


def test_no_structured_answer_when_no_evidence(tmp_path: Path) -> None:
    source = tmp_path / "empty_topic.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text("Only unrelated network policy text.\n", encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_NO_EVIDENCE
    assert answer.structured_answer is None
    assert not answer.cards


def test_non_list_question_stays_evidence_only() -> None:
    cards = [_card("The enterprise search stack is documented here.")]
    answer = compose_structured_answer("where is search mentioned", cards)

    assert answer is None
