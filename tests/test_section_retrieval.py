"""Tests for section hierarchy and section-level retrieval."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import ask_document
from app.retrieval.section_searcher import (
    collect_section_chunks,
    find_relevant_sections,
    score_section_relevance,
)
from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection
from app.storage.models import StoredChunk, StoredSection


def _section(
    section_id: str,
    title: str,
    *,
    start_line: int,
    end_line: int = 1,
    level: int = 1,
) -> DocumentSection:
    return DocumentSection(
        section_id=section_id,
        title=title,
        level=level,
        start_line=start_line,
        end_line=end_line,
        parent_section_id=None,
    )


def test_infer_section_ranges_sets_end_line_before_next_section() -> None:
    sections = [
        _section("s1", "Existing architectures", start_line=10, end_line=10),
        _section("s2", "Open-source building blocks", start_line=20, end_line=20),
    ]
    ranged = infer_section_ranges(sections, total_lines=30)

    assert ranged[0].start_line == 10
    assert ranged[0].end_line == 19
    assert ranged[1].end_line == 30


def test_build_section_hierarchy_assigns_parent_ids() -> None:
    sections = [
        _section("s1", "Root", start_line=1, end_line=1, level=1),
        _section("s2", "Child", start_line=5, end_line=5, level=2),
    ]
    hierarchy = build_section_hierarchy(sections)

    assert hierarchy[0].parent_section_id is None
    assert hierarchy[1].parent_section_id == "s1"


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

    ranked = find_relevant_sections("different architectures", sections, top_k=3)

    assert ranked
    assert ranked[0].title == "Existing architectures"
    assert score_section_relevance("different architectures", ranked[0]) > 0


def test_collect_section_chunks_returns_ordered_in_range_chunks() -> None:
    section = StoredSection(
        section_id="s2",
        title="Existing architectures",
        level=1,
        start_line=5,
        end_line=12,
    )
    chunks = [
        StoredChunk(
            chunk_id="c1",
            document_name="doc.txt",
            text="Existing architectures",
            chunk_type="section",
            start_line=5,
            end_line=5,
            section_id="s2",
            section_title="Existing architectures",
        ),
        StoredChunk(
            chunk_id="c2",
            document_name="doc.txt",
            text="The enterprise search stack ...",
            chunk_type="paragraph",
            start_line=6,
            end_line=6,
            section_id="s2",
            section_title="Existing architectures",
        ),
        StoredChunk(
            chunk_id="c3",
            document_name="doc.txt",
            text="Unrelated intro",
            chunk_type="paragraph",
            start_line=2,
            end_line=2,
            section_id="s1",
            section_title="Intro",
        ),
    ]

    selected = collect_section_chunks(section, chunks, max_chunks=20)

    assert [chunk.chunk_id for chunk in selected] == ["c1", "c2"]


def test_ask_document_section_level_architectures_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "architectures.pdf.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "# What this kind of system really is\n\n"
        "General background only.\n\n"
        "# Existing architectures\n\n"
        "The most common pre-generative architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph.\n\n"
        "# Open-source building blocks\n\n"
        "Other tools are listed here.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "what are different architectures mentioned in the pdf?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "these architecture families" in answer.structured_answer.lower()
    assert "1. Enterprise search stack" in answer.structured_answer
    assert "2. Classic QA pipeline" in answer.structured_answer
    assert "3. Ontology and knowledge-graph stack" in answer.structured_answer
    assert "4. Traceability and citation graph" in answer.structured_answer
    assert "transformer architecture" not in answer.structured_answer.lower()
    assert answer.cards
    assert answer.section_retrieval_used is True
    assert answer.retrieved_section_title == "Existing architectures"
    assert any(
        "section-level retrieval" in card.why_matched.lower() for card in answer.cards
    )


def test_section_retrieval_partial_architectures_only(tmp_path: Path) -> None:
    source = tmp_path / "partial.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "# Existing architectures\n\n"
        "The enterprise search stack is common.\n"
        "A second architecture is the classic QA pipeline.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.structured_answer is not None
    assert "Enterprise search stack" in answer.structured_answer
    assert "Classic QA pipeline" in answer.structured_answer
    assert "Ontology and knowledge-graph stack" not in answer.structured_answer


def test_bm25_fallback_when_no_relevant_section(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "# Security Policy\n\n"
        "HPC6 memory requirements are documented.\n"
        "REQ-001 defines baseline controls.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "different architectures",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.section_retrieval_used is False
    assert answer.answer_mode in {"EVIDENCE_ONLY", "NO_EVIDENCE"}
