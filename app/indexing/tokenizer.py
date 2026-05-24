"""Deterministic tokenization without NLP libraries."""

from __future__ import annotations

import re

# Requirement-style identifiers and general lexical tokens.
_TOKEN_PATTERN = re.compile(
    r"[A-Za-z]{2,}-\d+"  # REQ-001
    r"|[A-Za-z]{2,}\d+[A-Za-z0-9]*"  # HPC6, ISO27001
    r"|\d+(?:\.\d+)?"  # numbers
    r"|[A-Za-z]+"  # words
)


def tokenize(text: str) -> list[str]:
    """
    Split text into lowercase tokens.

    Splits on whitespace and punctuation while preserving numbers and
    requirement-style identifiers (for example REQ-001, HPC6, ISO27001).
    """
    if not text:
        return []

    tokens = [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text)]
    return [token for token in tokens if token]
