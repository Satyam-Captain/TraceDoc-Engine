"""Tests for deterministic graph matching."""

from __future__ import annotations

from app.graph import build_knowledge_graph, match_question_graph
from app.graph.matcher import GraphMatch
from app.question_graph import build_question_graph
from app.schema import discover_document_schema
from app.structure import structure_document
from app.tree import build_document_tree


def _graphs(text: str, question: str, document_id: int = 1):
    sections, chunks = structure_document("matcher.txt", text)
    tree = build_document_tree(sections, chunks, document_name="matcher.txt")
    schema = discover_document_schema(document_id, sections, chunks)
    knowledge = build_knowledge_graph(document_id, tree, schema)
    question_graph = build_question_graph(question, schema=schema)
    return question_graph, knowledge


def _entities(matches: list[GraphMatch]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for match in matches:
        for entity in match.answer_entities:
            key = entity.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entity)
    return ordered


def test_uses_relation_match() -> None:
    text = (
        "Components\n"
        "Enterprise search stack uses repository connectors.\n"
    )
    question = "What does Enterprise search stack use?"
    _, knowledge = _graphs(text, question)
    matches = match_question_graph(
        build_question_graph(question), knowledge, top_k=5
    )

    assert matches
    assert any("repository connectors" in e.lower() for e in _entities(matches))


def test_contains_relation_match_lists_all_objects() -> None:
    text = (
        "Pipeline\n"
        "Classic QA pipeline contains question analysis, query generation, "
        "search, and answer extraction.\n"
    )
    question = "What does Classic QA pipeline contain?"
    _, knowledge = _graphs(text, question)
    matches = match_question_graph(
        build_question_graph(question), knowledge, top_k=10
    )
    entities = [e.lower() for e in _entities(matches)]

    assert matches
    for expected in (
        "question analysis",
        "query generation",
        "search",
        "answer extraction",
    ):
        assert any(expected in entity for entity in entities)


def test_architecture_category_match() -> None:
    text = (
        "Existing architectures\n"
        "The most common architecture is the enterprise search stack.\n"
        "A second architecture is the classic QA pipeline.\n"
        "A third architecture is the ontology and knowledge-graph stack.\n"
    )
    question = "What architectures are mentioned?"
    _, knowledge = _graphs(text, question)
    matches = match_question_graph(
        build_question_graph(question), knowledge, top_k=10
    )

    assert matches
    labels = [e.lower() for e in _entities(matches)]
    assert any("enterprise search stack" in label for label in labels)
    assert any("classic qa pipeline" in label for label in labels)


def test_reverse_implements_relation() -> None:
    text = (
        "Policy\n"
        "Compliance module implements policy.\n"
        "Security policy implements access control.\n"
    )
    question = "What implements policy?"
    _, knowledge = _graphs(text, question)
    matches = match_question_graph(
        build_question_graph(question), knowledge, top_k=5
    )

    assert matches
    assert any("compliance module" in entity.lower() for entity in _entities(matches))


def test_no_match_returns_empty_without_crash() -> None:
    text = "Notes\nUnrelated weather discussion only.\n"
    question = "What does Unknown widget use?"
    _, knowledge = _graphs(text, question)
    matches = match_question_graph(
        build_question_graph(question), knowledge, top_k=5
    )
    assert matches == []


def test_graph_match_debug_lines_format() -> None:
    from app.graph.matcher import graph_match_debug_lines

    lines = graph_match_debug_lines([])
    assert "graph_matching_used=True" in lines
    assert "graph_match_count=0" in lines
