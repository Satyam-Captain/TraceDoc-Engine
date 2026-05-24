"""Pattern registry built from discovered document schema."""

from __future__ import annotations

import re
from collections import defaultdict

from app.schema.models import DiscoveredPattern, DocumentSchema

_ORDINAL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("ordinal_first", r"(?i)the\s+first\s+{type}\s+is\s+(?:the\s+)?"),
    ("ordinal_second", r"(?i)(?:a|the)\s+second\s+{type}\s+is\s+(?:the\s+)?"),
    ("ordinal_third", r"(?i)(?:a|the)\s+third\s+{type}\s+is\s+(?:the\s+)?"),
    ("ordinal_fourth", r"(?i)(?:a|the)\s+(?:fourth|fifth)\s+{type}\s+is\s+(?:the\s+)?"),
)

_STOP_LOOKAHEAD = (
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)


def _type_regex_fragment(type_phrase: str) -> str:
    words = [re.escape(word) for word in type_phrase.split()]
    return r"\s+".join(words)


def regexes_for_discovered_pattern(
    pattern: DiscoveredPattern,
) -> list[tuple[str, re.Pattern[str]]]:
    """Build deterministic extraction regexes for one discovered pattern."""
    compiled: list[tuple[str, re.Pattern[str]]] = []
    type_phrase = pattern.ordinal_type_phrase.strip()
    if not type_phrase:
        return compiled

    type_fragment = _type_regex_fragment(type_phrase)
    for label, prefix in _ORDINAL_PREFIXES:
        expression = prefix.format(type=type_fragment) + r"(.+?)" + _STOP_LOOKAHEAD
        compiled.append((label, re.compile(expression)))

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


def build_pattern_registry(schema: DocumentSchema) -> dict[str, list[str]]:
    """
    Build a category → pattern_name registry from discovered schema metadata.

    Example:
        {"architecture": ["most_common_architecture", "ordinal_architecture"], ...}
    """
    registry: dict[str, list[str]] = defaultdict(list)
    for pattern in schema.discovered_patterns:
        if pattern.pattern_name not in registry[pattern.category]:
            registry[pattern.category].append(pattern.pattern_name)
    return {category: sorted(names) for category, names in registry.items()}


def registry_patterns_for_category(
    schema: DocumentSchema,
    category: str,
) -> list[DiscoveredPattern]:
    """Return discovered pattern objects for one category."""
    return [
        pattern
        for pattern in schema.discovered_patterns
        if pattern.category == category
    ]
