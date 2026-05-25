"""Tests for Whoosh BM25 retrieval (v2 stack)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("whoosh")

from app.indexing import prepare_document_chunks
from app.retrieval.searcher import merge_retrieval_results, search_chunks_for_document
from app.retrieval.whoosh_index import build_whoosh_index, whoosh_index_dir
from app.retrieval.whoosh_searcher import search_whoosh
from app.structure.models import DocumentChunk


def _chunk(
    chunk_id: str,
    text: str,
    *,
    start_line: int = 1,
    section_id: str | None = None,
    section_title: str | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_name="policy.txt",
        text=text,
        chunk_type="paragraph",
        start_line=start_line,
        end_line=start_line,
        section_id=section_id,
        section_title=section_title,
    )


@pytest.fixture
def whoosh_fixture(tmp_path: Path) -> tuple[Path, list[DocumentChunk], object, dict]:
    chunks = [
        _chunk(
            "c1",
            "HPC6 cluster memory requirements are documented for operators.",
            start_line=1,
            section_id="sec-policy",
            section_title="Security Policy",
        ),
        _chunk(
            "c2",
            "REQ-001 defines baseline security controls for batch jobs.",
            start_line=2,
            section_id="sec-req",
            section_title="Requirements",
        ),
    ]
    index, stats = prepare_document_chunks(chunks)
    index_path = build_whoosh_index(42, chunks, tmp_path / "whoosh" / "42")
    return index_path, chunks, index, stats


def test_build_whoosh_index_and_search(whoosh_fixture: tuple) -> None:
    index_path, _chunks, _index, _stats = whoosh_fixture

    results = search_whoosh(index_path, "hpc6 memory", limit=5)

    assert results
    assert results[0].chunk_id == "c1"
    assert "hpc6" in results[0].matched_terms
    assert "Whoosh BM25" in results[0].why_matched


def test_search_chunks_for_document_whoosh_mode(
    whoosh_fixture: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_path, _chunks, index, stats = whoosh_fixture
    monkeypatch.setenv("TRACEDOC_RETRIEVAL", "whoosh")

    results = search_chunks_for_document(
        "hpc6 memory",
        index,
        stats,
        document_id=42,
        top_k=3,
        whoosh_index_path=index_path,
    )

    assert results
    assert results[0].chunk_id == "c1"
    assert "Whoosh BM25" in results[0].why_matched


def test_hybrid_merge_uses_max_score_per_chunk() -> None:
    from app.retrieval.models import SearchResult

    sqlite_hit = SearchResult(
        chunk_id="c1",
        document_name="policy.txt",
        text="alpha",
        score=1.0,
        matched_terms=["alpha"],
        term_scores={"alpha": 1.0},
        start_line=1,
        end_line=1,
        section_title=None,
        chunk_type="paragraph",
        why_matched="sqlite",
    )
    whoosh_hit = SearchResult(
        chunk_id="c1",
        document_name="policy.txt",
        text="alpha",
        score=2.5,
        matched_terms=["alpha"],
        term_scores={"alpha": 1.0},
        start_line=1,
        end_line=1,
        section_title=None,
        chunk_type="paragraph",
        why_matched="whoosh",
    )
    other = SearchResult(
        chunk_id="c2",
        document_name="policy.txt",
        text="beta",
        score=1.5,
        matched_terms=["beta"],
        term_scores={"beta": 1.0},
        start_line=2,
        end_line=2,
        section_title=None,
        chunk_type="paragraph",
        why_matched="whoosh",
    )

    merged = merge_retrieval_results([sqlite_hit], [whoosh_hit, other], top_k=2)

    assert [item.chunk_id for item in merged] == ["c1", "c2"]
    assert merged[0].score == 2.5


def test_whoosh_missing_index_falls_back_to_sqlite(
    whoosh_fixture: tuple,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _index_path, _chunks, index, stats = whoosh_fixture
    monkeypatch.setenv("TRACEDOC_RETRIEVAL", "whoosh")

    results = search_chunks_for_document(
        "hpc6 memory",
        index,
        stats,
        document_id=9999,
        top_k=3,
        whoosh_index_path=tmp_path / "no-whoosh" / "9999",
    )

    assert results
    assert results[0].chunk_id == "c1"
    assert "lexical index" in results[0].why_matched


def test_whoosh_index_dir_helper() -> None:
    path = whoosh_index_dir(7, base_dir=Path("/tmp/index"))
    assert path == Path("/tmp/index/7")
