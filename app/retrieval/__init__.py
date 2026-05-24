"""Deterministic lexical retrieval."""

from app.retrieval.models import SearchQuery, SearchResult
from app.retrieval.scorer import score_chunk_bm25
from app.retrieval.section_searcher import (
    collect_section_chunks,
    derive_sections_from_chunks,
    extract_topic_terms,
    find_relevant_sections,
    score_section_relevance,
)
from app.retrieval.section_trigger import should_use_section_retrieval
from app.retrieval.searcher import prepare_search_query, search_chunks

__all__ = [
    "SearchQuery",
    "SearchResult",
    "collect_section_chunks",
    "derive_sections_from_chunks",
    "extract_topic_terms",
    "find_relevant_sections",
    "score_section_relevance",
    "should_use_section_retrieval",
    "prepare_search_query",
    "score_chunk_bm25",
    "search_chunks",
]
