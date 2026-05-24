"""Tests for graph-based answer composition."""

from __future__ import annotations

from app.graph.answer_composer import (
    DEFAULT_GRAPH_ANSWER_THRESHOLD,
    compose_graph_answer,
    is_relationship_style_question,
)
from app.graph import build_knowledge_graph
from app.graph.matcher import GraphMatch, match_question_graph
from app.question_graph import build_question_graph
from app.schema import discover_document_schema
from app.structure import structure_document
from app.tree import build_document_tree


def _compose(question: str, text: str) -> tuple[object, object]:
    sections, chunks = structure_document("composer.txt", text)
    tree = build_document_tree(sections, chunks, document_name="composer.txt")
    schema = discover_document_schema(1, sections, chunks)
    knowledge = build_knowledge_graph(1, tree, schema)
    question_graph = build_question_graph(question, schema=schema)
    matches = match_question_graph(question_graph, knowledge, top_k=10)
    answer = compose_graph_answer(question_graph, matches)
    return answer, matches


def test_uses_answer_format() -> None:
    text = "Components\nEnterprise search stack uses repository connectors.\n"
    answer, _ = _compose("What does Enterprise search stack use?", text)
    assert answer is not None
    assert "Enterprise search stack uses:" in answer.structured_answer
    assert "repository connectors" in answer.structured_answer.lower()


def test_contains_answer_lists_all_objects() -> None:
    text = (
        "Pipeline\n"
        "Classic QA pipeline contains question analysis, query generation, "
        "search, and answer extraction.\n"
    )
    answer, _ = _compose("What does Classic QA pipeline contain?", text)
    assert answer is not None
    body = answer.structured_answer.lower()
    assert "classic qa pipeline contains:" in body
    for item in (
        "question analysis",
        "query generation",
        "search",
        "answer extraction",
    ):
        assert item in body


def test_reverse_implements_answer() -> None:
    text = (
        "Policy\n"
        "Compliance module implements policy.\n"
    )
    answer, _ = _compose("What implements policy?", text)
    assert answer is not None
    assert "implement" in answer.structured_answer.lower()
    assert "compliance module" in answer.structured_answer.lower()


def test_no_answer_when_score_below_threshold() -> None:
    weak_match = GraphMatch(
        matched=True,
        score=DEFAULT_GRAPH_ANSWER_THRESHOLD - 1.0,
        answer_entities=["Only one"],
        explanation="weak",
    )
    question_graph = build_question_graph("What does X use?")
    answer = compose_graph_answer(question_graph, [weak_match])
    assert answer is None


def test_enumeration_question_not_relationship_style() -> None:
    question_graph = build_question_graph("What architectures are mentioned?")
    assert not is_relationship_style_question(question_graph)
