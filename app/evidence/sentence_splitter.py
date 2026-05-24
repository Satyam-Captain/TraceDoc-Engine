"""Deterministic sentence segmentation without NLP libraries."""

from __future__ import annotations

import re

# Common abbreviations that should not end a sentence when followed by a period.
_ABBREVIATIONS: tuple[str, ...] = (
    "e.g.",
    "i.e.",
    "etc.",
    "al.",
    "vs.",
    "Dr.",
    "Mr.",
    "Mrs.",
    "Ms.",
    "Prof.",
    "Fig.",
    "No.",
    "Vol.",
    "approx.",
    "dept.",
    "Inc.",
    "Ltd.",
    "U.S.",
    "U.K.",
)

_PLACEHOLDER_PREFIX = "\x00ABBREV"
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _protect_abbreviations(text: str) -> tuple[str, dict[str, str]]:
    protected = text
    placeholders: dict[str, str] = {}
    for index, abbrev in enumerate(_ABBREVIATIONS):
        token = f"{_PLACEHOLDER_PREFIX}{index}\x00"
        placeholders[token] = abbrev
        protected = protected.replace(abbrev, token)
    return protected, placeholders


def _restore_abbreviations(text: str, placeholders: dict[str, str]) -> str:
    restored = text
    for token, abbrev in placeholders.items():
        restored = restored.replace(token, abbrev)
    return restored


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences on . ? ! boundaries.

    Preserves sentence text, cleans whitespace, skips empties. Does not use
    NLP libraries; applies simple abbreviation protection before splitting.
    """
    stripped = text.replace("\r\n", "\n").strip()
    if not stripped:
        return []

    # Treat paragraph breaks as sentence boundaries when no terminal punctuation.
    normalized = re.sub(r"\n{2,}", "\n\n", stripped)
    blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]

    sentences: list[str] = []
    for block in blocks:
        line_parts = [line.strip() for line in block.split("\n") if line.strip()]
        for part in line_parts:
            protected, placeholders = _protect_abbreviations(part)
            for segment in _SENTENCE_BOUNDARY.split(protected):
                segment = segment.strip()
                if not segment:
                    continue
                restored = _restore_abbreviations(segment, placeholders)
                cleaned = re.sub(r"\s+", " ", restored).strip()
                if cleaned:
                    sentences.append(cleaned)

    return sentences
