"""Query interpretation orchestration."""

from __future__ import annotations

from app.indexing.normalizer import normalize_token
from app.indexing.tokenizer import tokenize
from app.query.models import (
    INTENT_DEFINITION_LOOKUP,
    INTENT_GENERAL_SEARCH,
    INTENT_REQUIREMENT_REFERENCE,
    QueryIntent,
)
from app.query.rules import classify_intent, extract_entities


def interpret_query(question: str) -> QueryIntent:
    """
    Interpret a user question using deterministic string and regex rules.
    """
    raw_question = question or ""
    stripped = raw_question.strip()

    if not stripped:
        return QueryIntent(
            intent_type=INTENT_GENERAL_SEARCH,
            raw_question=raw_question,
            normalized_terms=[],
            entities=[],
            filters={},
            explanation="Empty question; using general search intent.",
        )

    entities = extract_entities(stripped)
    intent_type, explanation, filters = classify_intent(stripped, entities)
    normalized_terms = [
        normalize_token(token) for token in tokenize(stripped) if normalize_token(token)
    ]

    return QueryIntent(
        intent_type=intent_type,
        raw_question=raw_question,
        normalized_terms=normalized_terms,
        entities=entities,
        filters=filters,
        explanation=explanation,
    )


def build_retrieval_query(question: str, intent: QueryIntent) -> str:
    """Apply light deterministic query shaping before lexical retrieval."""
    if intent.intent_type == INTENT_DEFINITION_LOOKUP:
        return f"{question} definition means refers to"
    if intent.intent_type == INTENT_REQUIREMENT_REFERENCE:
        requirement_ids = intent.filters.get("requirement_ids", [])
        if requirement_ids:
            return f"{question} {' '.join(requirement_ids)}"
    return question


def compose_intent_explanation(intent: QueryIntent, base_explanation: str) -> str:
    """Combine intent and answer explanations for display."""
    parts = [part for part in (intent.explanation, base_explanation) if part]
    return " ".join(parts)
