"""Deterministic chunk search over an inverted index."""

from __future__ import annotations

from app.indexing.models import InvertedIndex
from app.indexing.normalizer import normalize_token
from app.indexing.stopwords import is_stopword
from app.indexing.tokenizer import tokenize
from app.retrieval.models import SearchQuery, SearchResult
from app.retrieval.scorer import score_chunk_bm25
from app.retrieval.section_boost import apply_section_aware_boost


def prepare_search_query(query: str) -> SearchQuery:
    """
    Tokenize and normalize a user query for lexical retrieval.

    Stopwords are removed by default. If that would remove every term,
    the query falls back to all normalized non-empty tokens.
    """
    raw_query = query or ""
    original_terms = tokenize(raw_query)
    normalized_all = [normalize_token(term) for term in original_terms]
    normalized_all = [term for term in normalized_all if term]

    normalized_terms = [term for term in normalized_all if not is_stopword(term)]
    if not normalized_terms:
        normalized_terms = list(normalized_all)

    return SearchQuery(
        raw_query=raw_query,
        normalized_terms=normalized_terms,
        original_terms=original_terms,
    )


def _build_why_matched(matched_terms: list[str]) -> str:
    terms_label = ", ".join(matched_terms) if matched_terms else "none"
    return (
        f"Matched terms: {terms_label}. "
        "Ranked using deterministic BM25 over lexical index."
    )


def _candidate_chunk_ids(query_terms: list[str], index: InvertedIndex) -> set[str]:
    candidates: set[str] = set()
    for term in query_terms:
        postings = index.term_to_chunks.get(term)
        if postings:
            candidates.update(postings.keys())
    return candidates


def search_chunks(
    query: str,
    index: InvertedIndex,
    bm25_stats: dict,
    top_k: int = 5,
    *,
    intent_type: str | None = None,
    entities: list[str] | None = None,
) -> list[SearchResult]:
    """
    Search indexed chunks with deterministic BM25 ranking.

    Returns an empty list for empty queries, non-positive top_k values,
    empty indexes, or queries with no matching indexed terms.
    """
    if top_k <= 0:
        return []

    prepared = prepare_search_query(query)
    if not prepared.raw_query.strip() or not prepared.normalized_terms:
        return []

    if index.total_chunk_count == 0:
        return []

    candidates = _candidate_chunk_ids(prepared.normalized_terms, index)
    if not candidates:
        return []

    k1 = float(bm25_stats.get("bm25_k1", 1.5))
    b = float(bm25_stats.get("bm25_b", 0.75))

    results: list[SearchResult] = []
    for chunk_id in candidates:
        chunk_entry = index.chunk_statistics[chunk_id]
        score, term_scores = score_chunk_bm25(
            prepared.normalized_terms,
            chunk_id,
            index,
            bm25_stats,
            k1=k1,
            b=b,
        )
        score = apply_section_aware_boost(
            score,
            chunk_entry,
            prepared.normalized_terms,
            intent_type=intent_type,
            entities=entities,
        )
        if score <= 0:
            continue

        matched_terms = sorted(
            term for term, term_score in term_scores.items() if term_score > 0
        )
        metadata = chunk_entry.metadata
        results.append(
            SearchResult(
                chunk_id=chunk_id,
                document_name=chunk_entry.document_name,
                text=chunk_entry.text,
                score=score,
                matched_terms=matched_terms,
                term_scores=term_scores,
                start_line=int(metadata.get("start_line", 0)),
                end_line=int(metadata.get("end_line", 0)),
                section_title=chunk_entry.section_title,
                chunk_type=chunk_entry.chunk_type,
                why_matched=_build_why_matched(matched_terms),
                section_id=metadata.get("section_id"),
            )
        )

    results.sort(
        key=lambda item: (
            -item.score,
            item.document_name,
            item.start_line,
            item.chunk_id,
        )
    )
    return results[:top_k]
