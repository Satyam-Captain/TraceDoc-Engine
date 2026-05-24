"""Tests for category-aligned extraction validation."""

from __future__ import annotations

from app.evidence.extraction_validator import (
    REJECTION_CATEGORY_BOUNDARY,
    build_extraction_validation_registry,
    explain_rejection,
    filter_validated_entities,
    validate_extracted_entity,
)
from app.schema.discovery import discover_document_schema
from app.structure import structure_document

BOUNDARY_DOCUMENT = (
    "Existing architectures\n\n"
    "The most common architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n\n"
    "Design patterns for implementation\n\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
    "The third pattern is deterministic query interpretation.\n"
    "The fourth pattern is citation-first answer composition.\n"
    "The fifth pattern is symbolic enrichment.\n"
)


def _validation_registry():
    sections, chunks = structure_document("boundary.txt", BOUNDARY_DOCUMENT)
    schema = discover_document_schema(1, sections, chunks)
    design_text = (
        "The first critical design pattern is section-aware ingestion.\n"
        "The second pattern is multi-granular indexing.\n"
        "The third pattern is deterministic query interpretation.\n"
        "The fourth pattern is citation-first answer composition.\n"
        "The fifth pattern is symbolic enrichment.\n"
    )
    arch_text = (
        "The most common architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
        "A fourth architecture is the traceability and citation graph.\n"
    )
    return build_extraction_validation_registry(
        schema,
        full_text_by_category={
            "design_pattern": design_text,
            "architecture": arch_text,
        },
    )


def test_architecture_entity_rejected_from_design_pattern_category() -> None:
    registry = _validation_registry()
    assert (
        validate_extracted_entity(
            "Classic QA pipeline",
            "design_pattern",
            "A second architecture is the classic QA pipeline.",
            registry,
            section_title="Design patterns for implementation",
        )
        is False
    )
    reason = explain_rejection(
        "Classic QA pipeline",
        "design_pattern",
        "A second architecture is the classic QA pipeline.",
        registry,
        section_title="Design patterns for implementation",
    )
    assert reason in {
        REJECTION_CATEGORY_BOUNDARY,
        "conflicting_category_entity",
        "grammar_sentence_mismatch",
        "section_scope_violation",
    }


def test_valid_design_pattern_accepted() -> None:
    registry = _validation_registry()
    assert validate_extracted_entity(
        "Section-aware ingestion",
        "design_pattern",
        "The first critical design pattern is section-aware ingestion.",
        registry,
        section_title="Design patterns for implementation",
    )


def test_cross_category_contamination_rejected() -> None:
    registry = _validation_registry()
    filtered = filter_validated_entities(
        [
            (
                "Ontology and knowledge-graph stack",
                "A third architecture is the ontology and knowledge-graph stack.",
                "Design patterns for implementation",
            ),
            (
                "Multi-granular indexing",
                "The second pattern is multi-granular indexing.",
                "Design patterns for implementation",
            ),
        ],
        "design_pattern",
        registry,
    )
    assert filtered.validated_entities == ["Multi-granular indexing"]
    assert "Ontology and knowledge-graph stack" in filtered.rejected_entities


def test_entities_from_unrelated_sections_rejected() -> None:
    registry = _validation_registry()
    assert (
        validate_extracted_entity(
            "Enterprise search stack",
            "design_pattern",
            "The most common architecture is the enterprise search stack.",
            registry,
            section_title="Existing architectures",
        )
        is False
    )
