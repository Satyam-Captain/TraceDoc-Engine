"""Tests for deterministic grammar execution runtime."""

from __future__ import annotations

from app.evidence.extraction_runtime import (
    execute_discovered_grammar_with_result,
    trim_entity_span,
)
from app.schema.discovery import discover_document_schema
from app.schema.models import DiscoveredPattern
from app.schema.registry import primary_grammar_for_category
from app.structure import structure_document

DESIGN_PATTERN_TEXT = (
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
)

UNRELATED_TEXT = (
    "Overview\n\n"
    "This section discusses storage policy and backup windows only.\n"
)


def _ordinal_grammar() -> DiscoveredPattern:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERN_TEXT)
    schema = discover_document_schema(1, sections, chunks)
    grammar = primary_grammar_for_category(schema, "design_pattern")
    assert grammar is not None
    return grammar


def test_single_sentence_extraction() -> None:
    grammar = _ordinal_grammar()
    sentence = "The first critical design pattern is section-aware ingestion."
    result = execute_discovered_grammar_with_result(sentence, grammar)

    assert result.success is True
    assert result.entities == ["Section-aware ingestion"]
    assert result.match_count == 1


def test_multiple_ordinal_extraction() -> None:
    grammar = _ordinal_grammar()
    result = execute_discovered_grammar_with_result(DESIGN_PATTERN_TEXT, grammar)

    assert result.success is True
    assert result.match_count == 3
    assert result.entities == [
        "Section-aware ingestion",
        "Multi-granular indexing",
        "Deterministic query interpretation",
    ]
    assert result.extraction_confidence >= 0.7


def test_optional_modifiers_supported() -> None:
    grammar = _ordinal_grammar()
    text = (
        "The first important capability is elastic scaling.\n"
        "The second common capability is audit logging.\n"
    )
    modified = DiscoveredPattern(
        pattern_name=grammar.pattern_name,
        category=grammar.category,
        type_phrases=["important capability", "common capability", "capability"],
        sentence_templates=grammar.sentence_templates,
        confidence_score=grammar.confidence_score,
        grammar_family=grammar.grammar_family,
    )
    result = execute_discovered_grammar_with_result(text, modified)

    assert result.entities == ["Elastic scaling", "Audit logging"]


def test_deduplication() -> None:
    grammar = _ordinal_grammar()
    text = (
        "The first pattern is shared cache.\n"
        "The second pattern is shared cache.\n"
        "The third pattern is edge routing.\n"
    )
    modified = DiscoveredPattern(
        pattern_name=grammar.pattern_name,
        category=grammar.category,
        type_phrases=["pattern"],
        sentence_templates=grammar.sentence_templates,
        confidence_score=grammar.confidence_score,
        grammar_family=grammar.grammar_family,
    )
    result = execute_discovered_grammar_with_result(text, modified)

    assert result.entities == ["Shared cache", "Edge routing"]


def test_regex_extracts_only_intended_entity_span() -> None:
    grammar = _ordinal_grammar()
    sentence = (
        "The first critical design pattern is section-aware ingestion; "
        "this enables traceability."
    )
    result = execute_discovered_grammar_with_result(sentence, grammar)
    assert result.entities == ["Section-aware ingestion"]


def test_clause_boundary_trimming_works() -> None:
    assert trim_entity_span("section-aware ingestion; this enables traceability") == (
        "section-aware ingestion"
    )
    assert trim_entity_span("multi-granular indexing: a key capability") == (
        "multi-granular indexing"
    )


def test_no_hallucination_on_unrelated_text() -> None:
    grammar = _ordinal_grammar()
    result = execute_discovered_grammar_with_result(UNRELATED_TEXT, grammar)

    assert result.success is False
    assert result.entities == []
    assert result.match_count == 0
    assert result.extraction_confidence == 0.0
