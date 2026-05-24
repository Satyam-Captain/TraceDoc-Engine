"""Deterministic symbolic relationship and co-reference inference."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.evidence.pattern_extractor import (
    INFERENCE_SYMBOLIC,
    ExtractedPhrase,
    clean_extracted_phrase,
)

# Lightweight implication registry for future symbolic mappings.
_SYMBOLIC_RELATIONSHIPS: dict[str, dict[str, tuple[str, ...]]] = {
    "openephyra": {
        "implies": ("Classic QA pipeline",),
        "pattern_name": "open_ephyra_pipeline_inference",
    },
}

_OPEN_EPHYRA_ENTITY = re.compile(r"\bopen\s*ephyra\b", re.IGNORECASE)
_OPEN_EPHYRA_FEATURE_MARKERS: tuple[str, ...] = (
    "question analysis",
    "query generation",
    "answer extraction",
    "modular implementation",
)

_COREFERENCE_PATTERN = re.compile(
    r"\b(?:this|that)\s+(?:pipeline|architecture)\b",
    re.IGNORECASE,
)

_ARCHITECTURE_CONTEXT_MARKERS: tuple[str, ...] = (
    "architecture",
    "openephyra",
    "open ephyra",
    "pipeline",
    "question analysis",
    "query generation",
    "answer extraction",
    "modular implementation",
    "enterprise search stack",
    "ontology",
    "knowledge-graph",
    "traceability",
    "citation graph",
)

_CLEANEST_PIPELINE_MARKER = "cleanest conceptual answer"


@dataclass(frozen=True)
class _SymbolicRule:
    """A category-specific symbolic inference rule."""

    pattern_name: str
    implied_value: str
    applies_to_sentence: Callable[[str], bool]
    resolve_coreference: bool = False


def _sentence_has_open_ephyra_features(sentence: str) -> bool:
    lower = sentence.lower()
    if not _OPEN_EPHYRA_ENTITY.search(sentence):
        return False
    if "modular implementation" in lower:
        return True
    feature_hits = sum(1 for marker in _OPEN_EPHYRA_FEATURE_MARKERS if marker in lower)
    return feature_hits >= 2


def _sentence_is_architecture_context(sentence: str) -> bool:
    lower = sentence.lower()
    return any(marker in lower for marker in _ARCHITECTURE_CONTEXT_MARKERS)


def _sentence_has_coreference(sentence: str) -> bool:
    return _COREFERENCE_PATTERN.search(sentence) is not None


def _resolve_backward_architecture_sentence(
    sentences: list[str],
    start_index: int,
) -> str | None:
    for index in range(start_index - 1, -1, -1):
        candidate = sentences[index]
        if _sentence_has_open_ephyra_features(candidate):
            return candidate
        if _sentence_is_architecture_context(candidate):
            return candidate
    return None


def _open_ephyra_rule_applies(sentence: str) -> bool:
    return _sentence_has_open_ephyra_features(sentence)


def _coreference_rule_applies(sentence: str, sentences: list[str], index: int) -> bool:
    if not _sentence_has_coreference(sentence):
        return False
    prior = _resolve_backward_architecture_sentence(sentences, index)
    if prior is None:
        return False
    if _sentence_has_open_ephyra_features(prior):
        return True
    lower = sentence.lower()
    return _CLEANEST_PIPELINE_MARKER in lower and _sentence_is_architecture_context(prior)


def _implied_architecture(entity_key: str) -> str:
    mapping = _SYMBOLIC_RELATIONSHIPS[entity_key]
    return str(mapping["implies"][0])


_ARCHITECTURE_SYMBOLIC_RULES: tuple[_SymbolicRule, ...] = (
    _SymbolicRule(
        pattern_name="open_ephyra_pipeline_inference",
        implied_value=_implied_architecture("openephyra"),
        applies_to_sentence=_open_ephyra_rule_applies,
    ),
    _SymbolicRule(
        pattern_name="coreference_pipeline_resolution",
        implied_value=_implied_architecture("openephyra"),
        applies_to_sentence=lambda _sentence: False,
        resolve_coreference=True,
    ),
)


def infer_symbolic_relationships(
    sentences: list[str],
    category: str,
    *,
    full_text: str = "",
    existing_values: frozenset[str] | None = None,
) -> list[ExtractedPhrase]:
    """
    Infer implicit entity phrases using deterministic symbolic rules.

    No probabilistic scoring; only registered relationship and co-reference rules.
    """
    if category.strip().lower() != "architecture" or not sentences:
        return []

    known = {value.lower() for value in (existing_values or frozenset())}
    inferred: list[tuple[int, ExtractedPhrase]] = []

    for index, sentence in enumerate(sentences):
        offset = full_text.find(sentence) if full_text else index * 1000

        for rule in _ARCHITECTURE_SYMBOLIC_RULES:
            if rule.resolve_coreference:
                if not _coreference_rule_applies(sentence, sentences, index):
                    continue
                pattern_name = "coreference_pipeline_resolution"
                if _sentence_has_open_ephyra_features(
                    _resolve_backward_architecture_sentence(sentences, index) or ""
                ):
                    pattern_name = "open_ephyra_pipeline_inference"
            elif not rule.applies_to_sentence(sentence):
                continue
            else:
                pattern_name = rule.pattern_name

            value = clean_extracted_phrase(rule.implied_value)
            if value.lower() in known:
                continue

            inferred.append(
                (
                    offset if offset >= 0 else index,
                    ExtractedPhrase(
                        value=value,
                        source_sentence=sentence.strip(),
                        pattern_name=pattern_name,
                        inference_type=INFERENCE_SYMBOLIC,
                    ),
                )
            )
            known.add(value.lower())
            break

    inferred.sort(key=lambda item: item[0])
    return [entry for _, entry in inferred]


def symbolic_relationship_graph() -> dict[str, dict[str, tuple[str, ...]]]:
    """Return the registered symbolic implication graph (read-only view)."""
    return {
        entity: {"implies": tuple(mapping["implies"])}
        for entity, mapping in _SYMBOLIC_RELATIONSHIPS.items()
    }
