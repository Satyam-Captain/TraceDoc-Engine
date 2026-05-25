"""Deterministic requirement/definition spans via spaCy blank English + EntityRuler."""

from __future__ import annotations

import os
from typing import Any

from spacy.language import Language
from spacy.lang.en import English
from spacy.pipeline import EntityRuler

_EXTRACTION_ENV = "TRACEDOC_EXTRACTION"

_RULER_PATTERNS: list[dict[str, Any]] = [
    {
        "label": "REQUIREMENT",
        "pattern": [{"LOWER": "must"}, {"IS_ALPHA": True, "OP": "+"}],
    },
    {
        "label": "REQUIREMENT",
        "pattern": [{"LOWER": "shall"}, {"IS_ALPHA": True, "OP": "+"}],
    },
    {
        "label": "DEFINITION",
        "pattern": [{"LOWER": "is"}, {"LOWER": "defined"}, {"LOWER": "as"}],
    },
]

_NLP: Language | None = None


def get_extraction_mode() -> str:
    """Return TRACEDOC_EXTRACTION (grammar, ruler, or both)."""
    return os.environ.get(_EXTRACTION_ENV, "grammar").lower()


def should_run_entity_ruler() -> bool:
    return get_extraction_mode() in ("ruler", "both")


def build_ruler_nlp() -> Language:
    """Blank English pipeline with EntityRuler only (no statistical models)."""
    global _NLP
    if _NLP is not None:
        return _NLP

    nlp = English()
    ruler: EntityRuler = nlp.add_pipe("entity_ruler")
    ruler.add_patterns(_RULER_PATTERNS)
    _NLP = nlp
    return nlp


def extract_ruler_entities(text: str) -> list[dict[str, Any]]:
    """
    Extract entity spans from text using EntityRuler patterns.

    Returns dicts with keys: label, text, start, end (character offsets).
    """
    if not text or not text.strip():
        return []

    doc = build_ruler_nlp()(text)
    entities: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()

    for ent in doc.ents:
        key = (ent.label_, ent.start_char, ent.end_char)
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            {
                "label": ent.label_,
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
            }
        )

    entities.sort(key=lambda item: (item["start"], item["label"], item["text"]))
    return entities


def ruler_debug_trace_lines(entities: list[dict[str, Any]]) -> list[str]:
    """Format ruler entities for QA debug traces."""
    lines = [
        f"entity_ruler_count={len(entities)}",
    ]
    for index, entity in enumerate(entities[:12]):
        preview = str(entity.get("text", "")).replace("\n", " ")[:120]
        lines.append(
            "entity_ruler_"
            f"{index}={entity.get('label')}|{entity.get('start')}-{entity.get('end')}|{preview!r}"
        )
    if len(entities) > 12:
        lines.append(f"entity_ruler_truncated={len(entities) - 12}")
    return lines


def append_entity_ruler_debug(
    debug_trace: list[str],
    text: str,
) -> list[dict[str, Any]]:
    """
    Append extraction mode and ruler entity lines to a debug trace.

    Does not modify grammar extraction results.
    """
    mode = get_extraction_mode()
    if not any(line.startswith("extraction_mode=") for line in debug_trace):
        debug_trace.append(f"extraction_mode={mode}")

    if not should_run_entity_ruler() or not text.strip():
        return []

    if any(line.startswith("entity_ruler_count=") for line in debug_trace):
        return []

    entities = extract_ruler_entities(text)
    debug_trace.extend(ruler_debug_trace_lines(entities))
    return entities
