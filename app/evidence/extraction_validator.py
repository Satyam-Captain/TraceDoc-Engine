"""Deterministic validation for category-aligned entity extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schema.models import DiscoveredPattern, DocumentSchema

REJECTION_CATEGORY_BOUNDARY = "category_boundary_violation"
REJECTION_GRAMMAR_MISMATCH = "grammar_sentence_mismatch"
REJECTION_SECTION_SCOPE = "section_scope_violation"
REJECTION_CONFLICTING_CATEGORY = "conflicting_category_entity"

_CROSS_CATEGORY_SOURCE_MARKERS: dict[str, tuple[str, ...]] = {
    "design_pattern": (
        " architecture is ",
        " architectures ",
        "most common",
        "enterprise search stack",
        "classic qa pipeline",
        "knowledge-graph stack",
        "citation graph",
    ),
    "architecture": (
        " design pattern is ",
        " design patterns ",
    ),
    "building_block": (
        " architecture is ",
        " design pattern is ",
    ),
    "capability": (
        " architecture is ",
        " design pattern is ",
    ),
}

_ORDINAL_GRAMMAR_LINE = re.compile(
    r"(?i)(?:the\s+first|(?:a|the)\s+(?:second|third|fourth|fifth|sixth))\s+.+?\s+is\s+",
)


@dataclass
class ExtractionValidationRegistry:
    """Per-document registry for category boundary checks."""

    category_sections: dict[str, str] = field(default_factory=dict)
    category_type_phrases: dict[str, list[str]] = field(default_factory=dict)
    entities_by_category: dict[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class EntityValidationOutcome:
    """Validation result for one extracted entity."""

    entity: str
    accepted: bool
    reason: str = ""


@dataclass
class FilteredExtractionResult:
    """Validated entities plus rejection audit trail."""

    validated_entities: list[str]
    rejected_entities: list[str]
    rejection_reasons: dict[str, str]


def type_phrases_for_category(
    schema: DocumentSchema,
    category: str,
) -> list[str]:
    """Collect discovered type phrases for one category."""
    from app.schema.registry import (
        primary_grammar_for_category,
        registry_patterns_for_category,
    )

    phrases: list[str] = []
    patterns = registry_patterns_for_category(schema, category)
    if not patterns and category == "design_pattern":
        grammar = primary_grammar_for_category(schema, category)
        if grammar is not None:
            patterns = [grammar]
    for pattern in patterns:
        phrases.extend(pattern.type_phrases)
        if pattern.ordinal_type_phrase:
            phrases.append(pattern.ordinal_type_phrase)
    normalized = sorted({_canonical_phrase(phrase) for phrase in phrases if phrase.strip()})
    if category == "design_pattern":
        normalized = [
            phrase
            for phrase in normalized
            if phrase != "architecture" and "architecture" not in phrase
        ]
    if category == "architecture":
        normalized = [
            phrase for phrase in normalized if "design pattern" not in phrase
        ]
    return normalized


def filter_text_to_category_sentences(
    text: str,
    category: str,
    schema: DocumentSchema,
) -> str:
    """Keep only sentences that align with one semantic category."""
    phrase_registry = ExtractionValidationRegistry(
        category_type_phrases={category: type_phrases_for_category(schema, category)},
    )
    from app.evidence.sentence_splitter import split_sentences

    return "\n".join(
        sentence
        for sentence in split_sentences(text)
        if _sentence_has_category_type_phrase(sentence, category, phrase_registry)
    )


def build_extraction_validation_registry(
    schema: DocumentSchema,
    *,
    full_text_by_category: dict[str, str] | None = None,
) -> ExtractionValidationRegistry:
    """
    Build category boundary metadata from a discovered document schema.

    Optionally pass pre-scoped section text per category to index known entities.
    """
    from app.evidence.extraction_runtime import execute_discovered_grammar

    from app.schema.registry import build_category_registry, registry_patterns_for_category

    category_registry = build_category_registry(schema)
    category_sections = {
        category: str(entry.get("section", ""))
        for category, entry in category_registry.items()
    }
    category_type_phrases: dict[str, list[str]] = {}
    entities_by_category: dict[str, frozenset[str]] = {}

    for category in category_sections:
        category_type_phrases[category] = type_phrases_for_category(schema, category)

    scoped_text = full_text_by_category or {}
    phrase_registry = ExtractionValidationRegistry(
        category_sections=category_sections,
        category_type_phrases=category_type_phrases,
    )
    for category in category_sections:
        indexed: set[str] = set()
        section_text = scoped_text.get(category, "")
        if section_text.strip():
            from app.evidence.sentence_splitter import split_sentences

            for sentence in split_sentences(section_text):
                if not _sentence_has_category_type_phrase(
                    sentence, category, phrase_registry
                ):
                    continue
                for pattern in registry_patterns_for_category(schema, category):
                    for entity in execute_discovered_grammar(sentence, pattern):
                        indexed.add(entity.lower())
            if category == "architecture":
                from app.evidence.pattern_extractor import _extract_architecture_phrases

                for entry in _extract_architecture_phrases(section_text):
                    if _sentence_has_category_type_phrase(
                        entry.source_sentence, category, phrase_registry
                    ):
                        indexed.add(entry.value.lower())
        entities_by_category[category] = frozenset(indexed)

    return ExtractionValidationRegistry(
        category_sections=category_sections,
        category_type_phrases=category_type_phrases,
        entities_by_category=entities_by_category,
    )


def _canonical_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _sentence_has_category_type_phrase(
    source_sentence: str,
    category: str,
    registry: ExtractionValidationRegistry,
) -> bool:
    sentence_lower = f" {source_sentence.lower()} "
    type_phrases = registry.category_type_phrases.get(category, ())
    if type_phrases:
        return any(phrase in sentence_lower for phrase in type_phrases)

    category_label = category.replace("_", " ")
    return category_label in sentence_lower


def _entity_in_foreign_category(
    entity: str,
    category: str,
    registry: ExtractionValidationRegistry,
    source_sentence: str,
) -> str | None:
    normalized = entity.lower()
    sentence_lower = f" {source_sentence.lower()} "
    for other_category, known_entities in registry.entities_by_category.items():
        if other_category == category:
            continue
        if normalized not in known_entities:
            continue
        if _sentence_has_category_type_phrase(source_sentence, other_category, registry):
            return other_category
        for marker in _CROSS_CATEGORY_SOURCE_MARKERS.get(category, ()):
            if marker in sentence_lower:
                return other_category
    return None


def validate_extracted_entity(
    entity: str,
    category: str,
    source_sentence: str,
    registry: ExtractionValidationRegistry,
    *,
    section_title: str = "",
) -> bool:
    """Return True when an entity belongs to the requested semantic category."""
    if not entity.strip() or not source_sentence.strip():
        return False

    sentence_lower = f" {source_sentence.lower()} "

    expected_section = registry.category_sections.get(category, "").strip().lower()
    if expected_section and section_title:
        if expected_section not in section_title.lower():
            return False

    foreign = _entity_in_foreign_category(
        entity, category, registry, source_sentence
    )
    if foreign is not None:
        return False

    for marker in _CROSS_CATEGORY_SOURCE_MARKERS.get(category, ()):
        if marker in sentence_lower:
            return False

    if not _ORDINAL_GRAMMAR_LINE.search(source_sentence):
        return False

    if not _sentence_has_category_type_phrase(source_sentence, category, registry):
        return False

    return True


def explain_rejection(
    entity: str,
    category: str,
    source_sentence: str,
    registry: ExtractionValidationRegistry,
    *,
    section_title: str = "",
) -> str:
    """Return a deterministic rejection reason for a failed entity."""
    if not source_sentence.strip():
        return REJECTION_GRAMMAR_MISMATCH

    expected_section = registry.category_sections.get(category, "").strip().lower()
    if expected_section and section_title and expected_section not in section_title.lower():
        return REJECTION_SECTION_SCOPE

    sentence_lower = f" {source_sentence.lower()} "
    foreign = _entity_in_foreign_category(
        entity, category, registry, source_sentence
    )
    if foreign is not None:
        return REJECTION_CONFLICTING_CATEGORY

    for marker in _CROSS_CATEGORY_SOURCE_MARKERS.get(category, ()):
        if marker in sentence_lower:
            return REJECTION_CATEGORY_BOUNDARY

    if not _ORDINAL_GRAMMAR_LINE.search(source_sentence):
        return REJECTION_GRAMMAR_MISMATCH

    if not _sentence_has_category_type_phrase(source_sentence, category, registry):
        return REJECTION_GRAMMAR_MISMATCH

    return ""


def filter_validated_entities(
    hits: list[tuple[str, str, str]],
    category: str,
    registry: ExtractionValidationRegistry,
) -> FilteredExtractionResult:
    """
    Filter raw extraction hits (entity, source_sentence, section_title).

    Preserves document order for accepted entities.
    """
    validated: list[str] = []
    rejected: list[str] = []
    reasons: dict[str, str] = {}
    seen: set[str] = set()

    for entity, source_sentence, section_title in hits:
        key = entity.lower()
        if key in seen:
            continue
        if validate_extracted_entity(
            entity,
            category,
            source_sentence,
            registry,
            section_title=section_title,
        ):
            seen.add(key)
            validated.append(entity)
            continue
        seen.add(key)
        rejected.append(entity)
        reasons[entity] = explain_rejection(
            entity,
            category,
            source_sentence,
            registry,
            section_title=section_title,
        )

    return FilteredExtractionResult(
        validated_entities=validated,
        rejected_entities=rejected,
        rejection_reasons=reasons,
    )


def validation_debug_lines(result: FilteredExtractionResult) -> list[str]:
    """Format validation audit lines for QA debug traces."""
    lines = [
        "entity_validation_enabled=True",
        f"validated_entities_count={len(result.validated_entities)}",
        f"rejected_entities_count={len(result.rejected_entities)}",
    ]
    if result.rejected_entities:
        rejected_preview = ", ".join(result.rejected_entities[:8])
        primary_reason = REJECTION_CATEGORY_BOUNDARY
        if result.rejection_reasons:
            primary_reason = next(iter(result.rejection_reasons.values()))
        lines.extend(
            [
                f"rejected_entities=[{rejected_preview}]",
                f"rejection_reason={primary_reason}",
            ]
        )
    return lines
