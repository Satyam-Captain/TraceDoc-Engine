"""Tests for deterministic graph candidate extraction."""

from __future__ import annotations

from app.schema.graph_candidates import discover_graph_candidates
from app.structure.models import DocumentChunk


def _chunk(text: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id="c1",
        document_name="sample.txt",
        text=text,
        chunk_type="paragraph",
        start_line=1,
        end_line=1,
    )


def test_uses_relation_extracted() -> None:
    candidates = discover_graph_candidates(
        [_chunk("Enterprise search stack uses repository connectors.")]
    )
    assert len(candidates) == 1
    assert candidates[0].subject == "Enterprise search stack"
    assert candidates[0].relation == "uses"
    assert candidates[0].object == "Repository connectors"


def test_depends_on_relation_extracted() -> None:
    candidates = discover_graph_candidates(
        [_chunk("Pipeline depends on retrieval engine.")]
    )
    assert len(candidates) == 1
    assert candidates[0].relation == "depends on"
    assert candidates[0].object == "Retrieval engine"


def test_unrelated_text_produces_no_graph_candidates() -> None:
    candidates = discover_graph_candidates(
        [_chunk("The weather was sunny and calm all day.")]
    )
    assert candidates == []
