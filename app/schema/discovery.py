"""Deterministic document schema discovery."""

from __future__ import annotations

import re
from collections import defaultdict

from app.schema.graph_candidates import discover_graph_candidates
from app.schema.models import (
    DiscoveredCategory,
    DiscoveredPattern,
    DocumentSchema,
)
from app.structure.models import DocumentChunk, DocumentSection

_HEADING_CATEGORY_RULES: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"\bexisting\s+architectures?\b", re.I), "architecture", 0.95),
    (re.compile(r"\barchitectures?\b", re.I), "architecture", 0.80),
    (re.compile(r"\bdesign\s+patterns?\b", re.I), "design_pattern", 0.95),
    (re.compile(r"\bopen[- ]source\s+building\s+blocks?\b", re.I), "building_block", 0.92),
    (re.compile(r"\bbuilding\s+blocks?\b", re.I), "building_block", 0.75),
    (re.compile(r"\bcommon\s+capabilities?\b", re.I), "capability", 0.92),
    (re.compile(r"\bcapabilities?\b", re.I), "capability", 0.70),
    (re.compile(r"\bfuture\s+improvements?\b", re.I), "improvement", 0.92),
    (re.compile(r"\bimprovements?\b", re.I), "improvement", 0.65),
    (re.compile(r"\brequirements?\b", re.I), "requirement", 0.80),
    (re.compile(r"\blimitations?\b", re.I), "limitation", 0.80),
    (re.compile(r"\bevaluation\b", re.I), "evaluation", 0.75),
    (re.compile(r"\bconclusion\b", re.I), "conclusion", 0.75),
    (re.compile(r"\btechnologies?\b", re.I), "technology", 0.70),
    (re.compile(r"\bworkflows?\b", re.I), "workflow", 0.70),
    (re.compile(r"\bprinciples?\b", re.I), "principle", 0.70),
    (re.compile(r"\bcomponents?\b", re.I), "component", 0.70),
    (re.compile(r"\bphases?\b", re.I), "phase", 0.70),
)

_ORDINAL_FIRST = re.compile(
    r"(?i)the\s+first\s+(.+?)\s+is\s+(?:the\s+)?(.+?)"
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)
_ORDINAL_SECOND = re.compile(
    r"(?i)(?:a|the)\s+second\s+(.+?)\s+is\s+(?:the\s+)?(.+?)"
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)
_ORDINAL_THIRD = re.compile(
    r"(?i)(?:a|the)\s+third\s+(.+?)\s+is\s+(?:the\s+)?(.+?)"
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)
_ORDINAL_FOURTH = re.compile(
    r"(?i)(?:a|the)\s+(?:fourth|fifth)\s+(.+?)\s+is\s+(?:the\s+)?(.+?)"
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)
_MOST_COMMON_IS = re.compile(
    r"(?i)the\s+most\s+common\b.+?\bis\s+(?:the\s+)?(.+?)"
    r"(?=\s*[:;.!?]|(?:\s+)(?:which|that|where|with)\b|$)"
)
_MEANS = re.compile(
    r"(?i)^(.{3,80}?)\s+means\s+(.{3,80}?)(?:[.!?]|$)"
)
_REFERS_TO = re.compile(
    r"(?i)^(.{3,80}?)\s+refers\s+to\s+(.{3,80}?)(?:[.!?]|$)"
)
_CONTAINS = re.compile(
    r"(?i)^(.{3,80}?)\s+contains\s+(.{3,80}?)(?:[.!?]|$)"
)
_DEPENDS_ON = re.compile(
    r"(?i)^(.{3,80}?)\s+depends\s+on\s+(.{3,80}?)(?:[.!?]|$)"
)


def normalize_category_name(title: str) -> str:
    """Normalize a heading into a stable category key."""
    cleaned = title.strip().lower()
    cleaned = cleaned.replace("-", " ")
    cleaned = re.sub(r"[^a-z0-9\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for suffix, replacement in (
        ("ies", "y"),
        ("ches", "ch"),
        ("shes", "sh"),
        ("xes", "x"),
        ("ses", "s"),
        ("s", ""),
    ):
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 2:
            cleaned = cleaned[: -len(suffix)] + replacement
            break
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "general"


def category_from_heading(title: str) -> tuple[str, float] | None:
    """Map a section heading to a semantic category when rules match."""
    for pattern, category, score in _HEADING_CATEGORY_RULES:
        if pattern.search(title):
            return category, score
    return None


def _canonical_type_phrase(type_phrase: str) -> str:
    return re.sub(r"\s+", " ", type_phrase.strip().lower())


def _pattern_name_for_ordinal(category: str, type_phrase: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", type_phrase.lower()).strip("_")
    if not slug:
        return f"ordinal_{category}"
    return f"ordinal_{slug}"


def _discover_categories_from_chunk_headings(
    chunks: list[DocumentChunk],
) -> list[DiscoveredCategory]:
    """Infer categories from short standalone lines at chunk starts."""
    discovered: dict[str, DiscoveredCategory] = {}
    for chunk in chunks:
        first_line = chunk.text.split("\n", maxsplit=1)[0].strip()
        if not first_line or len(first_line) > 100:
            continue
        if first_line.endswith((".", "?", "!")) and " is " in first_line.lower():
            continue
        mapping = category_from_heading(first_line)
        if mapping is None:
            continue
        category_key, score = mapping
        if category_key in discovered and discovered[category_key].confidence_score >= score:
            continue
        discovered[category_key] = DiscoveredCategory(
            name=category_key.replace("_", " "),
            normalized_name=category_key,
            source_section=first_line,
            confidence_score=score,
        )
    return list(discovered.values())


def _discover_categories_from_sections(
    sections: list[DocumentSection],
) -> list[DiscoveredCategory]:
    discovered: dict[str, DiscoveredCategory] = {}
    for section in sections:
        mapping = category_from_heading(section.title)
        if mapping is None:
            continue
        category_key, score = mapping
        if category_key in discovered:
            existing = discovered[category_key]
            if score > existing.confidence_score:
                discovered[category_key] = DiscoveredCategory(
                    name=category_key.replace("_", " "),
                    normalized_name=category_key,
                    source_section=section.title,
                    confidence_score=score,
                    discovered_patterns=list(existing.discovered_patterns),
                )
            continue
        discovered[category_key] = DiscoveredCategory(
            name=category_key.replace("_", " "),
            normalized_name=category_key,
            source_section=section.title,
            confidence_score=score,
        )
    return list(discovered.values())


def _section_category_map(
    sections: list[DocumentSection],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for section in sections:
        result = category_from_heading(section.title)
        if result is None:
            continue
        mapping[section.section_id] = result[0]
        mapping[section.title.lower()] = result[0]
    return mapping


def _category_for_chunk(
    chunk: DocumentChunk,
    sections: list[DocumentSection],
    section_categories: dict[str, str],
    category_by_section_title: dict[str, str],
) -> str:
    section_key = (chunk.section_title or "").lower()
    if chunk.section_id and chunk.section_id in section_categories:
        return section_categories[chunk.section_id]
    if section_key in category_by_section_title:
        return category_by_section_title[section_key]

    for section in sections:
        result = category_from_heading(section.title)
        if result is None:
            continue
        if chunk.start_line < section.start_line or chunk.end_line > section.end_line:
            continue
        if chunk.start_line >= section.start_line and chunk.end_line <= section.end_line:
            return result[0]
    return ""


def _discover_patterns_from_chunks(
    sections: list[DocumentSection],
    chunks: list[DocumentChunk],
    categories: list[DiscoveredCategory],
) -> list[DiscoveredPattern]:
    section_categories = _section_category_map(sections)
    category_by_section_title = {
        category.source_section.lower(): category.normalized_name
        for category in categories
    }
    if categories and not sections:
        default_category = max(categories, key=lambda item: item.confidence_score)
        section_categories.setdefault("__default__", default_category.normalized_name)

    hits: dict[tuple[str, str], dict[str, object]] = {}
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)

    for chunk in chunks:
        category = _category_for_chunk(
            chunk,
            sections,
            section_categories,
            category_by_section_title,
        )
        if not category and "__default__" in section_categories:
            category = section_categories["__default__"]
        if not category:
            continue

        text = chunk.text
        for regex, ordinal_label in (
            (_ORDINAL_FIRST, "the first"),
            (_ORDINAL_SECOND, "second"),
            (_ORDINAL_THIRD, "third"),
            (_ORDINAL_FOURTH, "fourth"),
        ):
            for match in regex.finditer(text):
                type_phrase = _canonical_type_phrase(match.group(1))
                key = (category, type_phrase)
                entry = hits.setdefault(
                    key,
                    {"count": 0, "triggers": set(), "ordinal_type_phrase": type_phrase},
                )
                entry["count"] = int(entry["count"]) + 1
                triggers = entry["triggers"]
                assert isinstance(triggers, set)
                triggers.add(f"{ordinal_label} {type_phrase} is")
                sentence = match.group(0).strip()
                if sentence and len(examples[key]) < 3:
                    examples[key].append(sentence[:200])

        if category == "architecture":
            for match in _MOST_COMMON_IS.finditer(text):
                key = (category, "architecture")
                entry = hits.setdefault(
                    key,
                    {
                        "count": 0,
                        "triggers": set(),
                        "ordinal_type_phrase": "architecture",
                    },
                )
                entry["count"] = int(entry["count"]) + 1
                triggers = entry["triggers"]
                assert isinstance(triggers, set)
                triggers.add("the most common architecture is")
                sentence = match.group(0).strip()
                if sentence and len(examples[key]) < 3:
                    examples[key].append(sentence[:200])

    patterns: list[DiscoveredPattern] = []
    for (category, type_phrase), entry in sorted(hits.items()):
        count = int(entry["count"])
        if count < 1:
            continue
        triggers = entry["triggers"]
        assert isinstance(triggers, set)
        if category == "architecture" and type_phrase == "architecture":
            pattern_name = "most_common_architecture"
        else:
            pattern_name = f"ordinal_{category}"

        patterns.append(
            DiscoveredPattern(
                pattern_name=pattern_name,
                category=category,
                trigger_phrases=sorted(triggers),
                example_sentences=examples[(category, type_phrase)],
                ordinal_type_phrase=str(entry["ordinal_type_phrase"]),
            )
        )

    return patterns


def _attach_patterns_to_categories(
    categories: list[DiscoveredCategory],
    patterns: list[DiscoveredPattern],
) -> None:
    by_category: dict[str, list[str]] = defaultdict(list)
    for pattern in patterns:
        by_category[pattern.category].append(pattern.pattern_name)
    for category in categories:
        category.discovered_patterns = sorted(by_category.get(category.normalized_name, []))


def _merge_categories(
    *category_groups: list[DiscoveredCategory],
) -> list[DiscoveredCategory]:
    merged: dict[str, DiscoveredCategory] = {}
    for group in category_groups:
        for category in group:
            existing = merged.get(category.normalized_name)
            if existing is None or category.confidence_score > existing.confidence_score:
                merged[category.normalized_name] = category
    return list(merged.values())


def discover_document_schema(
    document_id: int,
    sections: list[DocumentSection],
    chunks: list[DocumentChunk],
) -> DocumentSchema:
    """Infer semantic categories, extraction styles, and graph candidates."""
    categories = _merge_categories(
        _discover_categories_from_sections(sections),
        _discover_categories_from_chunk_headings(chunks),
    )
    patterns = _discover_patterns_from_chunks(sections, chunks, categories)
    _attach_patterns_to_categories(categories, patterns)
    graph_candidates = discover_graph_candidates(chunks)

    return DocumentSchema(
        document_id=document_id,
        categories=categories,
        discovered_patterns=patterns,
        graph_candidates=graph_candidates,
        discovered_sections=[section.title for section in sections],
    )


def match_question_to_schema_category(
    question: str,
    schema: DocumentSchema,
) -> DiscoveredCategory | None:
    """Route a question to a discovered category when phrasing matches."""
    lower = question.lower()
    best: DiscoveredCategory | None = None
    best_score = 0.0

    for category in schema.categories:
        label = category.normalized_name.replace("_", " ")
        plural = label + "s" if not label.endswith("s") else label
        matched = False
        if label in lower or plural in lower:
            matched = True
        if category.source_section.lower() in lower:
            matched = True
        if not matched:
            continue
        score = category.confidence_score + (0.1 * len(label))
        if score > best_score:
            best = category
            best_score = score

    return best
