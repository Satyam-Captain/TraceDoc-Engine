"""BM25 statistic preparation (no retrieval execution)."""

from __future__ import annotations

import math

from app.indexing.models import InvertedIndex

BM25_K1 = 1.5
BM25_B = 0.75


def _compute_idf(document_frequency: int, document_count: int) -> float:
    """Robertson/Spark Jones IDF used by BM25."""
    return math.log(
        ((document_count - document_frequency + 0.5) / (document_frequency + 0.5))
        + 1.0
    )


def compute_bm25_statistics(index: InvertedIndex) -> dict:
    """
    Prepare BM25 statistics from an inverted index.

    Returns document frequency, inverse document frequency, average chunk
    length, and per-chunk lengths. Retrieval is implemented in a later step.
    """
    document_count = index.total_chunk_count
    chunk_lengths = {
        chunk_id: entry.token_count
        for chunk_id, entry in index.chunk_statistics.items()
    }
    avgdl = index.average_chunk_length

    df: dict[str, int] = {}
    idf: dict[str, float] = {}

    for term, postings in index.term_to_chunks.items():
        term_df = len(postings)
        df[term] = term_df
        idf[term] = _compute_idf(term_df, document_count) if document_count else 0.0

    vocabulary = sorted(index.term_to_chunks.keys())

    return {
        "df": df,
        "idf": idf,
        "avgdl": avgdl,
        "chunk_lengths": chunk_lengths,
        "document_count": document_count,
        "corpus_document_count": index.document_count,
        "vocabulary": vocabulary,
        "vocabulary_size": len(vocabulary),
        "field_weights": dict(index.field_weights),
        "bm25_k1": BM25_K1,
        "bm25_b": BM25_B,
    }
