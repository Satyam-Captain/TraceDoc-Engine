"""Deterministic structured answers composed only from evidence text."""

from __future__ import annotations

import re

from app.evidence.models import EvidenceCard

_PLURAL_TARGETS = (
    "architectures",
    "patterns",
    "steps",
    "capabilities",
    "approaches",
    "options",
    "types",
    "categories",
    "families",
    "models",
)

_ARCHITECTURE_PHRASES: tuple[tuple[str, str], ...] = (
    ("enterprise search stack", "Enterprise search stack"),
    ("classic qa pipeline", "Classic QA pipeline"),
    ("ontology and knowledge-graph stack", "Ontology and knowledge-graph stack"),
    ("traceability and citation graph", "Traceability and citation graph"),
)

_NUMBERED_LINE = re.compile(r"^\s*\d+[\.\)]\s+(.+)$")
_BULLET_LINE = re.compile(r"^\s*[-*•]\s+(.+)$")
_THE_ORDINAL_LINE = re.compile(
    r"^\s*(?:the\s+)?(?:first|second|third|fourth|fifth)\s+.+?\s+is\s+(.+?)[\.,;]?\s*$",
    re.IGNORECASE,
)
_A_ORDINAL_LINE = re.compile(
    r"^\s*a\s+(?:second|third|fourth|fifth)\s+.+?\s+is\s+(.+?)[\.,;]?\s*$",
    re.IGNORECASE,
)


def _plain_evidence_text(cards: list[EvidenceCard]) -> str:
    return "\n".join(card.snippet.replace("[[", "").replace("]]", "") for card in cards)


def is_list_enumeration_question(question: str) -> bool:
    """Return True when the question asks for list-like document content."""
    stripped = question.strip()
    if not stripped:
        return False

    lower = stripped.lower()
    if "different" in lower:
        return True
    if "types of" in lower:
        return True
    if lower.startswith("what are"):
        return True
    if lower.startswith("list"):
        return True
    return any(term in lower for term in _PLURAL_TARGETS)


def _normalize_list_item(item: str) -> str:
    cleaned = re.sub(r"\s+", " ", item.strip(" \t-•*.;,"))
    if cleaned.lower().startswith("the "):
        cleaned = cleaned[4:]
    return cleaned.strip()


def _is_valid_list_item(item: str, evidence_lower: str) -> bool:
    if len(item) < 3 or len(item) > 180:
        return False
    return item.lower() in evidence_lower


def _compose_architecture_answer(evidence_text: str) -> str | None:
    evidence_lower = evidence_text.lower()
    found: list[str] = []
    for phrase, label in _ARCHITECTURE_PHRASES:
        if phrase in evidence_lower:
            found.append(label)

    if not found:
        return None

    count_word = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
    }.get(len(found), str(len(found)))
    lines = [f"The document describes {count_word} architecture families:"]
    lines.extend(f"{index}. {label}" for index, label in enumerate(found, start=1))
    return "\n".join(lines)


def _extract_generic_enumeration(evidence_text: str) -> list[str]:
    evidence_lower = evidence_text.lower()
    items: list[str] = []
    seen: set[str] = set()

    for raw_line in evidence_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        candidate: str | None = None
        numbered = _NUMBERED_LINE.match(line)
        if numbered:
            candidate = numbered.group(1)
        else:
            bullet = _BULLET_LINE.match(line)
            if bullet:
                candidate = bullet.group(1)
            else:
                ordinal = _THE_ORDINAL_LINE.match(line)
                if ordinal:
                    candidate = ordinal.group(1)
                else:
                    a_ordinal = _A_ORDINAL_LINE.match(line)
                    if a_ordinal:
                        candidate = a_ordinal.group(1)

        if not candidate:
            continue

        item = _normalize_list_item(candidate)
        key = item.lower()
        if not _is_valid_list_item(item, evidence_lower):
            continue
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items


def _compose_generic_enumeration_answer(
    question: str,
    items: list[str],
) -> str:
    lower = question.lower()
    if "architect" in lower:
        intro = (
            f"The document describes {len(items)} architecture-related "
            "items from the retrieved evidence:"
        )
    elif "different" in lower:
        intro = (
            f"The document describes {len(items)} different items "
            "from the retrieved evidence:"
        )
    else:
        intro = (
            f"The document describes {len(items)} enumerated items "
            "from the retrieved evidence:"
        )

    lines = [intro]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines)


def compose_structured_answer(
    question: str,
    cards: list[EvidenceCard],
) -> str | None:
    """
    Build a short extractive answer from evidence snippets when confident.

    Returns None when the question is not list-like, evidence is missing,
    or enumeration cannot be extracted deterministically from source text.
    """
    if not cards:
        return None
    if not is_list_enumeration_question(question):
        return None

    evidence_text = _plain_evidence_text(cards)
    if not evidence_text.strip():
        return None

    lower_question = question.lower()
    if "architect" in lower_question:
        architecture_answer = _compose_architecture_answer(evidence_text)
        if architecture_answer:
            return architecture_answer

    items = _extract_generic_enumeration(evidence_text)
    if len(items) >= 2:
        return _compose_generic_enumeration_answer(question, items)

    return None
