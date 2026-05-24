"""Deterministic rule-based phrase extraction for structured answers."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
_CITATION_PATTERN = re.compile(r"\[\d+\]|\(\d{4}\)|et al\.", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_MIN_PHRASE_LEN = 3
_MAX_PHRASE_LEN = 80

# Architecture enumeration: capture group 1 is the entity phrase X.
_ARCHITECTURE_RULES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)the\s+most\s+common\b.+?\barchitecture\s+is\s+(?:the\s+)?(.+?)(?:[.!?;,]|$)"
    ),
    re.compile(
        r"(?i)a\s+second\s+architecture\s+is\s+(?:the\s+)?(.+?)(?:[.!?;,]|$)"
    ),
    re.compile(
        r"(?i)a\s+third\s+architecture\s+is\s+(?:the\s+)?(.+?)(?:[.!?;,]|$)"
    ),
    re.compile(
        r"(?i)a\s+(?:fourth|fifth)\s+architecture\s+is\s+(?:the\s+)?(.+?)(?:[.!?;,]|$)"
    ),
    re.compile(
        r"(?i)another\s+architecture\s+is\s+(?:the\s+)?(.+?)(?:[.!?;,]|$)"
    ),
    re.compile(
        r"(?i)the\s+first\s+architecture\s+is\s+(?:the\s+)?(.+?)(?:[.!?;,]|$)"
    ),
)


@dataclass(frozen=True)
class ExtractedPhrase:
    """A phrase extracted from evidence with its source sentence."""

    value: str
    source_sentence: str


def _split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    parts = _SENTENCE_SPLIT.split(stripped)
    return [part.strip() for part in parts if part.strip()]


def _strip_leading_the(phrase: str) -> str:
    cleaned = phrase.strip()
    if cleaned.lower().startswith("the "):
        return cleaned[4:].strip()
    return cleaned


def _trim_punctuation(phrase: str) -> str:
    return phrase.strip(" \t\n\r.,;:!?\"'()[]")


def _to_display_phrase(phrase: str) -> str:
    """Apply light title casing while preserving acronyms and hyphenated tokens."""
    words = phrase.split()
    if not words:
        return phrase

    display: list[str] = []
    for index, word in enumerate(words):
        if len(word) >= 2 and word.isupper():
            display.append(word)
            continue
        if index == 0:
            display.append(word[:1].upper() + word[1:] if len(word) > 1 else word.upper())
        elif word.islower() or (len(word) > 1 and word[0].islower()):
            display.append(word.lower())
        else:
            display.append(word)
    return " ".join(display)


def _normalize_phrase(raw: str) -> str:
    cleaned = _trim_punctuation(_strip_leading_the(raw))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return _to_display_phrase(cleaned)


def _is_valid_phrase(phrase: str) -> bool:
    if len(phrase) < _MIN_PHRASE_LEN or len(phrase) > _MAX_PHRASE_LEN:
        return False
    if _URL_PATTERN.search(phrase):
        return False
    if _CITATION_PATTERN.search(phrase):
        return False
    if phrase.count(",") + phrase.count(";") >= 2:
        return False

    letters = [character for character in phrase if character.isalpha()]
    if not letters:
        return False
    digits = sum(character.isdigit() for character in phrase)
    if digits > len(phrase) * 0.4:
        return False

    alpha_lower = sum(character.islower() for character in letters)
    if alpha_lower / len(letters) > 0.95 and len(phrase) > 40:
        return False

    return True


def _phrase_in_source(phrase: str, source_lower: str) -> bool:
    return phrase.lower() in source_lower


def _dedupe_phrases(entries: list[ExtractedPhrase]) -> list[ExtractedPhrase]:
    seen: set[str] = set()
    unique: list[ExtractedPhrase] = []
    for entry in entries:
        key = entry.value.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


def _apply_rules(
    text: str,
    rules: tuple[re.Pattern[str], ...],
) -> list[ExtractedPhrase]:
    source_lower = text.lower()
    found: list[ExtractedPhrase] = []

    for sentence in _split_sentences(text):
        for pattern in rules:
            match = pattern.search(sentence)
            if not match:
                continue
            normalized = _normalize_phrase(match.group(1))
            if not _is_valid_phrase(normalized):
                continue
            if not _phrase_in_source(normalized, source_lower):
                continue
            found.append(
                ExtractedPhrase(value=normalized, source_sentence=sentence.strip())
            )

    return _dedupe_phrases(found)


def _extract_architecture_phrases(text: str) -> list[ExtractedPhrase]:
    return _apply_rules(text, _ARCHITECTURE_RULES)


_CATEGORY_EXTRACTORS: dict[str, Callable[[str], list[ExtractedPhrase]]] = {
    "architecture": _extract_architecture_phrases,
    # Future: capability, pattern, technology
}


def extract_enumerated_phrases_with_trace(
    text: str,
    category: str,
) -> list[ExtractedPhrase]:
    """Extract enumerated phrases with source-sentence traceability."""
    if not text or not text.strip():
        return []
    extractor = _CATEGORY_EXTRACTORS.get(category.strip().lower())
    if extractor is None:
        return []
    return extractor(text)


def extract_enumerated_phrases(text: str, category: str) -> list[str]:
    """
    Extract entity phrases from evidence text using category-specific rules.

    Deterministic, local-only, no ML. Returns display-normalized phrases in
    document order with duplicates removed.
    """
    return [
        entry.value
        for entry in extract_enumerated_phrases_with_trace(text, category)
    ]
