"""Deterministic semantic heading and category normalization."""

from __future__ import annotations

import re

_MIN_CATEGORY_CONFIDENCE = 0.65

_WEAK_SUFFIX_PHRASES: tuple[str, ...] = (
    "for implementation",
    "for production",
    "overview",
    "details",
    "considerations",
    "examples",
    "notes",
    "summary",
    "introduction",
    "background",
)

_WEAK_ONLY_HEADINGS: frozenset[str] = frozenset(
    {
        "overview",
        "details",
        "summary",
        "introduction",
        "background",
        "notes",
        "examples",
        "appendix",
    }
)

# Longest phrases first when matching.
_SEMANTIC_PHRASE_MAP: tuple[tuple[str, str], ...] = (
    ("open source building blocks", "building_block"),
    ("open-source building blocks", "building_block"),
    ("existing architectures", "architecture"),
    ("design patterns", "design_pattern"),
    ("design pattern", "design_pattern"),
    ("building blocks", "building_block"),
    ("building block", "building_block"),
    ("knowledge graph", "knowledge_graph"),
    ("common capabilities", "capability"),
    ("future improvements", "improvement"),
    ("evaluation checklist", "evaluation"),
    ("architectures", "architecture"),
    ("architecture", "architecture"),
    ("capabilities", "capability"),
    ("capability", "capability"),
    ("requirements", "requirement"),
    ("requirement", "requirement"),
    ("limitations", "limitation"),
    ("limitation", "limitation"),
    ("improvements", "improvement"),
    ("improvement", "improvement"),
    ("technologies", "technology"),
    ("technology", "technology"),
    ("principles", "principle"),
    ("principle", "principle"),
    ("workflows", "workflow"),
    ("workflow", "workflow"),
    ("patterns", "pattern"),
    ("pattern", "pattern"),
    ("components", "component"),
    ("component", "component"),
    ("phases", "phase"),
    ("phase", "phase"),
    ("evaluation", "evaluation"),
    ("conclusion", "conclusion"),
)


def normalize_heading_text(text: str) -> str:
    """Lowercase heading text with hyphen and punctuation normalization."""
    cleaned = text.strip().lower()
    cleaned = cleaned.replace("-", " ")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for suffix in _WEAK_SUFFIX_PHRASES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned


def singularize_term(term: str) -> str:
    """Singularize one token deterministically."""
    lower = term.lower()
    if len(lower) <= 2:
        return lower
    if lower.endswith("ies") and len(lower) > 4:
        return lower[:-3] + "y"
    if lower.endswith("ches") and len(lower) > 5:
        return lower[:-2]
    if lower.endswith("shes") and len(lower) > 5:
        return lower[:-2]
    if lower.endswith("xes") and len(lower) > 4:
        return lower[:-2]
    if lower.endswith("ses") and len(lower) > 4:
        return lower[:-2]
    if lower.endswith("s") and not lower.endswith("ss"):
        return lower[:-1]
    return lower


def extract_candidate_category(text: str) -> str | None:
    """
    Derive a semantic category key from heading or question text.

    Returns None for weak/non-semantic headings such as "Overview".
    """
    heading = normalize_heading_text(text)
    if not heading or heading in _WEAK_ONLY_HEADINGS:
        return None

    for phrase, category in _SEMANTIC_PHRASE_MAP:
        if phrase in heading:
            return category

    tokens = [singularize_term(token) for token in heading.split() if token]
    if not tokens:
        return None

    joined = " ".join(tokens)
    for phrase, category in _SEMANTIC_PHRASE_MAP:
        if phrase in joined:
            return category

    if len(tokens) == 1 and tokens[0] not in _WEAK_ONLY_HEADINGS:
        return tokens[0]

    return None


def normalize_category_name(text: str) -> str:
    """Normalize text to a stable underscore category identifier."""
    category = extract_candidate_category(text)
    if category:
        return category

    heading = normalize_heading_text(text)
    if not heading:
        return "general"

    tokens = [singularize_term(token) for token in heading.split() if token]
    return "_".join(tokens) if tokens else "general"


def category_confidence_from_heading(text: str, category: str) -> float:
    """Score how confidently a heading maps to a semantic category."""
    heading = normalize_heading_text(text)
    if not heading or heading in _WEAK_ONLY_HEADINGS:
        return 0.2

    for phrase, mapped in _SEMANTIC_PHRASE_MAP:
        if mapped != category:
            continue
        if heading == phrase:
            return 0.95
        if heading.startswith(phrase + " "):
            return 0.90
        if phrase in heading:
            return 0.85

    extracted = extract_candidate_category(text)
    if extracted == category:
        return 0.75
    return 0.4


def meets_category_confidence_threshold(confidence: float) -> bool:
    return confidence >= _MIN_CATEGORY_CONFIDENCE
