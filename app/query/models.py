"""Data models for query interpretation."""

from dataclasses import dataclass, field
from typing import Any

INTENT_DEFINITION_LOOKUP = "DEFINITION_LOOKUP"
INTENT_WHERE_MENTIONED = "WHERE_MENTIONED"
INTENT_LIST_REQUEST = "LIST_REQUEST"
INTENT_COMPARISON = "COMPARISON"
INTENT_TABLE_LOOKUP = "TABLE_LOOKUP"
INTENT_REQUIREMENT_REFERENCE = "REQUIREMENT_REFERENCE"
INTENT_GENERAL_SEARCH = "GENERAL_SEARCH"

SUPPORTED_INTENT_TYPES = (
    INTENT_DEFINITION_LOOKUP,
    INTENT_WHERE_MENTIONED,
    INTENT_LIST_REQUEST,
    INTENT_COMPARISON,
    INTENT_TABLE_LOOKUP,
    INTENT_REQUIREMENT_REFERENCE,
    INTENT_GENERAL_SEARCH,
)


@dataclass
class QueryIntent:
    """Deterministic interpretation of a user question."""

    intent_type: str
    raw_question: str
    normalized_terms: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
