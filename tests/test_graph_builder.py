"""Tests for deterministic knowledge graph builder."""

from __future__ import annotations

from app.graph import (
    build_knowledge_graph,
    extract_relations_from_sentence,
    find_edges_by_relation,
    find_nodes_by_label,
)
from app.graph.extractor import split_object_list
from app.pipeline import process_document
from app.schema import discover_document_schema
from app.structure import structure_document
from app.tree import build_document_tree

ARCHITECTURE_SECTION = (
    "Existing architectures\n"
    "The most common pre-generative architecture is the enterprise search stack.\n"
    "A second architecture is the classic QA pipeline.\n"
    "A third architecture is the ontology and knowledge-graph stack.\n"
    "A fourth architecture is the traceability and citation graph.\n"
)

DESIGN_SECTION = (
    "Design patterns for implementation\n"
    "The first critical design pattern is section-aware ingestion.\n"
    "The second pattern is multi-granular indexing.\n"
)


def _graph_from_text(text: str, document_id: int = 1):
    sections, chunks = structure_document("graph_test.txt", text)
    tree = build_document_tree(sections, chunks, document_name="graph_test.txt")
    schema = discover_document_schema(document_id, sections, chunks)
    return build_knowledge_graph(document_id, tree, schema)


def _edge_exists(graph, subject: str, relation: str, obj: str) -> bool:
    subject_nodes = find_nodes_by_label(graph, subject)
    object_nodes = find_nodes_by_label(graph, obj)
    if not subject_nodes or not object_nodes:
        return False
    relation_key = relation.replace(" ", "_")
    for edge in graph.edges:
        if edge.relation != relation_key:
            continue
        if edge.source_node_id in {n.node_id for n in subject_nodes}:
            if edge.target_node_id in {n.node_id for n in object_nodes}:
                return True
    return False


def test_graph_has_document_node() -> None:
    graph = _graph_from_text(ARCHITECTURE_SECTION + "\n" + DESIGN_SECTION)
    document_nodes = [node for node in graph.nodes if node.node_type == "document"]
    assert len(document_nodes) == 1


def test_graph_has_section_nodes() -> None:
    graph = _graph_from_text(ARCHITECTURE_SECTION + "\n" + DESIGN_SECTION)
    section_titles = {
        node.label for node in graph.nodes if node.node_type == "section"
    }
    assert "Existing architectures" in section_titles
    assert "Design patterns for implementation" in section_titles


def test_graph_has_contains_edges() -> None:
    graph = _graph_from_text(ARCHITECTURE_SECTION)
    contains = find_edges_by_relation(graph, "contains")
    assert contains
    document_nodes = [n for n in graph.nodes if n.node_type == "document"]
    section_nodes = [n for n in graph.nodes if n.node_type == "section"]
    assert document_nodes and section_nodes
    assert any(
        edge.source_node_id == document_nodes[0].node_id
        and edge.target_node_id == section_nodes[0].node_id
        for edge in contains
    )


def test_uses_relation_from_sentence() -> None:
    relations = extract_relations_from_sentence(
        "Enterprise search stack uses repository connectors."
    )
    assert relations
    assert relations[0].subject == "Enterprise search stack"
    assert relations[0].relation == "uses"
    assert relations[0].object.lower() == "repository connectors"

    graph = _graph_from_text(
        "Architecture\nEnterprise search stack uses repository connectors.\n"
    )
    assert _edge_exists(
        graph, "Enterprise search stack", "uses", "repository connectors"
    )


def test_contains_relation_splits_object_list() -> None:
    objects = split_object_list(
        "question analysis, query generation, search, and answer extraction"
    )
    assert [item.lower() for item in objects] == [
        "question analysis",
        "query generation",
        "search",
        "answer extraction",
    ]

    sentence = (
        "Classic QA pipeline contains question analysis, query generation, "
        "search, and answer extraction."
    )
    relations = extract_relations_from_sentence(sentence)
    assert len(relations) == 4
    assert {item.object for item in relations} == set(objects)

    graph = _graph_from_text(f"Pipeline\n{sentence}\n")
    for obj in objects:
        assert _edge_exists(graph, "Classic QA pipeline", "contains", obj)


def test_no_hallucinated_nodes_from_unrelated_text() -> None:
    graph = _graph_from_text(
        "Random notes\nThe weather is nice today and birds fly south in winter.\n"
    )
    entity_nodes = [
        node
        for node in graph.nodes
        if node.node_type not in {"document", "section", "concept"}
    ]
    assert not entity_nodes


def test_pipeline_persists_graph(tmp_path) -> None:
    source = tmp_path / "graph_doc.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(ARCHITECTURE_SECTION, encoding="utf-8")
    processed = process_document(str(source), db_path=str(db_path))
    from app.storage import load_knowledge_graph

    graph = load_knowledge_graph(str(db_path), processed.document_id)
    assert graph is not None
    assert graph.document_id == processed.document_id
    assert len(graph.nodes) >= 2
    assert len(graph.edges) >= 1
