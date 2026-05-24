"""Resolve the semantic category targeted by a user question."""

from __future__ import annotations

from app.schema.models import DiscoveredCategory, DocumentSchema
from app.schema.normalization import extract_candidate_category


def _is_plausible_category_key(category: str) -> bool:
    if not category or category == "general":
        return False
    if category.isdigit():
        return False
    if len(category) <= 1:
        return False
    return True


def filter_plausible_categories(
    categories: list[DiscoveredCategory],
) -> list[DiscoveredCategory]:
    """Drop numeric or weak category keys from a discovered schema."""
    return [
        category
        for category in categories
        if _is_plausible_category_key(category.normalized_name)
    ]


def _section_title_for_category(
    schema: DocumentSchema,
    category: str,
) -> str:
    for discovered in schema.categories:
        if discovered.normalized_name == category:
            return discovered.source_section
    for section_title in schema.discovered_sections:
        if extract_candidate_category(section_title) == category:
            return section_title
    if category == "design_pattern":
        for section_title in schema.discovered_sections:
            if "design pattern" in section_title.lower():
                return section_title
    if category == "architecture":
        for section_title in schema.discovered_sections:
            if "architecture" in section_title.lower():
                return section_title
    return ""


def resolve_query_target_category(
    question: str,
    schema: DocumentSchema | None = None,
    *,
    selected_section_title: str = "",
) -> str | None:
    """
    Determine the extraction category for a question.

    Design-pattern questions always resolve to design_pattern, never generic pattern.
    """
    lower = question.lower()

    if "design" in lower and "pattern" in lower:
        return "design_pattern"
    if "architect" in lower:
        return "architecture"

    inferred = extract_candidate_category(question)
    if inferred == "pattern" and ("design" in lower or "design pattern" in lower):
        return "design_pattern"

    if selected_section_title:
        section_category = extract_candidate_category(selected_section_title)
        if section_category:
            return section_category

    if inferred:
        return inferred

    if schema is None:
        return None

    if selected_section_title:
        section_category = extract_candidate_category(selected_section_title)
        if section_category:
            return section_category

    return None


def match_question_to_schema_category(
    question: str,
    schema: DocumentSchema,
    *,
    selected_section_title: str = "",
) -> DiscoveredCategory | None:
    """Route a question to a discovered category when phrasing matches."""
    lower = question.lower()
    target = resolve_query_target_category(
        question,
        schema,
        selected_section_title=selected_section_title,
    )

    if target is not None:
        for category in schema.categories:
            if category.normalized_name == target:
                return category

        source_section = _section_title_for_category(schema, target)
        if not source_section and selected_section_title:
            source_section = selected_section_title
        return DiscoveredCategory(
            name=target.replace("_", " "),
            normalized_name=target,
            source_section=source_section,
            confidence_score=0.95,
        )

    best: DiscoveredCategory | None = None
    best_score = 0.0

    for category in schema.categories:
        if not _is_plausible_category_key(category.normalized_name):
            continue
        label = category.normalized_name.replace("_", " ")
        plural = label + "s" if not label.endswith("s") else label
        matched = False
        if label in lower or plural in lower:
            matched = True
        if category.normalized_name == "pattern" and "design" in lower:
            matched = False
        if category.source_section.lower() in lower:
            matched = True
        if not matched:
            continue
        score = category.confidence_score + (0.1 * len(label))
        if score > best_score:
            best = category
            best_score = score

    return best
