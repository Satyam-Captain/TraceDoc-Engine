"""Whoosh BM25 chunk search."""

from __future__ import annotations

from pathlib import Path

import whoosh.index as whoosh_index
from whoosh.qparser import QueryParser

from app.indexing.models import ChunkIndexEntry
from app.retrieval.models import SearchResult
from app.retrieval.searcher import prepare_search_query
from app.retrieval.section_boost import apply_section_aware_boost


def _build_why_matched(matched_terms: list[str]) -> str:
    terms_label = ", ".join(matched_terms) if matched_terms else "none"
    return (
        f"Matched terms: {terms_label}. "
        "Ranked using deterministic Whoosh BM25 index."
    )


def _matched_terms_for_hit(query_terms: list[str], text: str) -> list[str]:
    lowered = text.lower()
    return sorted(term for term in query_terms if term in lowered)


def search_whoosh(
    index_path: Path,
    query: str,
    limit: int = 10,
    *,
    document_name: str = "",
    intent_type: str | None = None,
    entities: list[str] | None = None,
) -> list[SearchResult]:
    """
    Search a Whoosh index and return SearchResult rows.

    Returns an empty list when the index is missing, the query is empty,
    or no hits are found.
    """
    if limit <= 0:
        return []

    prepared = prepare_search_query(query)
    if not prepared.raw_query.strip() or not prepared.normalized_terms:
        return []

    index_dir = Path(index_path)
    if not index_dir.is_dir() or not whoosh_index.exists_in(index_dir):
        return []

    ix = whoosh_index.open_dir(str(index_dir))
    parser = QueryParser("text", schema=ix.schema)
    parsed = parser.parse(prepared.raw_query)

    results: list[SearchResult] = []
    with ix.searcher() as searcher:
        hits = searcher.search(parsed, limit=limit)
        for hit in hits:
            chunk_id = str(hit["chunk_id"])
            text = str(hit.get("text", ""))
            score = float(hit.score) if hit.score is not None else 0.0
            if score <= 0:
                continue

            section_title = hit.get("section_title") or None
            if section_title == "":
                section_title = None

            section_id = hit.get("section_id") or None
            if section_id == "":
                section_id = None

            chunk_entry = ChunkIndexEntry(
                chunk_id=chunk_id,
                document_name=str(hit.get("document_name") or document_name),
                chunk_type=str(hit.get("chunk_type") or "paragraph"),
                section_title=section_title,
                text=text,
                token_count=0,
                unique_token_count=0,
                normalized_text="",
                metadata={
                    "start_line": int(hit.get("start_line") or 0),
                    "end_line": int(hit.get("end_line") or 0),
                    "section_id": section_id,
                },
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

            matched_terms = _matched_terms_for_hit(prepared.normalized_terms, text)
            term_scores = {term: 1.0 for term in matched_terms}
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_name=chunk_entry.document_name,
                    text=text,
                    score=score,
                    matched_terms=matched_terms,
                    term_scores=term_scores,
                    start_line=int(chunk_entry.metadata.get("start_line", 0)),
                    end_line=int(chunk_entry.metadata.get("end_line", 0)),
                    section_title=section_title,
                    chunk_type=chunk_entry.chunk_type,
                    why_matched=_build_why_matched(matched_terms),
                    section_id=section_id,
                )
            )

    results.sort(key=lambda item: (-item.score, item.chunk_id))
    return results[:limit]
