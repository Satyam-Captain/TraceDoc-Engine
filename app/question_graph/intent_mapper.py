"""Map query intents to default question-graph shapes."""

from __future__ import annotations

from app.query.models import (
    INTENT_DEFINITION_LOOKUP,
    INTENT_EXPLANATION_LOOKUP,
    INTENT_GENERAL_SEARCH,
    INTENT_LIST_REQUEST,
    INTENT_WHERE_MENTIONED,
    QueryIntent,
)

DEFAULT_RELATION_BY_INTENT: dict[str, str] = {
    INTENT_WHERE_MENTIONED: "mentions",
    INTENT_LIST_REQUEST: "mentions",
}


def intent_type_for_graph(intent: QueryIntent | None) -> str:
    """Return intent type string for a question graph."""
    if intent is None:
        return INTENT_GENERAL_SEARCH
    return intent.intent_type


def fallback_relation_for_intent(intent: QueryIntent | None) -> str | None:
    """Return a weak default relation hint from intent when patterns do not match."""
    if intent is None:
        return None
    return DEFAULT_RELATION_BY_INTENT.get(intent.intent_type)


def is_definition_intent(intent: QueryIntent | None) -> bool:
    if intent is None:
        return False
    return intent.intent_type in {
        INTENT_DEFINITION_LOOKUP,
        INTENT_EXPLANATION_LOOKUP,
    }
