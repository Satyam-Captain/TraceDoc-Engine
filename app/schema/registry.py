"""Pattern registry built from discovered document schema."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.schema.grammar_discovery import flexible_type_fragment
from app.schema.models import DiscoveredPattern, DocumentSchema

_OPTIONAL_MODIFIER = r"(?:(?:critical|important|common)\s+)?"

_ORDINAL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("ordinal_first", r"(?i)the\s+first\s+{modifier}{type}\s+is\s+(?:the\s+)?"),
    ("ordinal_second", r"(?i)(?:a|the)\s+second\s+{modifier}{type}\s+is\s+(?:the\s+)?"),
    ("ordinal_third", r"(?i)(?:a|the)\s+third\s+{modifier}{type}\s+is\s+(?:the\s+)?"),
    ("ordinal_fourth", r"(?i)(?:a|the)\s+(?:fourth|fifth)\s+{modifier}{type}\s+is\s+(?:the\s+)?"),
)

_STOP_LOOKAHEAD = (
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)


def regexes_for_discovered_pattern(
    pattern: DiscoveredPattern,
) -> list[tuple[str, re.Pattern[str]]]:
    """Build deterministic extraction regexes for one discovered grammar."""
    compiled: list[tuple[str, re.Pattern[str]]] = []

    if pattern.pattern_name == "most_common_architecture":
        compiled.append(
            (
                "most_common_architecture",
                re.compile(
                    r"(?i)the\s+most\s+common\b.+?\barchitecture\s+is\s+(?:the\s+)?(.+?)"
                    + _STOP_LOOKAHEAD
                ),
            )
        )
        return compiled

    type_phrases = pattern.type_phrases or (
        [pattern.ordinal_type_phrase] if pattern.ordinal_type_phrase else []
    )
    type_fragment = flexible_type_fragment(type_phrases)
    if not type_fragment:
        return compiled

    for label, prefix in _ORDINAL_PREFIXES:
        expression = (
            prefix.format(modifier=_OPTIONAL_MODIFIER, type=type_fragment)
            + r"(.+?)"
            + _STOP_LOOKAHEAD
        )
        compiled.append((label, re.compile(expression)))

    return compiled


def build_pattern_registry(schema: DocumentSchema) -> dict[str, list[str]]:
    """
    Build a category → grammar name registry from discovered schema metadata.

    Example:
        {"design_pattern": ["ordinal_design_pattern"], ...}
    """
    registry: dict[str, list[str]] = defaultdict(list)
    for pattern in schema.discovered_patterns:
        if pattern.pattern_name not in registry[pattern.category]:
            registry[pattern.category].append(pattern.pattern_name)
    return {category: sorted(names) for category, names in registry.items()}


def build_category_registry(schema: DocumentSchema) -> dict[str, dict[str, Any]]:
    """
    Build rich registry entries with section titles and grammar families.

    Example:
        {
            "design_pattern": {
                "section": "Design patterns for implementation",
                "grammars": ["ordinal_design_pattern"],
            }
        }
    """
    category_sections = {
        category.normalized_name: category.source_section
        for category in schema.categories
    }
    registry: dict[str, dict[str, Any]] = {}
    for pattern in schema.discovered_patterns:
        entry = registry.setdefault(
            pattern.category,
            {
                "section": category_sections.get(pattern.category, ""),
                "grammars": [],
            },
        )
        if pattern.pattern_name not in entry["grammars"]:
            entry["grammars"].append(pattern.pattern_name)
    for category in schema.categories:
        registry.setdefault(
            category.normalized_name,
            {
                "section": category.source_section,
                "grammars": [],
            },
        )
    return registry


def registry_patterns_for_category(
    schema: DocumentSchema,
    category: str,
) -> list[DiscoveredPattern]:
    """Return discovered grammar objects for one category."""
    return [
        pattern
        for pattern in schema.discovered_patterns
        if pattern.category == category
    ]


def primary_grammar_for_category(
    schema: DocumentSchema,
    category: str,
) -> DiscoveredPattern | None:
    """Return the highest-confidence grammar for a category, if any."""
    patterns = registry_patterns_for_category(schema, category)
    if not patterns:
        return None
    return max(patterns, key=lambda item: item.confidence_score)

