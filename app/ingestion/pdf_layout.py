"""Deterministic PDF text layout reconstruction before structure detection."""

from __future__ import annotations

import re

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)

_KNOWN_INLINE_HEADINGS: tuple[str, ...] = (
    "Ways to make systems feel intelligent without AI",
    "What this kind of system really is",
    "Requirements for evidence quality",
    "Open-source building blocks",
    "Existing architectures",
    "Architecture comparison",
    "Evaluation checklist",
    "Common capabilities",
    "Future improvements",
    "Open source building blocks",
    "Limitations",
    "Conclusion",
    "Introduction",
    "Overview",
    "Background",
    "Summary",
    "Capabilities",
    "Requirements",
    "Architectures",
)

_HEADING_PREFIXES: tuple[str, ...] = (
    "existing",
    "architecture",
    "architectures",
    "open-source",
    "open source",
    "common",
    "requirements",
    "conclusion",
    "future",
    "capabilities",
    "limitations",
    "evaluation",
    "ways",
    "what",
    "how",
    "introduction",
    "overview",
    "background",
)

# Explanatory sentence often starts with these words after a heading phrase.
_FOLLOWING_SENTENCE_START = (
    "The",
    "A",
    "An",
    "For",
    "In",
    "When",
    "This",
    "These",
    "If",
    "Teams",
    "Users",
    "It",
    "Every",
    "Each",
    "Better",
    "Reviewers",
    "TraceDoc",
    "No",
    "PDF",
    "Heading",
    "Lexical",
    "Multi",
    "Lineage",
    "Structured",
    "Section",
    "Deterministic",
    "Evidence",
)

_FOLLOW_PATTERN = r"(?:" + "|".join(re.escape(word) for word in _FOLLOWING_SENTENCE_START) + r")\b"

_GENERIC_INLINE_HEADING = re.compile(
    rf"(?<=[.!?;:])\s+"
    rf"([A-Z][A-Za-z0-9\-]+(?:\s+(?:[a-z]+|[A-Z][A-Za-z0-9\-]+|and|or|of|the|in|on|to|for|without|with)){1,11})"
    rf"(?=\s+{_FOLLOW_PATTERN})"
)


def _normalize_whitespace_per_line(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines)


def _has_known_prefix(phrase: str) -> bool:
    lower = phrase.lower()
    return any(lower.startswith(prefix) for prefix in _HEADING_PREFIXES)


def _is_title_cased_phrase(phrase: str) -> bool:
    words = [word for word in phrase.split() if word]
    if not words or len(words) > 12:
        return False
    capitalized = sum(1 for word in words if word[0].isupper())
    return capitalized >= max(1, int(len(words) * 0.6))


def _is_valid_inline_heading_phrase(phrase: str) -> bool:
    stripped = phrase.strip()
    if len(stripped) < 3 or len(stripped) > 80:
        return False
    if stripped.endswith((".", "!", "?", ",", ";", ":")):
        return False
    if _URL_PATTERN.search(stripped):
        return False
    if stripped.count(",") + stripped.count(";") >= 2:
        return False
    if stripped.islower():
        return False
    if not (_is_title_cased_phrase(stripped) or _has_known_prefix(stripped)):
        return False
    return True


def _wrap_heading(phrase: str) -> str:
    return f"\n\n{phrase}\n\n"


def _isolate_known_headings(text: str) -> str:
    result = text
    for phrase in sorted(_KNOWN_INLINE_HEADINGS, key=len, reverse=True):
        if phrase not in result:
            continue
        escaped = re.escape(phrase)
        patterns = (
            rf"^({escaped})(?=\s+{_FOLLOW_PATTERN})",
            rf"(?<=[.!?;:])\s*({escaped})(?=\s+{_FOLLOW_PATTERN})",
            rf"(?<=[.!?;:])\s*({escaped})(?=\s+[A-Z])",
            rf"\s+({escaped})(?=\s+{_FOLLOW_PATTERN})",
            rf"\s+({escaped})(?=\s+[A-Z])",
        )
        for pattern in patterns:
            result = re.sub(pattern, lambda match: _wrap_heading(match.group(1)), result)
    return result


def _isolate_generic_inline_headings(text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        phrase = match.group(1).strip()
        if not _is_valid_inline_heading_phrase(phrase):
            return match.group(0)
        full = match.group(0)
        if f"\n\n{phrase}\n\n" in full:
            return full
        return full.replace(phrase, _wrap_heading(phrase), 1)

    return _GENERIC_INLINE_HEADING.sub(replacer, text)


def reconstruct_pdf_layout(text: str) -> str:
    """
    Insert semantic line breaks around probable inline headings in flattened PDF text.

    PDF extractors often merge headings into paragraphs, e.g.
    "...mechanism. Existing architectures The most common..." — this function
    restores isolated heading lines for downstream section detection.
    """
    if not text or not text.strip():
        return text

    normalized = text.replace("\r\n", "\n")
    normalized = _isolate_known_headings(normalized)
    normalized = _isolate_generic_inline_headings(normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return _normalize_whitespace_per_line(normalized).strip()
