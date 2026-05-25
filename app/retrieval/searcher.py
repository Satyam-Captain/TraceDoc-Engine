"""Deterministic chunk search over an inverted index."""

from __future__ import annotations

from pathlib import Path

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


def merge_retrieval_results(
    *result_lists: list[SearchResult],
    top_k: int,
) -> list[SearchResult]:
    """
    Merge ranked lists by max score per chunk_id; tie-break by chunk_id ascending.
    """
    if top_k <= 0:
        return []

    merged: dict[str, SearchResult] = {}
    for results in result_lists:
        for result in results:
            existing = merged.get(result.chunk_id)
            if existing is None:
                merged[result.chunk_id] = result
                continue
            if result.score > existing.score:
                merged[result.chunk_id] = result
            elif result.score == existing.score and result.chunk_id < existing.chunk_id:
                merged[result.chunk_id] = result

    ordered = sorted(merged.values(), key=lambda item: (-item.score, item.chunk_id))
    return ordered[:top_k]


def search_chunks_for_document(
    query: str,
    index: InvertedIndex,
    bm25_stats: dict,
    *,
    document_id: int,
    top_k: int = 5,
    retrieval_mode: str | None = None,
    intent_type: str | None = None,
    entities: list[str] | None = None,
    whoosh_index_path: Path | None = None,
) -> list[SearchResult]:
    """
    Search chunks using TRACEDOC_RETRIEVAL (sqlite, whoosh, or hybrid).

    Falls back to SQLite BM25 when mode is whoosh/hybrid but the Whoosh index
    is missing or returns no hits.
    """
    from app.retrieval.whoosh_index import (
        get_retrieval_mode,
        whoosh_index_dir as resolve_whoosh_dir,
        whoosh_index_exists,
    )
    from app.retrieval.whoosh_searcher import search_whoosh

    mode = (retrieval_mode or get_retrieval_mode()).lower()
    sqlite_results = search_chunks(
        query,
        index,
        bm25_stats,
        top_k=top_k,
        intent_type=intent_type,
        entities=entities,
    )

    if mode == "sqlite":
        return sqlite_results

    index_path = whoosh_index_path or resolve_whoosh_dir(document_id)
    if not whoosh_index_exists(index_path):
        return sqlite_results

    document_name = ""
    if index.chunk_statistics:
        first = next(iter(index.chunk_statistics.values()))
        document_name = first.document_name

    whoosh_results = search_whoosh(
        index_path,
        query,
        limit=max(top_k, top_k * 2),
        document_name=document_name,
        intent_type=intent_type,
        entities=entities,
    )

    if mode == "whoosh":
        return whoosh_results[:top_k] if whoosh_results else sqlite_results

    return merge_retrieval_results(sqlite_results, whoosh_results, top_k=top_k)
