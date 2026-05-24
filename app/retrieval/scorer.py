"""BM25 scoring for lexical retrieval."""

from __future__ import annotations

from app.indexing.models import InvertedIndex


def score_chunk_bm25(
    query_terms: list[str],
    chunk_id: str,
    index: InvertedIndex,
    bm25_stats: dict,
    k1: float = 1.5,
    b: float = 0.75,
) -> tuple[float, dict[str, float]]:
    """
    Compute BM25 score for one chunk.

    Returns the total score and per-term contribution map. Terms that do
    not appear in the chunk receive a score of 0.
    """
    chunk_entry = index.chunk_statistics.get(chunk_id)
    if chunk_entry is None:
        return 0.0, {term: 0.0 for term in query_terms}

    chunk_lengths = bm25_stats.get("chunk_lengths", {})
    idf_values = bm25_stats.get("idf", {})
    avgdl = bm25_stats.get("avgdl", 0.0) or 0.0
    dl = float(chunk_lengths.get(chunk_id, chunk_entry.token_count))

    term_scores: dict[str, float] = {}
    total_score = 0.0

    for term in query_terms:
        term_frequency = chunk_entry.token_frequencies.get(term, 0)
        if term_frequency == 0:
            term_scores[term] = 0.0
            continue

        idf = idf_values.get(term, 0.0)
        length_norm = 1.0 - b + b * (dl / avgdl) if avgdl > 0 else 1.0
        numerator = term_frequency * (k1 + 1.0)
        denominator = term_frequency + k1 * length_norm
        contribution = idf * (numerator / denominator)
        term_scores[term] = contribution
        total_score += contribution

    return total_score, term_scores
