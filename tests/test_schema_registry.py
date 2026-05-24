"""Tests for schema pattern registry generation."""

from __future__ import annotations

from app.schema.discovery import discover_document_schema
from app.schema.models import DiscoveredPattern, DocumentSchema
from app.schema.registry import build_pattern_registry, regexes_for_discovered_pattern
from app.structure import structure_document

DESIGN_PATTERNS_SECTION = (
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
)


def test_build_pattern_registry_lists_category_patterns() -> None:
    sections, chunks = structure_document("sample.txt", DESIGN_PATTERNS_SECTION)
    schema = discover_document_schema(42, sections, chunks)
    registry = build_pattern_registry(schema)
    assert registry["design_pattern"] == ["ordinal_design_pattern"]


def test_regexes_for_discovered_pattern_compile() -> None:
    pattern = DiscoveredPattern(
        pattern_name="ordinal_design_pattern",
        category="design_pattern",
        trigger_phrases=["the first critical design pattern is"],
        example_sentences=[],
        ordinal_type_phrase="critical design pattern",
    )
    regexes = regexes_for_discovered_pattern(pattern)
    assert regexes
    sentence = "The first critical design pattern is section-aware ingestion."
    assert any(regex.search(sentence) for _, regex in regexes)


def test_registry_from_manual_schema() -> None:
    schema = DocumentSchema(
        document_id=1,
        discovered_patterns=[
            DiscoveredPattern(
                pattern_name="ordinal_capability",
                category="capability",
                ordinal_type_phrase="capability",
            )
        ],
    )
    registry = build_pattern_registry(schema)
    assert registry == {"capability": ["ordinal_capability"]}
