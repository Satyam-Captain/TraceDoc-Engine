"""Deterministic extraction grammar discovery from document text."""

from __future__ import annotations

import re
from collections import defaultdict

from app.evidence.sentence_splitter import split_sentences
from app.schema.models import DiscoveredCategory, DiscoveredPattern
from app.structure.models import DocumentChunk

_STOP_LOOKAHEAD = (
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)

_ORDINAL_SENTENCE = re.compile(
    r"(?i)(?P<ordinal>the\s+first|(?:a|the)\s+second|(?:a|the)\s+third|"
    r"(?:a|the)\s+(?:fourth|fifth))\s+(?P<type>.+?)\s+is\s+(?:the\s+)?"
    r"(?P<entity>.+?)"
    + _STOP_LOOKAHEAD
)

_MOST_COMMON_ARCHITECTURE = re.compile(
    r"(?i)the\s+most\s+common\b.+?\barchitecture\s+is\s+(?:the\s+)?(.+?)"
    + _STOP_LOOKAHEAD
)

_ORDINAL_TEMPLATE_LABELS: tuple[tuple[str, str], ...] = (
    ("the first", "The first <CATEGORY> is <ENTITY>"),
    ("second", "The second <CATEGORY> is <ENTITY>"),
    ("third", "The third <CATEGORY> is <ENTITY>"),
    ("fourth", "The fourth <CATEGORY> is <ENTITY>"),
    ("fifth", "The fifth <CATEGORY> is <ENTITY>"),
)

_MIN_GRAMMAR_HITS = 2


def _canonical_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _type_regex_fragment(type_phrase: str) -> str:
    words = [re.escape(word) for word in type_phrase.split()]
    return r"\s+".join(words)


def flexible_type_fragment(type_phrases: list[str]) -> str:
    """Build a regex fragment covering observed type-phrase variants."""
    normalized = sorted(
        {_canonical_phrase(phrase) for phrase in type_phrases if phrase.strip()},
        key=len,
    )
    if not normalized:
        return r"(?:\w+(?:\s+\w+){0,10})"
    if len(normalized) == 1:
        return _type_regex_fragment(normalized[0])

    shortest = normalized[0]
    longest = normalized[-1]
    if longest.endswith(shortest) and longest != shortest:
        prefix = longest[: -len(shortest)].strip()
        if prefix:
            return (
                rf"(?:{_type_regex_fragment(prefix)}\s+)?"
                rf"{_type_regex_fragment(shortest)}"
            )

    return "(?:" + "|".join(_type_regex_fragment(phrase) for phrase in normalized) + ")"


def _grammar_confidence(hit_count: int, ordinal_variants: int) -> float:
    score = 0.55 + (0.12 * hit_count) + (0.05 * ordinal_variants)
    return min(0.98, score)


def _sentence_templates_for_hits(
    hits: list[dict[str, str]],
    category: str,
) -> list[str]:
    templates: list[str] = []
    seen: set[str] = set()
    for label, template in _ORDINAL_TEMPLATE_LABELS:
        if any(label in hit["ordinal"].lower() for hit in hits):
            if template not in seen:
                seen.add(template)
                templates.append(template)
    if not templates:
        category_label = category.replace("_", " ")
        templates.append(f"The first <CATEGORY> is <ENTITY>")
        templates.append(f"The second <CATEGORY> is <ENTITY>")
        templates.append(f"The third <CATEGORY> is <ENTITY>")
        templates.append(
            f"Templates describe ordinal enumeration for {category_label}."
        )
    return templates


def discover_extraction_grammars(
    category: str,
    chunks: list[DocumentChunk],
    *,
    source_section: str = "",
) -> list[DiscoveredPattern]:
    """
    Detect repeated symbolic sentence structures for one semantic category.

    Clusters ordinal enumeration lines into a single grammar family per category.
    """
    if not chunks:
        return []

    hits: list[dict[str, str]] = []
    examples: list[str] = []
    triggers: set[str] = set()

    for chunk in chunks:
        for sentence in split_sentences(chunk.text):
            match = _ORDINAL_SENTENCE.search(sentence)
            if not match:
                continue
            type_phrase = _canonical_phrase(match.group("type"))
            entity = match.group("entity").strip()
            ordinal = match.group("ordinal").strip()
            hits.append(
                {
                    "ordinal": ordinal,
                    "type": type_phrase,
                    "entity": entity,
                    "sentence": sentence.strip(),
                }
            )
            triggers.add(f"{ordinal.lower()} {type_phrase} is")
            if len(examples) < 5:
                examples.append(sentence.strip()[:200])

    patterns: list[DiscoveredPattern] = []

    if len(hits) >= _MIN_GRAMMAR_HITS:
        type_phrases = sorted({hit["type"] for hit in hits})
        ordinal_variants = len({hit["ordinal"].lower() for hit in hits})
        pattern_name = f"ordinal_{category}"
        primary_type = type_phrases[-1] if type_phrases else category.replace("_", " ")

        patterns.append(
            DiscoveredPattern(
                pattern_name=pattern_name,
                category=category,
                trigger_phrases=sorted(triggers),
                example_sentences=examples,
                ordinal_type_phrase=primary_type,
                type_phrases=type_phrases,
                sentence_templates=_sentence_templates_for_hits(hits, category),
                confidence_score=_grammar_confidence(len(hits), ordinal_variants),
                grammar_family="ordinal_pattern_enumeration",
            )
        )

    if category == "architecture":
        arch_examples: list[str] = []
        arch_triggers: set[str] = set()
        for chunk in chunks:
            for sentence in split_sentences(chunk.text):
                match = _MOST_COMMON_ARCHITECTURE.search(sentence)
                if not match:
                    continue
                arch_triggers.add("the most common architecture is")
                if len(arch_examples) < 3:
                    arch_examples.append(sentence.strip()[:200])

        if arch_triggers:
            patterns.append(
                DiscoveredPattern(
                    pattern_name="most_common_architecture",
                    category=category,
                    trigger_phrases=sorted(arch_triggers),
                    example_sentences=arch_examples,
                    ordinal_type_phrase="architecture",
                    type_phrases=["architecture"],
                    sentence_templates=["The most common <CATEGORY> is <ENTITY>"],
                    confidence_score=0.9,
                    grammar_family="most_common_enumeration",
                )
            )

    if not patterns and source_section:
        return patterns

    return patterns


def discover_grammars_for_categories(
    categories: list[DiscoveredCategory],
    chunks: list[DocumentChunk],
    category_resolver,
) -> list[DiscoveredPattern]:
    """Discover grammars for each category over its related chunks."""
    by_category_chunks: dict[str, list[DocumentChunk]] = defaultdict(list)
    for chunk in chunks:
        resolved = category_resolver(chunk)
        if resolved:
            by_category_chunks[resolved].append(chunk)

    discovered: list[DiscoveredPattern] = []
    for category in categories:
        category_chunks = by_category_chunks.get(category.normalized_name, [])
        if not category_chunks:
            category_chunks = chunks
        grammars = discover_extraction_grammars(
            category.normalized_name,
            category_chunks,
            source_section=category.source_section,
        )
        discovered.extend(grammars)

    return discovered
