"""Deterministic graph triple candidate extraction."""

from __future__ import annotations

import re

from app.evidence.phrase_cleanup import clean_extracted_phrase
from app.schema.models import GraphCandidate
from app.structure.models import DocumentChunk

_SUPPORTED_RELATIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "uses",
        re.compile(
            r"(?i)^(.{3,80}?)\s+uses\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "contains",
        re.compile(
            r"(?i)^(.{3,80}?)\s+contains\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "depends on",
        re.compile(
            r"(?i)^(.{3,80}?)\s+depends\s+on\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "refers to",
        re.compile(
            r"(?i)^(.{3,80}?)\s+refers\s+to\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "links to",
        re.compile(
            r"(?i)^(.{3,80}?)\s+links\s+to\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "includes",
        re.compile(
            r"(?i)^(.{3,80}?)\s+includes\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "consists of",
        re.compile(
            r"(?i)^(.{3,80}?)\s+consists\s+of\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
    (
        "implements",
        re.compile(
            r"(?i)^(.{3,80}?)\s+implements\s+(.{3,80}?)(?:[.!?]|$)"
        ),
    ),
)

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)
_JUNK_PATTERN = re.compile(
    r"\b(the|and|or|but|if|when|where|which|that)\s+(the|and|or)\b",
    re.IGNORECASE,
)


def _split_chunk_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _is_valid_graph_endpoints(subject: str, obj: str, sentence: str) -> bool:
    if len(subject) < 3 or len(obj) < 3:
        return False
    if len(subject) > 80 or len(obj) > 80:
        return False
    if _URL_PATTERN.search(subject) or _URL_PATTERN.search(obj):
        return False
    if _JUNK_PATTERN.search(subject) or _JUNK_PATTERN.search(obj):
        return False
    # Endpoints must appear in the source sentence.
    sentence_lower = sentence.lower()
    return subject.lower() in sentence_lower and obj.lower() in sentence_lower


def discover_graph_candidates(chunks: list[DocumentChunk]) -> list[GraphCandidate]:
    """Extract deterministic subject-relation-object candidates from chunk text."""
    candidates: list[GraphCandidate] = []
    seen: set[tuple[str, str, str]] = set()

    for chunk in chunks:
        for sentence in _split_chunk_sentences(chunk.text):
            normalized_sentence = re.sub(r"\s+", " ", sentence).strip()
            if not normalized_sentence:
                continue

            for relation, pattern in _SUPPORTED_RELATIONS:
                match = pattern.match(normalized_sentence)
                if not match:
                    continue

                subject = clean_extracted_phrase(match.group(1))
                obj = clean_extracted_phrase(match.group(2))
                if not _is_valid_graph_endpoints(subject, obj, normalized_sentence):
                    continue

                key = (subject.lower(), relation, obj.lower())
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    GraphCandidate(
                        subject=subject,
                        relation=relation,
                        object=obj,
                        source_sentence=normalized_sentence,
                        confidence_score=0.85,
                    )
                )

    return candidates
