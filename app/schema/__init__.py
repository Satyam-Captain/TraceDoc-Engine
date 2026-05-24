"""Deterministic document schema discovery and registries."""

from app.schema.discovery import (
    discover_document_schema,
    format_category_normalization_trace,
    match_question_to_schema_category,
)
from app.schema.normalization import (
    extract_candidate_category,
    normalize_category_name,
    normalize_heading_text,
    singularize_term,
)
from app.schema.graph_candidates import discover_graph_candidates
from app.schema.models import (
    DiscoveredCategory,
    DiscoveredPattern,
    DocumentSchema,
    GraphCandidate,
)
from app.schema.grammar_discovery import (
    discover_extraction_grammars,
    discover_grammars_for_categories,
)
from app.schema.registry import (
    build_category_registry,
    build_pattern_registry,
    primary_grammar_for_category,
    regexes_for_discovered_pattern,
    registry_patterns_for_category,
)

__all__ = [
    "DiscoveredCategory",
    "DiscoveredPattern",
    "DocumentSchema",
    "GraphCandidate",
    "build_category_registry",
    "build_pattern_registry",
    "discover_document_schema",
    "discover_extraction_grammars",
    "discover_grammars_for_categories",
    "discover_graph_candidates",
    "extract_candidate_category",
    "format_category_normalization_trace",
    "match_question_to_schema_category",
    "normalize_category_name",
    "normalize_heading_text",
    "singularize_term",
    "primary_grammar_for_category",
    "regexes_for_discovered_pattern",
    "registry_patterns_for_category",
]
