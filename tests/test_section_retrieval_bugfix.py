"""Regression tests for section-level retrieval trigger (Step 15.1)."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.query.models import INTENT_GENERAL_SEARCH
from app.retrieval.section_searcher import find_relevant_sections
from app.retrieval.section_trigger import should_use_section_retrieval
from app.storage.models import StoredSection


def test_should_use_section_retrieval_for_long_architecture_question() -> None:
    question = "what are different architectures mentioned in the pdf?"
    assert (
        should_use_section_retrieval(question, INTENT_GENERAL_SEARCH) is True
    )


def test_should_use_section_retrieval_for_variants() -> None:
    assert should_use_section_retrieval("different architectures", INTENT_GENERAL_SEARCH)
    assert should_use_section_retrieval(
        "what architectures are mentioned", INTENT_GENERAL_SEARCH
    )
    assert should_use_section_retrieval("types of architecture", INTENT_GENERAL_SEARCH)
    assert should_use_section_retrieval("explain lineage", INTENT_GENERAL_SEARCH)
    assert should_use_section_retrieval("what does lineage mean", INTENT_GENERAL_SEARCH)
    assert should_use_section_retrieval("list capabilities", INTENT_GENERAL_SEARCH)
    assert should_use_section_retrieval(
        "what are different architctures mentioned", INTENT_GENERAL_SEARCH
    )


def test_find_relevant_sections_ranks_existing_architectures_first() -> None:
    sections = [
        StoredSection(
            section_id="s1",
            title="What this kind of system really is",
            level=1,
            start_line=1,
            end_line=8,
        ),
        StoredSection(
            section_id="s2",
            title="Existing architectures",
            level=1,
            start_line=9,
            end_line=20,
        ),
        StoredSection(
            section_id="s3",
            title="Open-source building blocks",
            level=1,
            start_line=21,
            end_line=30,
        ),
    ]

    ranked = find_relevant_sections(
        "what are different architectures mentioned in the pdf?",
        sections,
        top_k=3,
    )

    assert ranked
    assert ranked[0].title == "Existing architectures"


def test_plain_text_architectures_section_end_to_end(tmp_path: Path) -> None:
    """Plain-text heading without markdown must still use section-level retrieval."""
    source = tmp_path / "architectures_plain.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "Existing architectures\n\n"
        "The most common pre-generative architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "what are different architectures mentioned in the pdf?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.retrieved_section_title == "Existing architectures"
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "enterprise search stack" in answer.structured_answer.lower()
    assert "classic qa pipeline" in answer.structured_answer.lower()
    assert "ontology and knowledge-graph stack" in answer.structured_answer.lower()
    assert "traceability and citation graph" in answer.structured_answer.lower()
    assert answer.cards
    assert any(
        "section-level retrieval" in card.why_matched.lower() for card in answer.cards
    )
    assert "transformer architecture" not in answer.structured_answer.lower()


def test_bm25_fallback_when_no_section_match(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "# Security Policy\n\nHPC6 memory requirements are documented.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.retrieval_strategy == "BM25_CHUNK"
