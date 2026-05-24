"""Tests for deterministic document schema discovery."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.schema.discovery import (
    category_from_heading,
    discover_document_schema,
    match_question_to_schema_category,
)
from app.schema.registry import build_pattern_registry
from app.structure import structure_document
from app.structure.models import DocumentChunk

DESIGN_PATTERNS_SECTION = (
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second design pattern is multi-granular indexing.\n"
    "The third design pattern is deterministic query interpretation.\n"
)


def _chunk(
    text: str,
    *,
    section_title: str,
    section_id: str = "sec-1",
    start_line: int = 1,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"chunk-{start_line}",
        document_name="sample.txt",
        text=text,
        chunk_type="paragraph",
        start_line=start_line,
        end_line=start_line,
        section_title=section_title,
        section_id=section_id,
    )


def test_existing_architectures_heading_maps_to_architecture() -> None:
    result = category_from_heading("Existing architectures")
    assert result is not None
    assert result[0] == "architecture"


def test_design_patterns_heading_maps_to_design_pattern() -> None:
    result = category_from_heading("Design patterns for implementation")
    assert result is not None
    assert result[0] == "design_pattern"


def test_discover_ordinal_patterns_for_design_section() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERNS_SECTION)
    schema = discover_document_schema(1, sections, chunks)
    design_patterns = [
        pattern
        for pattern in schema.discovered_patterns
        if pattern.category == "design_pattern"
    ]
    assert design_patterns
    assert any("the first" in " ".join(pattern.trigger_phrases) for pattern in design_patterns)
    assert any("second" in " ".join(pattern.trigger_phrases) for pattern in design_patterns)


def test_registry_generation_groups_patterns_by_category() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERNS_SECTION)
    schema = discover_document_schema(1, sections, chunks)
    registry = build_pattern_registry(schema)
    assert "design_pattern" in registry
    assert "ordinal_design_pattern" in registry["design_pattern"]


def test_no_hallucinated_categories_from_unrelated_heading() -> None:
    sections, chunks = structure_document(
        "sample.txt",
        "Weather report\n\nIt was sunny and dry.\n",
    )
    schema = discover_document_schema(1, sections, chunks)
    assert not schema.categories


def test_design_patterns_question_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "design_patterns.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(DESIGN_PATTERNS_SECTION, encoding="utf-8")

    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "what design patterns are mentioned?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "1. Section-aware ingestion" in answer.structured_answer
    assert "2. Multi-granular indexing" in answer.structured_answer
    assert "3. Deterministic query interpretation" in answer.structured_answer
    trace_text = "\n".join(answer.debug_trace)
    assert "schema_category_match=design_pattern" in trace_text
    assert "schema_patterns=[ordinal_design_pattern]" in trace_text


def test_match_question_to_schema_category() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERNS_SECTION)
    schema = discover_document_schema(1, sections, chunks)
    matched = match_question_to_schema_category(
        "what design patterns are mentioned?",
        schema,
    )
    assert matched is not None
    assert matched.normalized_name == "design_pattern"
