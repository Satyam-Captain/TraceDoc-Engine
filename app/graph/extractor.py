"""Deterministic relation and entity extraction for the knowledge graph."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.evidence.phrase_cleanup import clean_extracted_phrase

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
_ORDINAL_IS = re.compile(
    r"(?i)(?:the\s+)?(?:first|second|third|fourth|fifth|sixth)\s+.+?\s+is\s+",
)
_ADJECTIVE_OBJECTS = frozenset(
    {
        "nice",
        "good",
        "bad",
        "warm",
        "cold",
        "hot",
        "new",
        "old",
        "large",
        "small",
        "high",
        "low",
    }
)

_RELATION_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "uses",
        "uses",
        re.compile(r"(?i)^(.{3,80}?)\s+uses\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "contains",
        "contains",
        re.compile(r"(?i)^(.{3,80}?)\s+contains\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "includes",
        "includes",
        re.compile(r"(?i)^(.{3,80}?)\s+includes\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "depends_on",
        "depends on",
        re.compile(r"(?i)^(.{3,80}?)\s+depends\s+on\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "refers_to",
        "refers to",
        re.compile(r"(?i)^(.{3,80}?)\s+refers\s+to\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "links_to",
        "links to",
        re.compile(r"(?i)^(.{3,80}?)\s+links\s+to\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "implements",
        "implements",
        re.compile(r"(?i)^(.{3,80}?)\s+implements\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "contains",
        "consists of",
        re.compile(r"(?i)^(.{3,80}?)\s+consists\s+of\s+(.+?)(?:[.!?]|$)"),
    ),
    (
        "is_a",
        "is",
        re.compile(
            r"(?i)^(.{3,80}?)\s+is\s+(?:the\s+)?(.+?)(?:[.!?]|$)"
        ),
    ),
)


@dataclass(frozen=True)
class ExtractedRelation:
    """One subject-relation-object triple from a sentence."""

    subject: str
    relation: str
    object: str
    source_sentence: str
    confidence_score: float = 0.85


def split_object_list(object_text: str) -> list[str]:
    """Split comma- or 'and'-separated object phrases."""
    stripped = object_text.strip().rstrip(".")
    if not stripped:
        return []

    parts = re.split(r",|\band\b", stripped, flags=re.IGNORECASE)
    objects: list[str] = []
    for part in parts:
        cleaned = clean_extracted_phrase(part)
        if cleaned:
            objects.append(cleaned)
    return objects


def _is_valid_endpoint(value: str, sentence: str) -> bool:
    if len(value) < 3 or len(value) > 80:
        return False
    if _URL_PATTERN.search(value):
        return False
    sentence_lower = sentence.lower()
    return value.lower() in sentence_lower


def extract_relations_from_sentence(sentence: str) -> list[ExtractedRelation]:
    """Extract deterministic relations from one sentence."""
    normalized = re.sub(r"\s+", " ", sentence).strip()
    if not normalized:
        return []

    relations: list[ExtractedRelation] = []
    seen: set[tuple[str, str, str]] = set()

    for relation_key, _display, pattern in _RELATION_RULES:
        match = pattern.match(normalized)
        if not match:
            continue

        if relation_key == "is_a" and _ORDINAL_IS.search(normalized):
            continue

        subject = clean_extracted_phrase(match.group(1))
        object_raw = match.group(2).strip()
        if not _is_valid_endpoint(subject, normalized):
            continue

        objects = (
            split_object_list(object_raw)
            if relation_key in {"contains", "includes"}
            else [clean_extracted_phrase(object_raw)]
        )

        for obj in objects:
            if not _is_valid_endpoint(obj, normalized):
                continue
            if relation_key == "is_a":
                if " and " in obj.lower() or len(obj) > 60:
                    continue
                object_words = obj.lower().split()
                if len(object_words) < 2 and object_words[0] in _ADJECTIVE_OBJECTS:
                    continue
                if len(object_words) <= 2 and any(
                    word in _ADJECTIVE_OBJECTS for word in object_words
                ):
                    continue
            key = (subject.lower(), relation_key, obj.lower())
            if key in seen:
                continue
            seen.add(key)
            relations.append(
                ExtractedRelation(
                    subject=subject,
                    relation=relation_key,
                    object=obj,
                    source_sentence=normalized,
                )
            )

    return relations


def extract_capitalized_phrases(sentence: str) -> list[str]:
    """
    Extract conservative capitalized noun phrases present in the sentence.

    Used only as supplemental entity hints alongside grammar/schema entities.
    """
    phrases: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"\b([A-Z][A-Za-z0-9]*(?:\s+(?:and\s+)?[A-Z][A-Za-z0-9]*){0,5})\b"
    )
    for match in pattern.finditer(sentence):
        phrase = clean_extracted_phrase(match.group(1))
        if len(phrase) < 3 or len(phrase) > 60:
            continue
        if phrase.lower() not in sentence.lower():
            continue
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        phrases.append(phrase)
    return phrases


def stable_relation_id(subject: str, relation: str, obj: str) -> str:
    payload = f"{subject}|{relation}|{obj}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
