"""Tests for rule-based query interpretation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline import process_document
from app.qa import ask_document
from app.query import interpret_query
from app.query.interpreter import build_retrieval_query
from app.query.models import (
    INTENT_COMPARISON,
    INTENT_DEFINITION_LOOKUP,
    INTENT_GENERAL_SEARCH,
    INTENT_LIST_REQUEST,
    INTENT_REQUIREMENT_REFERENCE,
    INTENT_TABLE_LOOKUP,
    INTENT_WHERE_MENTIONED,
)


def test_definition_lookup_intent() -> None:
    intent = interpret_query("What is HPC6?")

    assert intent.intent_type == INTENT_DEFINITION_LOOKUP
    assert "HPC6" in intent.entities or "hpc6" in [term.lower() for term in intent.entities]


def test_where_mentioned_intent() -> None:
    intent = interpret_query("Where is memory mentioned in the policy?")

    assert intent.intent_type == INTENT_WHERE_MENTIONED


def test_list_request_intent() -> None:
    intent = interpret_query("List all security controls")

    assert intent.intent_type == INTENT_LIST_REQUEST


def test_comparison_intent() -> None:
    intent = interpret_query("Compare HPC6 and ISO27001")

    assert intent.intent_type == INTENT_COMPARISON
    assert intent.filters.get("comparison_terms")


def test_table_lookup_intent() -> None:
    intent = interpret_query("Show the table row for memory column")

    assert intent.intent_type == INTENT_TABLE_LOOKUP


def test_requirement_reference_intent() -> None:
    intent = interpret_query("What does REQ-001 require?")

    assert intent.intent_type == INTENT_REQUIREMENT_REFERENCE
    assert "REQ-001" in intent.entities
    assert any(
        value.lower() == "req-001"
        for value in intent.filters.get("requirement_ids", [])
    )


def test_general_search_fallback() -> None:
    intent = interpret_query("cluster memory policy overview")

    assert intent.intent_type == INTENT_GENERAL_SEARCH


def test_empty_question_general_search() -> None:
    intent = interpret_query("   ")

    assert intent.intent_type == INTENT_GENERAL_SEARCH
    assert intent.normalized_terms == []


def test_requirement_ids_preserved_in_retrieval_query() -> None:
    intent = interpret_query("Explain REQ-001 and REQ-002")

    retrieval_query = build_retrieval_query("Explain REQ-001 and REQ-002", intent)

    assert "REQ-001" in retrieval_query
    assert "REQ-002" in retrieval_query


def test_definition_lookup_expands_retrieval_query() -> None:
    intent = interpret_query("Define HPC6")

    retrieval_query = build_retrieval_query("Define HPC6", intent)

    assert "definition" in retrieval_query
    assert "means" in retrieval_query


def test_ask_document_includes_intent_information(tmp_path: Path) -> None:
    source = tmp_path / "policy.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "HPC6 memory requirements are documented.\nREQ-001 applies.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))

    answer = ask_document("What is HPC6?", processed.document_id, db_path=str(db_path))

    assert answer.query_intent is not None
    assert answer.query_intent.intent_type == INTENT_DEFINITION_LOOKUP
    assert answer.query_intent.intent_type in answer.explanation or answer.query_intent.explanation


def test_app_main_still_imports() -> None:
    import importlib

    module = importlib.import_module("app.main")
    assert hasattr(module, "main")
