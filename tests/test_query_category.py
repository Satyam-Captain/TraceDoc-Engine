"""Tests for query target category resolution."""

from __future__ import annotations

from app.schema.discovery import discover_document_schema, match_question_to_schema_category
from app.schema.models import DiscoveredCategory, DiscoveredPattern, DocumentSchema
from app.schema.query_category import resolve_query_target_category
from app.structure import structure_document

DESIGN_QUESTION = "what are different design pattern mentioned in the pdf?"
ARCHITECTURE_QUESTION = "what are different architectures mentioned in the pdf?"


def test_design_pattern_question_resolves_to_design_pattern_not_pattern() -> None:
    schema = DocumentSchema(
        document_id=1,
        categories=[
            DiscoveredCategory(
                name="pattern",
                normalized_name="pattern",
                source_section="A practical reference pattern therefore looks like this:",
                confidence_score=0.85,
            ),
            DiscoveredCategory(
                name="architecture",
                normalized_name="architecture",
                source_section="Existing architectures",
                confidence_score=0.95,
            ),
        ],
        discovered_patterns=[
            DiscoveredPattern(
                pattern_name="ordinal_pattern",
                category="pattern",
                type_phrases=["pattern", "critical design pattern"],
                confidence_score=0.9,
            )
        ],
        discovered_sections=[
            "Existing architectures",
            "Design patterns for implementation",
        ],
    )

    assert resolve_query_target_category(DESIGN_QUESTION, schema) == "design_pattern"
    matched = match_question_to_schema_category(
        DESIGN_QUESTION,
        schema,
        selected_section_title="Design patterns for implementation",
    )
    assert matched is not None
    assert matched.normalized_name == "design_pattern"


def test_architecture_question_resolves_to_architecture() -> None:
    schema = DocumentSchema(
        document_id=1,
        categories=[
            DiscoveredCategory(
                name="pattern",
                normalized_name="pattern",
                source_section="Reference pattern",
                confidence_score=0.85,
            ),
            DiscoveredCategory(
                name="architecture",
                normalized_name="architecture",
                source_section="Existing architectures",
                confidence_score=0.95,
            ),
        ],
    )
    assert resolve_query_target_category(ARCHITECTURE_QUESTION, schema) == "architecture"


def test_schema_discovery_promotes_design_pattern_grammar() -> None:
    text = (
        "Design patterns for implementation\n"
        "The first critical design pattern is section-aware ingestion.\n"
        "The second pattern is multi-granular indexing.\n"
    )
    sections, chunks = structure_document("sample.txt", text)
    schema = discover_document_schema(1, sections, chunks)
    names = {category.normalized_name for category in schema.categories}
    assert "design_pattern" in names
    pattern_names = {pattern.pattern_name for pattern in schema.discovered_patterns}
    assert "ordinal_design_pattern" in pattern_names
