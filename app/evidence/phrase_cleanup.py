"""Shared phrase normalization for extraction and graph candidates."""

from __future__ import annotations

import re

_PRESERVED_ACRONYMS = frozenset(
    {"QA", "RDF", "OWL", "SPARQL", "BM25", "LLM", "AI"}
)

_STOP_AFTER = re.compile(
    r"\s+(?:which|that|where|with)\b",
    re.IGNORECASE,
)


def clean_extracted_phrase(phrase: str) -> str:
    """Normalize a raw captured phrase for display."""
    cleaned = phrase.strip()
    for article in ("the ", "a ", "an "):
        if cleaned.lower().startswith(article):
            cleaned = cleaned[len(article) :].strip()
            break

    cleaned = _STOP_AFTER.split(cleaned, maxsplit=1)[0]
    for separator in (":", ";", ","):
        if separator in cleaned:
            cleaned = cleaned.split(separator, maxsplit=1)[0]

    cleaned = cleaned.strip(" \t\n\r.,;:!?\"'()[]")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return _to_display_phrase(cleaned)


def _to_display_phrase(phrase: str) -> str:
    words = phrase.split()
    if not words:
        return phrase

    display: list[str] = []
    for index, word in enumerate(words):
        bare = word.strip(".,;:!?")
        upper_bare = bare.upper()
        if upper_bare in _PRESERVED_ACRONYMS or (len(bare) >= 2 and bare.isupper()):
            display.append(upper_bare if upper_bare in _PRESERVED_ACRONYMS else bare)
            continue
        if index == 0:
            display.append(bare[:1].upper() + bare[1:] if len(bare) > 1 else bare.upper())
        elif bare.islower() or (len(bare) > 1 and bare[0].islower()):
            display.append(bare.lower())
        else:
            display.append(bare)
    return " ".join(display)
