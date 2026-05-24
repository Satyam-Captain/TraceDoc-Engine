"""Tests for semantic heading and category normalization."""

from __future__ import annotations

from app.schema.normalization import (
    category_confidence_from_heading,
    extract_candidate_category,
    meets_category_confidence_threshold,
    normalize_category_name,
    normalize_heading_text,
    singularize_term,
)


def test_existing_architectures_normalizes_to_architecture() -> None:
    assert extract_candidate_category("Existing architectures") == "architecture"
    assert normalize_category_name("Existing architectures") == "architecture"


def test_design_patterns_for_implementation_normalizes_to_design_pattern() -> None:
    assert extract_candidate_category("Design patterns for implementation") == "design_pattern"
    assert normalize_heading_text("Design patterns for implementation") == "design patterns"
    assert normalize_category_name("Design patterns for implementation") == "design_pattern"


def test_open_source_building_blocks_normalizes() -> None:
    assert extract_candidate_category("Open-source building blocks") == "building_block"


def test_common_capabilities_normalizes() -> None:
    assert extract_candidate_category("Common capabilities") == "capability"


def test_overview_heading_rejected() -> None:
    assert extract_candidate_category("Overview") is None
    confidence = category_confidence_from_heading("Overview", "general")
    assert not meets_category_confidence_threshold(confidence)


def test_singularize_term() -> None:
    assert singularize_term("architectures") == "architecture"
    assert singularize_term("patterns") == "pattern"


def test_question_text_extracts_design_pattern_category() -> None:
    assert (
        extract_candidate_category(
            "what are different design pattern mentioned in the pdf?"
        )
        == "design_pattern"
    )
