"""Deterministic rule-based phrase extraction for structured answers."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.evidence.sentence_splitter import split_sentences

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
_CITATION_PATTERN = re.compile(r"\[\d+\]|\(\d{4}\)|et al\.", re.IGNORECASE)

_MIN_PHRASE_LEN = 3
_MAX_PHRASE_LEN = 80

_PRESERVED_ACRONYMS = frozenset(
    {"QA", "RDF", "OWL", "SPARQL", "BM25", "LLM", "AI"}
)

# Deterministic noun-phrase recognition targets (only emitted if present in evidence).
_ARCHITECTURE_NOUN_PHRASES: tuple[str, ...] = (
    "enterprise search stack",
    "classic QA pipeline",
    "ontology and knowledge-graph stack",
    "traceability and citation graph",
)

_STOP_AFTER = re.compile(
    r"\s+(?:which|that|where|with)\b",
    re.IGNORECASE,
)

_MOST_COMMON_ARCHITECTURE = re.compile(
    r"(?i)the\s+most\s+common\b.+?\barchitecture\s+is\s+(?:the\s+)?(.+?)"
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)

_ORDINAL_ARCHITECTURE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "second_architecture",
        re.compile(
            r"(?i)a\s+second\s+architecture\s+is\s+(?:the\s+)?(.+?)"
            r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
        ),
    ),
    (
        "third_architecture",
        re.compile(
            r"(?i)a\s+third\s+architecture\s+is\s+(?:the\s+)?(.+?)"
            r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
        ),
    ),
    (
        "fourth_architecture",
        re.compile(
            r"(?i)a\s+(?:fourth|fifth)\s+architecture\s+is\s+(?:the\s+)?(.+?)"
            r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
        ),
    ),
    (
        "another_architecture",
        re.compile(
            r"(?i)another\s+architecture\s+is\s+(?:the\s+)?(.+?)"
            r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
        ),
    ),
    (
        "first_architecture",
        re.compile(
            r"(?i)the\s+first\s+architecture\s+is\s+(?:the\s+)?(.+?)"
            r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
        ),
    ),
)

_CLASSIC_QA_PHRASE = re.compile(r"(?i)\b(?:the\s+)?classic\s+QA\s+pipeline\b")
_CLASSIC_QA_CONTEXT_MARKERS = (
    "second architecture",
    "this pipeline is still the cleanest conceptual answer",
    "pipeline is still the cleanest conceptual answer",
)


@dataclass(frozen=True)
class ExtractedPhrase:
    """A phrase extracted from evidence with trace metadata."""

    value: str
    source_sentence: str
    pattern_name: str = ""


def clean_extracted_phrase(phrase: str) -> str:
    """
    Normalize a raw captured phrase for display.

    Strips leading articles, trims punctuation, removes trailing explanatory
  clauses after :, ;, or , and applies light title-casing while preserving
    known acronyms.
    """
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


def _is_valid_phrase(phrase: str) -> bool:
    if len(phrase) < _MIN_PHRASE_LEN or len(phrase) > _MAX_PHRASE_LEN:
        return False
    if _URL_PATTERN.search(phrase):
        return False
    if "://" in phrase or phrase.lower().startswith("http"):
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

    return True


def _phrase_in_source(phrase: str, source_lower: str) -> bool:
    return phrase.lower() in source_lower


def _sentence_for_match(text: str, match_start: int, sentences: list[str]) -> str:
    offset = 0
    for sentence in sentences:
        index = text.find(sentence, offset)
        if index == -1:
            continue
        end = index + len(sentence)
        if index <= match_start < end:
            return sentence
        offset = end
    return text[max(0, match_start - 80) : match_start + 120].strip()


def _add_candidate(
    candidates: list[tuple[int, ExtractedPhrase]],
    *,
    position: int,
    value: str,
    source_sentence: str,
    pattern_name: str,
    source_lower: str,
) -> None:
    cleaned = clean_extracted_phrase(value)
    if not _is_valid_phrase(cleaned):
        return
    if not _phrase_in_source(cleaned, source_lower):
        return
    candidates.append(
        (
            position,
            ExtractedPhrase(
                value=cleaned,
                source_sentence=source_sentence.strip(),
                pattern_name=pattern_name,
            ),
        )
    )


def _extract_classic_qa_pipeline(
    text: str,
    sentences: list[str],
    source_lower: str,
    candidates: list[tuple[int, ExtractedPhrase]],
) -> None:
    for index, sentence in enumerate(sentences):
        match = _CLASSIC_QA_PHRASE.search(sentence)
        if not match:
            continue

        window = " ".join(sentences[max(0, index - 2) : min(len(sentences), index + 3)])
        window_lower = window.lower()
        if not any(marker in window_lower for marker in _CLASSIC_QA_CONTEXT_MARKERS):
            continue

        sentence_offset = text.find(sentence)
        position = sentence_offset + match.start() if sentence_offset >= 0 else match.start()
        _add_candidate(
            candidates,
            position=position,
            value=match.group(0),
            source_sentence=sentence,
            pattern_name="classic_qa_context",
            source_lower=source_lower,
        )


def _extract_noun_phrase_fallback(
    text: str,
    source_lower: str,
    candidates: list[tuple[int, ExtractedPhrase]],
    sentences: list[str],
) -> None:
    for canonical in _ARCHITECTURE_NOUN_PHRASES:
        pattern = re.compile(re.escape(canonical), re.IGNORECASE)
        for match in pattern.finditer(text):
            _add_candidate(
                candidates,
                position=match.start(),
                value=match.group(0),
                source_sentence=_sentence_for_match(text, match.start(), sentences),
                pattern_name="noun_phrase_evidence",
                source_lower=source_lower,
            )


def _dedupe_by_position(candidates: list[tuple[int, ExtractedPhrase]]) -> list[ExtractedPhrase]:
    ordered = sorted(candidates, key=lambda item: item[0])
    seen: set[str] = set()
    unique: list[ExtractedPhrase] = []
    for _, entry in ordered:
        key = entry.value.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique


def _extract_architecture_phrases(text: str) -> list[ExtractedPhrase]:
    source_lower = text.lower()
    sentences = split_sentences(text)
    candidates: list[tuple[int, ExtractedPhrase]] = []

    for match in _MOST_COMMON_ARCHITECTURE.finditer(text):
        _add_candidate(
            candidates,
            position=match.start(),
            value=match.group(1),
            source_sentence=_sentence_for_match(text, match.start(), sentences),
            pattern_name="most_common_architecture",
            source_lower=source_lower,
        )

    for sentence in sentences:
        sentence_offset = text.find(sentence)
        base = sentence_offset if sentence_offset >= 0 else 0
        for pattern_name, pattern in _ORDINAL_ARCHITECTURE_RULES:
            match = pattern.search(sentence)
            if not match:
                continue
            _add_candidate(
                candidates,
                position=base + match.start(),
                value=match.group(1),
                source_sentence=sentence,
                pattern_name=pattern_name,
                source_lower=source_lower,
            )

    _extract_classic_qa_pipeline(text, sentences, source_lower, candidates)
    _extract_noun_phrase_fallback(text, source_lower, candidates, sentences)

    return _dedupe_by_position(candidates)


_CATEGORY_EXTRACTORS: dict[str, Callable[[str], list[ExtractedPhrase]]] = {
    "architecture": _extract_architecture_phrases,
}


def extract_enumerated_phrases_with_trace(
    text: str,
    category: str,
) -> list[ExtractedPhrase]:
    """Extract enumerated phrases with source-sentence and pattern traceability."""
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
