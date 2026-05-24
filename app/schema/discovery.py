"""Deterministic document schema discovery."""

from __future__ import annotations

from collections import defaultdict

from app.schema.grammar_discovery import discover_grammars_for_categories
from app.schema.graph_candidates import discover_graph_candidates
from app.schema.models import (
    DiscoveredCategory,
    DiscoveredPattern,
    DocumentSchema,
)
from app.schema.normalization import (
    category_confidence_from_heading,
    extract_candidate_category,
    meets_category_confidence_threshold,
    normalize_category_name,
    normalize_heading_text,
)
from app.structure.models import DocumentChunk, DocumentSection

def category_from_heading(title: str) -> tuple[str, float] | None:
    """Map a section heading to a semantic category using normalization rules."""
    category = extract_candidate_category(title)
    if category is None:
        return None
    score = category_confidence_from_heading(title, category)
    if not meets_category_confidence_threshold(score):
        return None
    return category, score


def _discover_categories_from_chunk_headings(
    chunks: list[DocumentChunk],
) -> list[DiscoveredCategory]:
    """Infer categories from short standalone lines at chunk starts."""
    discovered: dict[str, DiscoveredCategory] = {}
    for chunk in chunks:
        first_line = chunk.text.split("\n", maxsplit=1)[0].strip()
        if not first_line or len(first_line) > 120:
            continue
        if first_line.endswith((".", "?", "!")) and " is " in first_line.lower():
            continue
        mapping = category_from_heading(first_line)
        if mapping is None:
            continue
        category_key, score = mapping
        existing = discovered.get(category_key)
        if existing is not None and existing.confidence_score >= score:
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
        existing = discovered.get(category_key)
        if existing is not None and existing.confidence_score >= score:
            continue
        discovered[category_key] = DiscoveredCategory(
            name=category_key.replace("_", " "),
            normalized_name=category_key,
            source_section=section.title,
            confidence_score=score,
            discovered_patterns=list(existing.discovered_patterns) if existing else [],
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
        normalized = normalize_heading_text(section.title)
        mapping[normalized] = result[0]
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

    first_line = chunk.text.split("\n", maxsplit=1)[0].strip()
    line_category = extract_candidate_category(first_line)
    if line_category:
        return line_category

    for section in sections:
        result = category_from_heading(section.title)
        if result is None:
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
    category_by_section_title.update(
        {
            normalize_heading_text(category.source_section): category.normalized_name
            for category in categories
        }
    )

    if categories and not sections:
        default_category = max(categories, key=lambda item: item.confidence_score)
        section_categories.setdefault("__default__", default_category.normalized_name)

    def resolve_category(chunk: DocumentChunk) -> str:
        category = _category_for_chunk(
            chunk,
            sections,
            section_categories,
            category_by_section_title,
        )
        if not category and "__default__" in section_categories:
            return section_categories["__default__"]
        return category

    return discover_grammars_for_categories(categories, chunks, resolve_category)


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
    question_category = extract_candidate_category(question)
    if question_category == "pattern" and (
        "design pattern" in lower or "design patterns" in lower
    ):
        question_category = "design_pattern"

    if question_category is not None:
        for category in schema.categories:
            if category.normalized_name == question_category:
                return category
        if question_category == "design_pattern":
            for category in schema.categories:
                if category.normalized_name == "design_pattern":
                    return category

    best: DiscoveredCategory | None = None
    best_score = 0.0

    for category in schema.categories:
        label = category.normalized_name.replace("_", " ")
        plural = label + "s" if not label.endswith("s") else label
        matched = False
        if label in lower or plural in lower:
            matched = True
        if "design" in lower and "pattern" in lower and category.normalized_name == "design_pattern":
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


def format_category_normalization_trace(categories: list[DiscoveredCategory]) -> list[str]:
    """Debug lines for heading → category normalization."""
    lines: list[str] = []
    for category in categories:
        lines.append(
            f"normalized_heading={category.source_section!r} -> "
            f"{category.normalized_name!r}"
        )
        lines.append(f"schema_category_confidence={category.confidence_score:.2f}")
    return lines
