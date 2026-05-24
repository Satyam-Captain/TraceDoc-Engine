"""Deterministic token normalization."""

from __future__ import annotations

import re

_SURROUNDING_PUNCTUATION = re.compile(r'^["\'`([{]+|["\'`)\]},.:;!?]+$')
_WHITESPACE = re.compile(r"\s+")


def normalize_token(token: str) -> str:
    """
    Normalize a token for indexing.

    Lowercases, trims whitespace, collapses repeated spaces, strips
    surrounding punctuation, and preserves internal hyphens.
    """
    normalized = _WHITESPACE.sub(" ", token.strip().lower())
    while normalized:
        updated = _SURROUNDING_PUNCTUATION.sub("", normalized)
        if updated == normalized:
            break
        normalized = updated
    return normalized
