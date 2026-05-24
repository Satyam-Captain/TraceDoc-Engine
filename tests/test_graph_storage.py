"""Tests for knowledge graph SQLite persistence."""

from __future__ import annotations

from pathlib import Path

from app.graph import build_knowledge_graph
from app.pipeline import process_document
from app.storage import load_knowledge_graph, save_knowledge_graph
from app.structure import structure_document
from app.tree import build_document_tree

SAMPLE_TEXT = (
    "Components\n"
    "Enterprise search stack uses repository connectors.\n"
    "Classic QA pipeline contains question analysis, query generation, search, "
    "and answer extraction.\n"
)


def test_graph_save_and_load_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "storage_sample.txt"
    db_path = tmp_path / "graph_storage.db"
    source.write_text(SAMPLE_TEXT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))

    sections, chunks = structure_document("storage.txt", SAMPLE_TEXT)
    tree = build_document_tree(sections, chunks, document_name="storage.txt")
    original = build_knowledge_graph(processed.document_id, tree, schema=None)

    save_knowledge_graph(str(db_path), processed.document_id, original)
    loaded = load_knowledge_graph(str(db_path), processed.document_id)

    assert loaded is not None
    assert loaded.document_id == processed.document_id
    assert len(loaded.nodes) == len(original.nodes)
    assert len(loaded.edges) == len(original.edges)
    assert {node.node_id for node in loaded.nodes} == {
        node.node_id for node in original.nodes
    }


def test_process_document_loads_graph(tmp_path: Path) -> None:
    source = tmp_path / "doc.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(SAMPLE_TEXT, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))

    graph = load_knowledge_graph(str(db_path), processed.document_id)
    assert graph is not None
    assert any(node.node_type == "document" for node in graph.nodes)
    assert graph.edges
