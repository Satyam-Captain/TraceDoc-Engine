"""Deterministic document schema discovery and registries."""

from app.schema.discovery import (
    discover_document_schema,
    match_question_to_schema_category,
    normalize_category_name,
)
from app.schema.graph_candidates import discover_graph_candidates
from app.schema.models import (
    DiscoveredCategory,
    DiscoveredPattern,
    DocumentSchema,
    GraphCandidate,
)
from app.schema.registry import (
    build_pattern_registry,
    regexes_for_discovered_pattern,
    registry_patterns_for_category,
)

__all__ = [
    "DiscoveredCategory",
    "DiscoveredPattern",
    "DocumentSchema",
    "GraphCandidate",
    "build_pattern_registry",
    "discover_document_schema",
    "discover_graph_candidates",
    "match_question_to_schema_category",
    "normalize_category_name",
    "regexes_for_discovered_pattern",
    "registry_patterns_for_category",
]
