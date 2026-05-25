"""Tests for spaCy blank EntityRuler extraction (no statistical models)."""

from __future__ import annotations

import pytest

pytest.importorskip("spacy")

from app.evidence.entity_ruler import (
    append_entity_ruler_debug,
    build_ruler_nlp,
    extract_ruler_entities,
    get_extraction_mode,
    should_run_entity_ruler,
)


def test_build_ruler_nlp_uses_blank_english_only() -> None:
    nlp = build_ruler_nlp()

    assert nlp.pipe_names == ["entity_ruler"]


def test_extract_requirement_and_definition_spans() -> None:
    text = (
        "REQ-001: Teams must document all controls. "
        "The baseline is defined as the minimum security posture. "
        "Operators shall maintain audit logs."
    )
    entities = extract_ruler_entities(text)

    labels = {entity["label"] for entity in entities}
    assert "REQUIREMENT" in labels
    assert "DEFINITION" in labels

    requirement = next(entity for entity in entities if entity["label"] == "REQUIREMENT")
    assert "must" in requirement["text"].lower()
    assert requirement["start"] < requirement["end"]
    assert text[requirement["start"] : requirement["end"]] == requirement["text"]

    definition = next(entity for entity in entities if entity["label"] == "DEFINITION")
    assert definition["text"].lower() == "is defined as"


def test_extract_ruler_entities_is_deterministic() -> None:
    text = "Systems shall enforce retention. Policy is defined as mandatory rules."

    first = extract_ruler_entities(text)
    second = extract_ruler_entities(text)

    assert first == second


def test_append_entity_ruler_debug_respects_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace: list[str] = []
    text = "Teams must comply. Scope is defined as the documented boundary."

    monkeypatch.setenv("TRACEDOC_EXTRACTION", "grammar")
    append_entity_ruler_debug(trace, text)
    assert trace == ["extraction_mode=grammar"]
    assert not any(line.startswith("entity_ruler_") for line in trace)

    trace.clear()
    monkeypatch.setenv("TRACEDOC_EXTRACTION", "ruler")
    append_entity_ruler_debug(trace, text)
    assert trace[0] == "extraction_mode=ruler"
    assert any(line.startswith("entity_ruler_count=") for line in trace)
    assert should_run_entity_ruler()
    assert get_extraction_mode() == "ruler"

    trace.clear()
    monkeypatch.setenv("TRACEDOC_EXTRACTION", "both")
    append_entity_ruler_debug(trace, text)
    assert trace[0] == "extraction_mode=both"
    assert int(trace[1].split("=", 1)[1]) >= 2
