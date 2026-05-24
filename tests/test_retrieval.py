"""Tests for deterministic BM25 retrieval."""

from __future__ import annotations

from app.indexing import prepare_document_chunks
from app.retrieval import prepare_search_query, score_chunk_bm25, search_chunks
from app.structure.models import DocumentChunk


def _chunk(
    chunk_id: str,
    text: str,
    *,
    document_name: str = "alpha.txt",
    start_line: int = 1,
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_name=document_name,
        text=text,
        chunk_type="paragraph",
        start_line=start_line,
        end_line=start_line,
    )


def _build_index(chunks: list[DocumentChunk]):
    return prepare_document_chunks(chunks)


def test_query_preparation_removes_stopwords() -> None:
    prepared = prepare_search_query("the hpc6 memory")

    assert "the" not in prepared.normalized_terms
    assert prepared.normalized_terms == ["hpc6", "memory"]


def test_query_preparation_preserves_identifiers() -> None:
    prepared = prepare_search_query("REQ-001 ISO27001")

    assert "req-001" in prepared.normalized_terms
    assert "iso27001" in prepared.normalized_terms


def test_query_preparation_fallback_when_only_stopwords() -> None:
    prepared = prepare_search_query("the and of")

    assert prepared.normalized_terms == ["the", "and", "of"]


def test_bm25_scoring_returns_positive_score_for_matching_chunk() -> None:
    chunks = [_chunk("c1", "hpc6 memory configuration")]
    index, stats = _build_index(chunks)

    score, term_scores = score_chunk_bm25(["hpc6", "memory"], "c1", index, stats)

    assert score > 0
    assert term_scores["hpc6"] > 0
    assert term_scores["memory"] > 0


def test_non_matching_chunk_score_is_zero() -> None:
    chunks = [_chunk("c1", "alpha beta gamma")]
    index, stats = _build_index(chunks)

    score, term_scores = score_chunk_bm25(["hpc6"], "c1", index, stats)

    assert score == 0
    assert term_scores["hpc6"] == 0


def test_search_returns_ranked_results() -> None:
    chunks = [
        _chunk("c1", "hpc6 memory configuration", start_line=1),
        _chunk("c2", "network storage overview", start_line=2),
        _chunk("c3", "hpc6 memory tuning guide", start_line=3),
    ]
    index, stats = _build_index(chunks)

    results = search_chunks("hpc6 memory", index, stats, top_k=3)

    assert len(results) == 2
    assert results[0].score >= results[1].score
    assert {result.chunk_id for result in results} == {"c1", "c3"}


def test_top_k_is_respected() -> None:
    chunks = [
        _chunk("c1", "alpha beta"),
        _chunk("c2", "alpha gamma"),
        _chunk("c3", "alpha delta"),
    ]
    index, stats = _build_index(chunks)

    results = search_chunks("alpha", index, stats, top_k=2)

    assert len(results) == 2


def test_empty_query_returns_no_results() -> None:
    chunks = [_chunk("c1", "alpha beta")]
    index, stats = _build_index(chunks)

    assert search_chunks("", index, stats) == []
    assert search_chunks("   ", index, stats) == []


def test_no_matching_terms_returns_no_results() -> None:
    chunks = [_chunk("c1", "alpha beta")]
    index, stats = _build_index(chunks)

    assert search_chunks("zzzz-unknown", index, stats) == []


def test_empty_index_returns_no_results() -> None:
    index, stats = _build_index([])

    assert search_chunks("alpha", index, stats) == []


def test_top_k_zero_returns_no_results() -> None:
    chunks = [_chunk("c1", "alpha beta")]
    index, stats = _build_index(chunks)

    assert search_chunks("alpha", index, stats, top_k=0) == []


def test_deterministic_tie_breaking() -> None:
    chunks = [
        _chunk("c1", "alpha beta", document_name="b-doc.txt", start_line=2),
        _chunk("c2", "alpha beta", document_name="a-doc.txt", start_line=5),
    ]
    index, stats = _build_index(chunks)

    results = search_chunks("alpha beta", index, stats, top_k=2)

    assert results[0].document_name == "a-doc.txt"
    assert results[1].document_name == "b-doc.txt"


def test_why_matched_is_populated() -> None:
    chunks = [_chunk("c1", "hpc6 memory configuration")]
    index, stats = _build_index(chunks)

    results = search_chunks("hpc6 memory", index, stats, top_k=1)

    assert "Matched terms:" in results[0].why_matched
    assert "deterministic BM25" in results[0].why_matched


def test_matched_terms_are_populated() -> None:
    chunks = [_chunk("c1", "hpc6 memory configuration")]
    index, stats = _build_index(chunks)

    results = search_chunks("hpc6 memory", index, stats, top_k=1)

    assert results[0].matched_terms == ["hpc6", "memory"]


def test_original_chunk_text_is_returned() -> None:
    original = "HPC6 memory configuration for cluster A."
    chunks = [_chunk("c1", original)]
    index, stats = _build_index(chunks)

    results = search_chunks("hpc6", index, stats, top_k=1)

    assert results[0].text == original
