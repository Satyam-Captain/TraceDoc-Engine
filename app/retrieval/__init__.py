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
from app.retrieval.searcher import (
    merge_retrieval_results,
    prepare_search_query,
    search_chunks,
    search_chunks_for_document,
)
from app.retrieval.whoosh_index import (
    build_whoosh_index,
    get_retrieval_mode,
    should_build_whoosh_index,
    whoosh_index_dir,
)
from app.retrieval.whoosh_searcher import search_whoosh

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
    "search_chunks_for_document",
    "merge_retrieval_results",
    "build_whoosh_index",
    "get_retrieval_mode",
    "should_build_whoosh_index",
    "whoosh_index_dir",
    "search_whoosh",
]
