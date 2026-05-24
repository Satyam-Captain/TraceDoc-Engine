"""Data models for deterministic retrieval."""

from dataclasses import dataclass, field


@dataclass
class SearchQuery:
    """Prepared lexical search query."""

    raw_query: str
    normalized_terms: list[str]
    original_terms: list[str]


@dataclass
class SearchResult:
    """Ranked chunk match with explainable scoring metadata."""

    chunk_id: str
    document_name: str
    text: str
    score: float
    matched_terms: list[str]
    term_scores: dict[str, float]
    start_line: int
    end_line: int
    section_title: str | None
    chunk_type: str
    why_matched: str
    section_id: str | None = None
