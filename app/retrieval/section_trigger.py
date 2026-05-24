"""Deterministic rules for when to use section-level retrieval."""

from __future__ import annotations

from app.query.models import (
    INTENT_COMPARISON,
    INTENT_DEFINITION_LOOKUP,
    INTENT_EXPLANATION_LOOKUP,
    INTENT_LIST_REQUEST,
    INTENT_WHERE_MENTIONED,
)

_ENUMERATION_PHRASES = (
    "different",
    "types of",
    "type of",
    "kinds of",
    "kind of",
    "what are",
    "list ",
    "mentioned",
    "explain",
    "meaning",
    "define",
    "architecture",
    "architectures",
    "design pattern",
    "design patterns",
    "implementation pattern",
    "architcture",
    "architecure",
    "capability",
    "capabilities",
    "lineage",
)

_INTENT_TYPES_USING_SECTIONS = frozenset(
    {
        INTENT_LIST_REQUEST,
        INTENT_DEFINITION_LOOKUP,
        INTENT_WHERE_MENTIONED,
        INTENT_COMPARISON,
        INTENT_EXPLANATION_LOOKUP,
    }
)


def should_use_section_retrieval(question: str, intent_type: str) -> bool:
    """
    Return True when a question needs full-section context instead of top chunks.

    Applies to list/enumeration, explanation, and definition-style questions even
    when intent classification falls back to GENERAL_SEARCH.
    """
    stripped = question.strip()
    if not stripped:
        return False

    if intent_type in _INTENT_TYPES_USING_SECTIONS:
        return True

    lower = stripped.lower()
    if lower.startswith("what are") or lower.startswith("list"):
        return True

    return any(phrase in lower for phrase in _ENUMERATION_PHRASES)
