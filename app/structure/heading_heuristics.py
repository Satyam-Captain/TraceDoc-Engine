"""Deterministic PDF-friendly heading detection heuristics."""

from __future__ import annotations

import re

_HEADING_SCORE_THRESHOLD = 5.0
_MAX_HEADING_LEN = 80
_HARD_MAX_HEADING_LEN = 120

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
_CITATION_PATTERN = re.compile(r"\[\d+\]|\(\d{4}\)|et al\.", re.IGNORECASE)
_BULLET_PATTERN = re.compile(r"^[\-\*•]\s+")
_NUMBER_HEAVY_PATTERN = re.compile(r"^\d+[\.\)]\s+")

_KNOWN_HEADING_PREFIXES = (
    "existing",
    "design",
    "design patterns",
    "design pattern",
    "overview",
    "architecture",
    "architectures",
    "open-source",
    "open source",
    "common",
    "future",
    "requirements",
    "capabilities",
    "limitations",
    "conclusion",
    "ways",
    "what",
    "how",
    "why",
    "introduction",
    "background",
    "summary",
)


def _strip(line: str | None) -> str:
    return (line or "").strip()


def _is_blank(line: str | None) -> bool:
    return not _strip(line)


def _word_count(line: str) -> int:
    return len(_strip(line).split())


def _is_title_cased(line: str) -> bool:
    words = [word for word in _strip(line).split() if word]
    if not words or len(words) > 12:
        return False
    capitalized = sum(1 for word in words if word[0].isupper())
    return capitalized >= max(1, int(len(words) * 0.6))


def _capital_ratio(line: str) -> float:
    letters = [character for character in line if character.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for character in letters if character.isupper()) / len(letters)


def _has_known_prefix(line: str) -> bool:
    lower = _strip(line).lower()
    return any(lower.startswith(prefix) for prefix in _KNOWN_HEADING_PREFIXES)


def _next_is_longer_paragraph(next_line: str | None) -> bool:
    next_stripped = _strip(next_line)
    if not next_stripped:
        return False
    return len(next_stripped) > 40 and not next_stripped.endswith(":")


def score_heading_probability(
    line: str,
    previous_line: str | None,
    next_line: str | None,
) -> float:
    """
    Score how likely a line is a PDF-style section heading (higher is stronger).

    Uses layout and typography heuristics only; no ML.
    """
    stripped = _strip(line)
    if not stripped:
        return 0.0

    score = 0.0

    if len(stripped) <= _MAX_HEADING_LEN:
        score += 1.0
    if _is_title_cased(stripped):
        score += 2.0
    if not stripped.endswith((".", "!", "?")):
        score += 1.0
    if _is_blank(previous_line):
        score += 1.0
    if _is_blank(next_line):
        score += 1.0
    if _capital_ratio(stripped) >= 0.35:
        score += 1.0
    if _has_known_prefix(stripped):
        score += 2.0
    if not _URL_PATTERN.search(stripped):
        score += 0.5
    if sum(character.isdigit() for character in stripped) <= max(2, len(stripped) // 8):
        score += 0.5
    if _next_is_longer_paragraph(next_line):
        score += 2.0

    if stripped.endswith("."):
        score -= 3.0
    if _URL_PATTERN.search(stripped):
        score -= 2.0
    if _CITATION_PATTERN.search(stripped):
        score -= 2.0
    if len(stripped) > _HARD_MAX_HEADING_LEN:
        score -= 5.0
    if stripped.islower():
        score -= 2.0
    if _BULLET_PATTERN.match(stripped):
        score -= 3.0
    if stripped.count(",") + stripped.count(";") >= 2:
        score -= 2.0
    if _word_count(stripped) > 14:
        score -= 2.0
    if _NUMBER_HEAVY_PATTERN.match(stripped) and not _has_known_prefix(stripped):
        score -= 1.0

    return score


def is_probable_heading(
    line: str,
    previous_line: str | None,
    next_line: str | None,
) -> bool:
    """Return True when layout heuristics indicate a semantic section heading."""
    stripped = _strip(line)
    if not stripped:
        return False
    if stripped.endswith((".", "!", "?")):
        return False

    # PDF-style headings usually sit on their own line between blank lines.
    if not _is_blank(previous_line):
        return False
    if not (_is_blank(next_line) or _next_is_longer_paragraph(next_line)):
        return False
    if _word_count(stripped) > 12:
        return False
    if not _is_title_cased(stripped) and not _has_known_prefix(stripped):
        return False

    return score_heading_probability(line, previous_line, next_line) >= _HEADING_SCORE_THRESHOLD
