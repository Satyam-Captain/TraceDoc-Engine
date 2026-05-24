"""Tests for evidence context expansion and explanation retrieval."""

from __future__ import annotations

from pathlib import Path

from app.evidence.context import expand_result_context, needs_context_expansion
from app.indexing import prepare_document_chunks
from app.pipeline import process_document
from app.qa import ask_document
from app.query import interpret_query
from app.query.interpreter import build_retrieval_query
from app.query.models import INTENT_EXPLANATION_LOOKUP
from app.retrieval import search_chunks
from app.retrieval.models import SearchResult
from app.structure.models import DocumentChunk


def _chunk(
    chunk_id: str,
    text: str,
    *,
    document_name: str = "doc.txt",
    start_line: int = 1,
    end_line: int | None = None,
    chunk_type: str = "paragraph",
    section_id: str | None = "sec-1",
    section_title: str | None = "Lineage",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_name=document_name,
        text=text,
        chunk_type=chunk_type,
        start_line=start_line,
        end_line=end_line or start_line,
        section_id=section_id,
        section_title=section_title,
    )


def test_needs_expansion_for_section_chunk() -> None:
    result = SearchResult(
        chunk_id="h1",
        document_name="doc.txt",
        text="SPDM Lineage on Runs",
        score=2.0,
        matched_terms=["lineage"],
        term_scores={"lineage": 1.0},
        start_line=3,
        end_line=3,
        section_title="SPDM Lineage on Runs",
        chunk_type="section",
        why_matched="test",
    )

    assert needs_context_expansion(result) is True


def test_expand_result_context_includes_following_paragraphs() -> None:
    chunks = [
        _chunk("h1", "SPDM Lineage on Runs", start_line=3, end_line=3, chunk_type="section"),
        _chunk(
            "p1",
            "Lineage is one of the most important concepts in SPDM workflows.",
            start_line=5,
            end_line=5,
        ),
        _chunk(
            "p2",
            "Lineage = history and traceability of something across a workflow.",
            start_line=7,
            end_line=7,
        ),
        _chunk(
            "p3",
            "Examples include which geometry was used and which dataset was used.",
            start_line=9,
            end_line=9,
        ),
    ]
    heading_result = SearchResult(
        chunk_id="h1",
        document_name="doc.txt",
        text="SPDM Lineage on Runs",
        score=2.0,
        matched_terms=["lineage"],
        term_scores={"lineage": 1.0},
        start_line=3,
        end_line=3,
        section_title="SPDM Lineage on Runs",
        chunk_type="section",
        why_matched="test",
        section_id="sec-1",
    )

    expanded = expand_result_context(heading_result, chunks)

    assert "history and traceability" in expanded.text
    assert "which geometry was used" in expanded.text
    assert expanded.start_line == 3
    assert expanded.end_line >= 7


def test_explanation_lookup_intent() -> None:
    intent = interpret_query("explain lineage")

    assert intent.intent_type == INTENT_EXPLANATION_LOOKUP
    assert "lineage" in [entity.lower() for entity in intent.entities]


def test_explanation_lookup_expands_retrieval_query() -> None:
    intent = interpret_query("explain lineage")
    retrieval_query = build_retrieval_query("explain lineage", intent)

    for term in ("meaning", "definition", "explanation", "concept"):
        assert term in retrieval_query


def test_explain_lineage_evidence_includes_explanation(tmp_path: Path) -> None:
    source = tmp_path / "lineage.txt"
    db_path = tmp_path / "tracedoc.db"
    source.write_text(
        "COMMON CAPABILITIES\n\n"
        "SPDM Lineage on Runs\n\n"
        "Lineage is one of the most important concepts in SPDM workflows.\n\n"
        "Lineage = history and traceability of something across a workflow.\n\n"
        "Examples include which geometry was used, which dataset was used, "
        "which solver version was applied.\n",
        encoding="utf-8",
    )
    processed = process_document(str(source), db_path=str(db_path))
    answer = ask_document(
        "explain lineage",
        processed.document_id,
        db_path=str(db_path),
    )

    assert answer.query_intent is not None
    assert answer.query_intent.intent_type == INTENT_EXPLANATION_LOOKUP
    assert answer.cards

    snippet = answer.cards[0].snippet.replace("[[", "").replace("]]", "").lower()
    assert "history and traceability" in snippet
    assert "geometry was used" in snippet or "dataset was used" in snippet
    assert snippet.strip() != "spdm lineage on runs"


def test_section_boost_prefers_explanatory_chunk() -> None:
    chunks = [
        _chunk(
            "h1",
            "Lineage Overview",
            start_line=1,
            chunk_type="section",
            section_id="sec-lineage",
            section_title="Lineage Overview",
        ),
        _chunk(
            "p1",
            "Lineage means history and traceability across engineering workflows.",
            start_line=3,
            chunk_type="paragraph",
            section_id="sec-lineage",
            section_title="Lineage Overview",
        ),
    ]
    index, stats = prepare_document_chunks(chunks)
    results = search_chunks(
        "explain lineage meaning definition",
        index,
        stats,
        top_k=2,
        intent_type=INTENT_EXPLANATION_LOOKUP,
        entities=["lineage"],
    )

    assert results
    top = results[0]
    assert "history and traceability" in top.text.lower()
