"""Deterministic matched-term highlighting."""

from __future__ import annotations

import re


def _is_inside_highlight(text: str, index: int) -> bool:
    """Return True if index falls inside existing [[...]] markers."""
    open_marker = text.rfind("[[", 0, index)
    if open_marker == -1:
        return False
    close_marker = text.find("]]", open_marker)
    return close_marker != -1 and close_marker >= index


def highlight_terms(text: str, terms: list[str]) -> str:
    """
    Highlight matched terms using [[term]] markers.

    Matching is case-insensitive while preserving original text casing.
    Already highlighted regions are not highlighted again.
    """
    if not text or not terms:
        return text

    unique_terms = sorted({term for term in terms if term}, key=len, reverse=True)
    spans: list[tuple[int, int]] = []

    for term in unique_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            if _is_inside_highlight(text, start):
                continue
            if any(not (end <= existing_start or start >= existing_end) for existing_start, existing_end in spans):
                continue
            spans.append((start, end))

    if not spans:
        return text

    spans.sort(key=lambda item: item[0])
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        parts.append(f"[[{text[start:end]}]]")
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)
