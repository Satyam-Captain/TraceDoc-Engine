"""Section-title-aware score adjustments for lexical retrieval."""

from __future__ import annotations

from app.indexing.models import ChunkIndexEntry
from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize
from app.query.models import INTENT_EXPLANATION_LOOKUP

SECTION_TITLE_MATCH_BOOST = 1.35
EXPLANATORY_BODY_BOOST = 1.2
HEADING_ONLY_EXPLANATION_FACTOR = 0.92


def _normalized_title_tokens(section_title: str) -> list[str]:
    tokens = tokenize(section_title)
    return [term for term in (normalize_token(t) for t in tokens) if term]


def section_title_matches_terms(
    section_title: str | None,
    query_terms: list[str],
    entities: list[str] | None = None,
) -> bool:
    """True when any query term or entity appears in the section title."""
    if not section_title:
        return False
    title_tokens = set(_normalized_title_tokens(section_title))
    if not title_tokens:
        return False

    for term in query_terms:
        if term in title_tokens:
            return True

    for entity in entities or []:
        entity_tokens = [
            t for t in (normalize_token(token) for token in tokenize(entity)) if t
        ]
        if entity_tokens and all(token in title_tokens for token in entity_tokens):
            return True
        for token in entity_tokens:
            if token in title_tokens:
                return True
    return False


def apply_section_aware_boost(
    score: float,
    chunk_entry: ChunkIndexEntry,
    query_terms: list[str],
    *,
    intent_type: str | None = None,
    entities: list[str] | None = None,
) -> float:
    """
    Boost chunks in sections whose titles match the query.

    Paragraph and overflow chunks receive an extra boost so explanatory
    body text ranks above heading-only section chunks for explanation queries.
    """
    if score <= 0:
        return score

    section_title = chunk_entry.section_title
    if not section_title_matches_terms(section_title, query_terms, entities):
        return score

    chunk_type = chunk_entry.chunk_type or ""

    if chunk_type in ("paragraph", "overflow"):
        return score * SECTION_TITLE_MATCH_BOOST * EXPLANATORY_BODY_BOOST

    if chunk_type == "section" and intent_type == INTENT_EXPLANATION_LOOKUP:
        return score * HEADING_ONLY_EXPLANATION_FACTOR

    return score * SECTION_TITLE_MATCH_BOOST
