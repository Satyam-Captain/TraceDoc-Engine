"""Deterministic section-level retrieval for broader-context questions."""

from __future__ import annotations

from typing import TypeAlias

from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize
from app.storage.models import StoredChunk, StoredSection

ChunkLike: TypeAlias = StoredChunk

_VARIANT_PAIRS = (
    ("architecture", "architectures"),
    ("capability", "capabilities"),
    ("pattern", "patterns"),
    ("section", "sections"),
)

_WEAK_WORDS = frozenset(
    {
        "what",
        "are",
        "different",
        "mentioned",
        "pdf",
        "document",
        "explain",
        "tell",
        "me",
        "the",
        "in",
        "of",
        "a",
        "an",
        "is",
        "was",
        "be",
    }
)


def _question_terms(question: str) -> set[str]:
    terms = {normalize_token(token) for token in tokenize(question)}
    return {term for term in terms if term}


def _expand_variants(terms: set[str]) -> set[str]:
    expanded = set(terms)
    for singular, plural in _VARIANT_PAIRS:
        if singular in terms:
            expanded.add(plural)
        if plural in terms:
            expanded.add(singular)
    return expanded


def _content_terms(question: str) -> set[str]:
    terms = _question_terms(question) - _WEAK_WORDS
    return _expand_variants(terms)


def score_section_relevance(question: str, section: StoredSection) -> float:
    """Score a section title against question terms (higher is better)."""
    query_terms = _content_terms(question)
    if not query_terms:
        return 0.0

    title_terms = _expand_variants(_question_terms(section.title))
    overlap = query_terms.intersection(title_terms)
    if not overlap:
        return 0.0

    score = float(len(overlap))
    normalized_title = " ".join(tokenize(section.title.lower()))
    normalized_question = " ".join(tokenize(question.lower()))
    if section.title.strip().lower() in question.strip().lower():
        score += 2.0
    if normalized_title and normalized_title in normalized_question:
        score += 1.5
    if title_terms and overlap == title_terms:
        score += 1.0
    return score


def find_relevant_sections(
    question: str,
    sections: list[StoredSection],
    top_k: int = 3,
) -> list[StoredSection]:
    """
    Rank sections by lexical overlap between question and section title.

    Ranking is deterministic: score descending, then start_line, then section_id.
    """
    if top_k <= 0 or not sections:
        return []

    scored: list[tuple[float, StoredSection]] = []
    for section in sections:
        score = score_section_relevance(question, section)
        if score > 0:
            scored.append((score, section))

    if not scored:
        return []

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].start_line,
            item[1].section_id,
        )
    )
    return [section for _, section in scored[:top_k]]


def collect_section_chunks(
    section: StoredSection,
    chunks: list[ChunkLike],
    max_chunks: int = 20,
) -> list[ChunkLike]:
    """
    Collect chunks whose line range falls inside the section line range.

    Chunks are returned in start_line order, capped at max_chunks.
    """
    if max_chunks <= 0:
        return []

    ordered = sorted(chunks, key=lambda item: (item.start_line, item.chunk_id))
    selected = [
        chunk
        for chunk in ordered
        if chunk.start_line >= section.start_line and chunk.end_line <= section.end_line
    ]
    return selected[:max_chunks]
