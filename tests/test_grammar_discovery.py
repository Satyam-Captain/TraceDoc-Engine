"""Tests for deterministic extraction grammar discovery."""

from __future__ import annotations

from pathlib import Path

from app.evidence.models import ANSWER_MODE_STRUCTURED_EXTRACTIVE
from app.evidence.pattern_extractor import (
    extract_enumerated_phrases,
    extract_using_discovered_grammar,
)
from app.pipeline import process_document
from app.qa import RETRIEVAL_STRATEGY_SECTION, ask_document
from app.schema.discovery import discover_document_schema
from app.schema.grammar_discovery import discover_extraction_grammars
from app.schema.registry import (
    build_category_registry,
    build_pattern_registry,
    primary_grammar_for_category,
)
from app.structure import structure_document
from app.structure.models import DocumentChunk

DESIGN_PATTERN_TEXT = (
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
)


def _paragraph_chunk(text: str, *, start_line: int = 1) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"c-{start_line}",
        document_name="sample.txt",
        text=text,
        chunk_type="paragraph",
        start_line=start_line,
        end_line=start_line + text.count("\n"),
        section_title="Design patterns for implementation",
    )


def test_ordinal_design_pattern_grammar_discovered() -> None:
    chunk = _paragraph_chunk(DESIGN_PATTERN_TEXT)
    grammars = discover_extraction_grammars(
        "design_pattern",
        [chunk],
        source_section="Design patterns for implementation",
    )
    ordinal = next(
        (grammar for grammar in grammars if grammar.pattern_name == "ordinal_design_pattern"),
        None,
    )
    assert ordinal is not None
    assert ordinal.grammar_family == "ordinal_pattern_enumeration"
    assert ordinal.confidence_score >= 0.65
    assert any("The first <CATEGORY> is <ENTITY>" in template for template in ordinal.sentence_templates)
    assert "pattern" in ordinal.type_phrases


def test_registry_contains_discovered_grammar() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERN_TEXT)
    schema = discover_document_schema(1, sections, chunks)
    registry = build_pattern_registry(schema)
    assert "ordinal_design_pattern" in registry["design_pattern"]

    rich = build_category_registry(schema)
    assert rich["design_pattern"]["section"] == "Design patterns for implementation"
    assert "ordinal_design_pattern" in rich["design_pattern"]["grammars"]


def test_grammar_driven_extraction_returns_entities() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERN_TEXT)
    schema = discover_document_schema(1, sections, chunks)
    grammar = primary_grammar_for_category(schema, "design_pattern")
    assert grammar is not None

    text = DESIGN_PATTERN_TEXT
    entries = extract_using_discovered_grammar(text, grammar)
    values = [entry.value for entry in entries]

    assert "Section-aware ingestion" in values
    assert "Multi-granular indexing" in values
    assert "Deterministic query interpretation" in values


def test_no_grammar_when_ordinal_sentences_absent() -> None:
    chunk = _paragraph_chunk("Overview\n\nThis section has no ordinal enumeration.")
    grammars = discover_extraction_grammars("design_pattern", [chunk])
    assert grammars == []


def test_design_patterns_question_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "design_grammar.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(DESIGN_PATTERN_TEXT, encoding="utf-8")

    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "what design patterns are mentioned?",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.retrieval_strategy == RETRIEVAL_STRATEGY_SECTION
    assert answer.answer_mode == ANSWER_MODE_STRUCTURED_EXTRACTIVE
    assert answer.structured_answer is not None
    assert "Section-aware ingestion" in answer.structured_answer
    assert "Multi-granular indexing" in answer.structured_answer
    assert "Deterministic query interpretation" in answer.structured_answer
    assert "mentions these design patterns" in answer.structured_answer.lower()

    trace = "\n".join(answer.debug_trace)
    assert "schema_category_match=design_pattern" in trace
    assert (
        "discovered_grammar=ordinal_design_pattern" in trace
        or "grammar_used=ordinal_design_pattern" in trace
    )
    assert "grammar_confidence=" in trace
    assert "grammar_sentence_templates=" in trace
    assert "schema_patterns=[ordinal_design_pattern]" in trace
    assert "grammar_execution_success=True" in trace
    assert "extracted_entities_count=3" in trace
    assert "section-aware ingestion" in trace.lower()


def test_extract_enumerated_phrases_via_schema_grammar() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERN_TEXT)
    schema = discover_document_schema(1, sections, chunks)
    phrases = extract_enumerated_phrases(
        DESIGN_PATTERN_TEXT,
        "design_pattern",
        document_schema=schema,
    )
    assert len(phrases) >= 3
