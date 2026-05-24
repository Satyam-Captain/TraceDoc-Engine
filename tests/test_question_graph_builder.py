"""Tests for deterministic question graph builder."""

from __future__ import annotations

from app.question_graph import (
    UNKNOWN_SLOT_LABEL,
    build_question_graph,
)
from app.question_graph.models import QuestionGraph
from app.query import interpret_query
from app.query.models import INTENT_DEFINITION_LOOKUP, INTENT_LIST_REQUEST


def _graph(question: str, *, schema=None) -> QuestionGraph:
    intent = interpret_query(question)
    return build_question_graph(question, query_intent=intent, schema=schema)


def _entity_labels(graph: QuestionGraph) -> list[str]:
    return [node.label for node in graph.nodes if node.node_type == "entity"]


def _unknown_nodes(graph: QuestionGraph) -> list[str]:
    return [node for node in graph.nodes if node.node_type == "unknown"]


def _edge_relations(graph: QuestionGraph) -> list[str]:
    return [edge.relation for edge in graph.edges]


def test_enterprise_search_stack_uses_relation() -> None:
    graph = _graph("What does Enterprise search stack use?")

    assert graph.target_relation == "uses"
    assert "Enterprise search stack" in _entity_labels(graph)
    assert _unknown_nodes(graph)
    assert graph.unknown_slots
    assert "uses" in _edge_relations(graph)


def test_classic_qa_pipeline_contains_relation() -> None:
    graph = _graph("What does Classic QA pipeline contain?")

    assert graph.target_relation == "contains"
    assert "Classic QA pipeline" in _entity_labels(graph)
    assert _unknown_nodes(graph)
    assert "contains" in _edge_relations(graph)


def test_architectures_mentioned_category() -> None:
    graph = _graph("What architectures are mentioned?")

    assert graph.target_category == "architecture"
    assert graph.intent_type == INTENT_LIST_REQUEST
    assert any(node.node_type == "category" for node in graph.nodes)
    assert _unknown_nodes(graph)
    assert "mentions" in _edge_relations(graph)


def test_design_patterns_mentioned_category() -> None:
    graph = _graph("What design patterns are mentioned?")

    assert graph.target_category == "design_pattern"
    assert any(
        node.normalized_label == "design pattern" for node in graph.nodes
    )


def test_explain_lineage_definition_intent() -> None:
    graph = _graph("Explain lineage")

    assert graph.intent_type == INTENT_DEFINITION_LOOKUP
    assert "lineage" in [label.lower() for label in _entity_labels(graph)]
    assert graph.target_relation == "definition"
    assert "definition" in _edge_relations(graph)


def test_vague_question_does_not_invent_entities() -> None:
    graph = _graph("Tell me something about the document")

    assert not _entity_labels(graph)
    assert _unknown_nodes(graph)
    assert all(
        node.label != "Enterprise search stack" for node in graph.nodes
    )
    assert len(graph.nodes) <= 2


def test_implements_reverse_relation() -> None:
    graph = _graph("What implements Classic QA pipeline?")

    assert graph.target_relation == "implements"
    assert "Classic QA pipeline" in [
        node.label for node in graph.nodes if node.node_type == "relation_target"
    ]
    assert _unknown_nodes(graph)


def test_question_graph_debug_lines() -> None:
    from app.question_graph import question_graph_debug_lines

    graph = _graph("What does Enterprise search stack use?")
    trace = question_graph_debug_lines(graph)
    assert "question_graph_built=True" in trace
    assert any(line.startswith("qgraph_nodes=") for line in trace)
    assert "qgraph_target_relation=uses" in trace
