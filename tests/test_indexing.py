"""Tests for lexical indexing and BM25 preparation."""

from __future__ import annotations

from app.indexing import (
    build_inverted_index,
    compute_bm25_statistics,
    is_stopword,
    normalize_token,
    prepare_document_chunks,
    tokenize,
)
from app.indexing.stopwords import STOPWORDS
from app.structure.models import DocumentChunk


def _chunk(
    chunk_id: str,
    text: str,
    *,
    section_title: str | None = None,
    document_name: str = "spec.txt",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_name=document_name,
        text=text,
        chunk_type="paragraph",
        start_line=1,
        end_line=1,
        section_title=section_title,
    )


def test_tokenizer_behavior() -> None:
    tokens = tokenize("HPC6 cluster supports REQ-001 and ISO27001 controls.")
    assert tokens == ["hpc6", "cluster", "supports", "req-001", "and", "iso27001", "controls"]


def test_normalization() -> None:
    assert normalize_token("HPC6,") == "hpc6"
    assert normalize_token("(REQ-001)") == "req-001"
    assert normalize_token("  Mixed   Case  ") == "mixed case"


def test_stopword_detection() -> None:
    assert is_stopword("the")
    assert is_stopword("and")
    assert "the" in STOPWORDS
    assert not is_stopword("hpc6")


def test_requirement_id_preservation() -> None:
    tokens = tokenize("Requirement REQ-001 applies.")
    assert "req-001" in tokens


def test_deterministic_token_output() -> None:
    text = "Deterministic token output for REQ-001."
    first = tokenize(text)
    second = tokenize(text)
    assert first == second


def test_inverted_index_creation() -> None:
    chunks = [
        _chunk("c1", "alpha beta gamma"),
        _chunk("c2", "beta delta"),
    ]
    index = build_inverted_index(chunks)

    assert index.total_chunk_count == 2
    assert index.document_count == 1
    assert "beta" in index.term_to_chunks
    assert set(index.term_to_chunks["beta"].keys()) == {"c1", "c2"}


def test_term_frequency_correctness() -> None:
    chunks = [_chunk("c1", "alpha alpha beta")]
    index = build_inverted_index(chunks)

    assert index.term_to_chunks["alpha"]["c1"]["frequency"] == 2
    assert index.term_to_chunks["beta"]["c1"]["frequency"] == 1


def test_token_position_tracking() -> None:
    chunks = [_chunk("c1", "alpha beta alpha")]
    index = build_inverted_index(chunks)

    assert index.term_to_chunks["alpha"]["c1"]["positions"] == [0, 2]


def test_bm25_statistics_generation() -> None:
    chunks = [
        _chunk("c1", "alpha beta"),
        _chunk("c2", "beta gamma"),
    ]
    index, stats = prepare_document_chunks(chunks)

    assert stats["document_count"] == 2
    assert stats["avgdl"] == index.average_chunk_length
    assert stats["df"]["beta"] == 2
    assert stats["idf"]["beta"] < stats["idf"]["alpha"]
    assert "searchable_term_map" in stats


def test_average_chunk_length_calculation() -> None:
    chunks = [
        _chunk("c1", "one two three"),
        _chunk("c2", "four five"),
    ]
    index = build_inverted_index(chunks)

    assert index.average_chunk_length == 2.5


def test_vocabulary_generation() -> None:
    chunks = [_chunk("c1", "alpha beta"), _chunk("c2", "gamma")]
    index, stats = prepare_document_chunks(chunks)

    assert index.vocabulary_size == 3
    assert stats["vocabulary_size"] == 3
    assert stats["vocabulary"] == ["alpha", "beta", "gamma"]


def test_stopword_filtering_is_configurable() -> None:
    chunks = [_chunk("c1", "the alpha and beta")]
    with_stopwords = build_inverted_index(chunks, remove_stopwords=False)
    without_stopwords = build_inverted_index(chunks, remove_stopwords=True)

    assert "the" in with_stopwords.term_to_chunks
    assert "the" not in without_stopwords.term_to_chunks
    assert "alpha" in without_stopwords.term_to_chunks


def test_section_title_tokens_indexed() -> None:
    chunks = [_chunk("c1", "body text", section_title="Security Controls")]
    index = build_inverted_index(chunks)

    assert "security" in index.term_to_chunks
    assert "controls" in index.term_to_chunks


def test_field_weights_prepared() -> None:
    chunks = [_chunk("c1", "alpha beta")]
    index, stats = prepare_document_chunks(chunks)

    assert index.field_weights["text"] == 1.0
    assert stats["field_weights"]["section_title"] == 1.5


def test_empty_chunk_handling() -> None:
    chunks = [_chunk("empty", "   "), _chunk("valid", "alpha beta")]
    index, stats = prepare_document_chunks(chunks)

    assert index.total_chunk_count == 1
    assert stats["document_count"] == 1
    assert "alpha" in index.term_to_chunks
