"""Regression tests for section-level retrieval trigger (Step 15.1/15.2)."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.query.models import INTENT_GENERAL_SEARCH
from app.retrieval.section_searcher import derive_sections_from_chunks, find_relevant_sections
from app.retrieval.section_trigger import should_use_section_retrieval
from app.storage import get_chunks_for_document, get_sections_for_document
from app.storage.models import StoredSection

ARCHITECTURES_SAMPLE = (
    "Existing architectures\n\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
)

QUESTION = "what are different architectures mentioned in the pdf?"


def test_should_use_section_retrieval_for_long_architecture_question() -> None:
    assert should_use_section_retrieval(QUESTION, INTENT_GENERAL_SEARCH) is True


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

    ranked = find_relevant_sections(QUESTION, sections, top_k=3)

    assert ranked
    assert ranked[0].title == "Existing architectures"


def test_storage_has_existing_architectures_section_and_chunks(tmp_path: Path) -> None:
    source = tmp_path / "architectures_plain.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(ARCHITECTURES_SAMPLE, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))

    chunks = get_chunks_for_document(db_path, processed.document_id)
    sections = get_sections_for_document(db_path, processed.document_id)
    if not sections:
        sections = derive_sections_from_chunks(chunks)
    assert sections, "expected sections from storage or chunk-derived fallback"
    architecture_section = next(
        (section for section in sections if section.title == "Existing architectures"),
        None,
    )
    assert architecture_section is not None
    assert architecture_section.start_line >= 1
    assert architecture_section.end_line >= architecture_section.start_line

    in_range = [
        chunk
        for chunk in chunks
        if chunk.start_line >= architecture_section.start_line
        and chunk.end_line <= architecture_section.end_line
    ]
    assert in_range, "expected chunks inside Existing architectures line range"


def test_plain_text_architectures_section_end_to_end(tmp_path: Path) -> None:
    """Plain-text heading without markdown must still use section-level retrieval."""
    source = tmp_path / "architectures_plain.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(ARCHITECTURES_SAMPLE, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(QUESTION, processed.document_id, db_path=str(db_path))

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


def test_debug_trace_for_architecture_question(tmp_path: Path) -> None:
    source = tmp_path / "architectures_plain.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(ARCHITECTURES_SAMPLE, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(QUESTION, processed.document_id, db_path=str(db_path))

    trace_text = "\n".join(answer.debug_trace)
    assert "should_use_section_retrieval=True" in trace_text
    assert "selected_section=Existing architectures" in trace_text
    assert "extraction_source=DOCUMENT_TREE" in trace_text
    assert "tree_loaded=True" in trace_text
    assert "using_bm25_fallback=False" in trace_text
    assert not any(line.startswith("fallback_reason=") for line in answer.debug_trace)
    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE

    # Observable trace for UI debugging (printed only on failure by pytest unless -s)
    assert any(line.startswith("candidate_sections=") for line in answer.debug_trace)


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
    trace_text = "\n".join(answer.debug_trace)
    assert "using_bm25_fallback=True" in trace_text
    assert "fallback_reason=" in trace_text
