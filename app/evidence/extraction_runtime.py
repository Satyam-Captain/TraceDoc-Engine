"""Execute discovered symbolic grammars against document text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.evidence.phrase_cleanup import clean_extracted_phrase
from app.evidence.sentence_splitter import split_sentences
from app.schema.models import DiscoveredPattern

_STOP_LOOKAHEAD = (
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)

_OPTIONAL_MODIFIER = r"(?:(?:critical|important|common)\s+)?"

_ORDINAL_LABEL_RANK: dict[str, int] = {
    "ordinal_first": 1,
    "ordinal_second": 2,
    "ordinal_third": 3,
    "ordinal_fourth": 4,
}

_TEMPLATE_ORDINAL_PREFIX: tuple[tuple[str, int, str], ...] = (
    ("the first", 1, r"(?i)the\s+first\s+"),
    ("second", 2, r"(?i)(?:a|the)\s+second\s+"),
    ("third", 3, r"(?i)(?:a|the)\s+third\s+"),
    ("fourth", 4, r"(?i)(?:a|the)\s+(?:fourth|fifth)\s+"),
)

_MIN_PHRASE_LEN = 3
_MAX_PHRASE_LEN = 80


@dataclass(frozen=True)
class GrammarExecutionResult:
    """Outcome of running one discovered grammar over text."""

    entities: list[str]
    extraction_confidence: float
    success: bool
    match_count: int


def _is_valid_entity(value: str) -> bool:
    if len(value) < _MIN_PHRASE_LEN or len(value) > _MAX_PHRASE_LEN:
        return False
    letters = [character for character in value if character.isalpha()]
    return bool(letters)


def _entity_in_source(entity: str, source_lower: str) -> bool:
    return entity.lower() in source_lower


def _dedupe_preserve_order(entities: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for entity in entities:
        key = entity.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(entity)
    return unique


def _extraction_confidence(
    match_count: int,
    grammar_confidence: float,
) -> float:
    if match_count <= 0:
        return 0.0
    score = 0.45 + (0.14 * match_count) + (0.12 * grammar_confidence)
    if match_count >= 2:
        score += 0.1
    return min(0.98, score)


def compile_grammar_regexes(
    pattern: DiscoveredPattern,
) -> list[tuple[str, int, re.Pattern[str]]]:
    """
    Build ordered ordinal extraction regexes from discovered grammar metadata.

    Uses sentence templates when present; otherwise falls back to registry regexes.
    """
    from app.schema.grammar_discovery import flexible_type_fragment
    from app.schema.registry import regexes_for_discovered_pattern

    if pattern.pattern_name == "most_common_architecture":
        compiled: list[tuple[str, int, re.Pattern[str]]] = []
        for label, regex in regexes_for_discovered_pattern(pattern):
            compiled.append((label, 0, regex))
        return compiled

    type_phrases = pattern.type_phrases or (
        [pattern.ordinal_type_phrase] if pattern.ordinal_type_phrase else []
    )
    type_fragment = flexible_type_fragment(type_phrases)
    if not type_fragment:
        return []

    templates = pattern.sentence_templates or []
    active_ordinal: list[tuple[str, int, str]] = []
    template_text = " ".join(templates).lower()
    for marker, rank, prefix in _TEMPLATE_ORDINAL_PREFIX:
        if marker in template_text or not templates:
            active_ordinal.append((f"ordinal_{marker.replace(' ', '_')}", rank, prefix))

    if not active_ordinal:
        active_ordinal = list(_TEMPLATE_ORDINAL_PREFIX)

    type_with_modifier = _OPTIONAL_MODIFIER + type_fragment
    compiled = []
    for label, rank, prefix in active_ordinal:
        expression = prefix + type_with_modifier + r"\s+is\s+(?:the\s+)?(.+?)" + _STOP_LOOKAHEAD
        compiled.append((label, rank, re.compile(expression)))

    if compiled:
        return compiled

    for label, regex in regexes_for_discovered_pattern(pattern):
        rank = _ORDINAL_LABEL_RANK.get(label, 99)
        compiled.append((label, rank, regex))
    return compiled


def execute_discovered_grammar(
    text: str,
    discovered_pattern: DiscoveredPattern,
) -> list[str]:
    """Extract entity strings using one discovered grammar (document order, deduped)."""
    return execute_discovered_grammar_with_result(
        text, discovered_pattern
    ).entities


def execute_discovered_grammar_with_result(
    text: str,
    discovered_pattern: DiscoveredPattern,
) -> GrammarExecutionResult:
    """Extract entities and return execution metadata for debug traces."""
    if not text or not text.strip():
        return GrammarExecutionResult(
            entities=[],
            extraction_confidence=0.0,
            success=False,
            match_count=0,
        )

    source_lower = text.lower()
    sentences = split_sentences(text)
    hits: list[tuple[int, int, str]] = []

    for label, rank, regex in compile_grammar_regexes(discovered_pattern):
        for sentence in sentences:
            match = regex.search(sentence)
            if not match:
                continue
            raw_entity = match.group(1)
            cleaned = clean_extracted_phrase(raw_entity)
            if not _is_valid_entity(cleaned):
                continue
            if not _entity_in_source(cleaned, source_lower):
                continue
            sentence_offset = text.find(sentence)
            position = (
                sentence_offset + match.start()
                if sentence_offset >= 0
                else match.start()
            )
            hits.append((rank if rank > 0 else position, position, cleaned))

    hits.sort(key=lambda item: (item[0], item[1]))
    entities = _dedupe_preserve_order([entity for _, _, entity in hits])
    match_count = len(entities)
    confidence = _extraction_confidence(
        match_count,
        discovered_pattern.confidence_score,
    )
    return GrammarExecutionResult(
        entities=entities,
        extraction_confidence=confidence,
        success=match_count > 0,
        match_count=match_count,
    )
