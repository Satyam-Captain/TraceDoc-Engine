"""Deterministic query intent rules."""

from __future__ import annotations

import re

from app.query.models import (
    INTENT_COMPARISON,
    INTENT_DEFINITION_LOOKUP,
    INTENT_EXPLANATION_LOOKUP,
    INTENT_GENERAL_SEARCH,
    INTENT_LIST_REQUEST,
    INTENT_REQUIREMENT_REFERENCE,
    INTENT_TABLE_LOOKUP,
    INTENT_WHERE_MENTIONED,
)

_REQUIREMENT_ID = re.compile(r"\b[A-Za-z]{2,}-\d+\b", re.IGNORECASE)
_QUOTED_ENTITY = re.compile(r'"([^"]+)"|\'([^\']+)\'')

_EXPLANATION_PATTERNS = (
    re.compile(r"^\s*explain\s+(.+?)\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*what\s+does\s+(.+?)\s+mean\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*describe\s+(.+?)\??\s*$", re.IGNORECASE),
)

_DEFINITION_PATTERNS = (
    re.compile(r"^\s*what\s+is\s+(.+?)\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*define\s+(.+?)\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*meaning\s+of\s+(.+?)\??\s*$", re.IGNORECASE),
)

_WHERE_PATTERNS = (
    re.compile(r"\bwhere\s+is\b.+\bmentioned\b", re.IGNORECASE),
    re.compile(r"\bwhere\s+.+\bmentioned\b", re.IGNORECASE),
    re.compile(r"\bfind\b.+\bmentions?\b", re.IGNORECASE),
    re.compile(r"\bshow\s+mentions?\s+of\b", re.IGNORECASE),
    re.compile(r"\bwhere\s+is\b", re.IGNORECASE),
)

_LIST_PATTERNS = (
    re.compile(r"^\s*list\s+all\b", re.IGNORECASE),
    re.compile(r"^\s*show\s+all\b", re.IGNORECASE),
    re.compile(r"\blist\s+all\b", re.IGNORECASE),
    re.compile(r"\bshow\s+all\b", re.IGNORECASE),
)

_COMPARISON_PATTERNS = (
    re.compile(r"\bcompare\b", re.IGNORECASE),
    re.compile(r"\bdifference\s+between\b", re.IGNORECASE),
    re.compile(r"\bvs\.?\b", re.IGNORECASE),
    re.compile(r"\bversus\b", re.IGNORECASE),
)

_TABLE_PATTERNS = (
    re.compile(r"\btable\b", re.IGNORECASE),
    re.compile(r"\brow\b", re.IGNORECASE),
    re.compile(r"\bcolumn\b", re.IGNORECASE),
)

_REQUIREMENT_PATTERNS = (
    re.compile(r"\brequirement\b", re.IGNORECASE),
    re.compile(r"\bshall\b", re.IGNORECASE),
    re.compile(r"\bmust\b", re.IGNORECASE),
)


def extract_entities(question: str) -> list[str]:
    """Extract simple entities from a question string."""
    entities: list[str] = []

    for match in _REQUIREMENT_ID.finditer(question):
        entities.append(match.group(0))

    for match in _QUOTED_ENTITY.finditer(question):
        value = match.group(1) or match.group(2)
        if value:
            entities.append(value.strip())

    for pattern in _EXPLANATION_PATTERNS:
        match = pattern.match(question)
        if match:
            subject = match.group(1).strip(" ?.")
            if subject:
                entities.append(subject)

    for pattern in _DEFINITION_PATTERNS:
        match = pattern.match(question)
        if match:
            subject = match.group(1).strip(" ?.")
            if subject:
                entities.append(subject)

    seen: set[str] = set()
    unique: list[str] = []
    for entity in entities:
        key = entity.lower()
        if key not in seen:
            seen.add(key)
            unique.append(entity)
    return unique


def extract_comparison_terms(question: str) -> list[str]:
    """Extract simple comparison operands from a question."""
    between_match = re.search(
        r"difference\s+between\s+(.+?)\s+and\s+(.+?)\??\s*$",
        question,
        re.IGNORECASE,
    )
    if between_match:
        return [between_match.group(1).strip(), between_match.group(2).strip()]

    compare_match = re.search(
        r"compare\s+(.+?)\s+and\s+(.+?)\??\s*$",
        question,
        re.IGNORECASE,
    )
    if compare_match:
        return [compare_match.group(1).strip(), compare_match.group(2).strip()]

    vs_match = re.search(r"(.+?)\s+vs\.?\s+(.+?)\??\s*$", question, re.IGNORECASE)
    if vs_match:
        return [vs_match.group(1).strip(), vs_match.group(2).strip()]

    return []


def classify_intent(question: str, entities: list[str]) -> tuple[str, str, dict]:
    """
    Classify question intent using ordered deterministic rules.

    Returns intent_type, explanation, and filters.
    """
    stripped = question.strip()
    if not stripped:
        return (
            INTENT_GENERAL_SEARCH,
            "Empty question; using general search intent.",
            {},
        )

    requirement_ids = [
        entity for entity in entities if _REQUIREMENT_ID.fullmatch(entity)
    ]
    if requirement_ids or any(pattern.search(stripped) for pattern in _REQUIREMENT_PATTERNS):
        return (
            INTENT_REQUIREMENT_REFERENCE,
            "Requirement reference intent detected from requirement language or IDs.",
            {"requirement_ids": requirement_ids},
        )

    if any(pattern.search(stripped) for pattern in _COMPARISON_PATTERNS):
        comparison_terms = extract_comparison_terms(stripped)
        return (
            INTENT_COMPARISON,
            "Comparison intent detected from compare/difference/vs language.",
            {"comparison_terms": comparison_terms},
        )

    if any(pattern.search(stripped) for pattern in _LIST_PATTERNS):
        return (
            INTENT_LIST_REQUEST,
            "List request intent detected from list/show-all phrasing.",
            {},
        )

    for pattern in _EXPLANATION_PATTERNS:
        if pattern.match(stripped):
            return (
                INTENT_EXPLANATION_LOOKUP,
                "Explanation lookup intent detected from explain/describe/what-does-mean phrasing.",
                {},
            )

    for pattern in _DEFINITION_PATTERNS:
        if pattern.match(stripped):
            return (
                INTENT_DEFINITION_LOOKUP,
                "Definition lookup intent detected from what-is/define/meaning phrasing.",
                {},
            )

    if any(pattern.search(stripped) for pattern in _WHERE_PATTERNS):
        return (
            INTENT_WHERE_MENTIONED,
            "Where-mentioned intent detected from find/mention location phrasing.",
            {},
        )

    if any(pattern.search(stripped) for pattern in _TABLE_PATTERNS):
        return (
            INTENT_TABLE_LOOKUP,
            "Table lookup intent detected from table/row/column language.",
            {},
        )

    return (
        INTENT_GENERAL_SEARCH,
        "General search intent used as deterministic fallback.",
        {},
    )
