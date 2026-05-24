"""Deterministic structured answers composed only from evidence text."""

from __future__ import annotations

import re

from app.evidence.extraction_runtime import (
    GrammarExecutionResult,
    execute_discovered_grammar_with_result,
)
from app.evidence.models import EvidenceCard
from app.evidence.pattern_extractor import (
    extract_enumerated_phrases,
    extract_enumerated_phrases_with_trace,
)
from app.evidence.sentence_splitter import split_sentences
from app.schema.models import DiscoveredPattern, DocumentSchema

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

_LINEAGE_PHRASES: tuple[tuple[str, str], ...] = (
    ("history and traceability", "History and traceability"),
    ("provenance", "Provenance"),
    ("which geometry", "Which geometry was used"),
    ("which dataset", "Which dataset was used"),
    ("solver version", "Solver version"),
    ("runtime environment", "Runtime environment"),
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
    if "types" in lower or "kinds" in lower:
        return True
    if lower.startswith("what are"):
        return True
    if lower.startswith("list"):
        return True
    if "mentioned" in lower:
        return True
    return any(term in lower for term in _PLURAL_TARGETS)


def _is_lineage_question(question: str) -> bool:
    lower = question.lower()
    return "lineage" in lower and any(
        token in lower for token in ("explain", "meaning", "define", "describe", "what")
    )


def _should_attempt_structured_answer(question: str) -> bool:
    return is_list_enumeration_question(question) or _is_lineage_question(question)


def _normalize_list_item(item: str) -> str:
    cleaned = re.sub(r"\s+", " ", item.strip(" \t-•*.;,"))
    if cleaned.lower().startswith("the "):
        cleaned = cleaned[4:]
    return cleaned.strip()


def _is_valid_list_item(item: str, evidence_lower: str) -> bool:
    if len(item) < 3 or len(item) > 180:
        return False
    return item.lower() in evidence_lower


def architecture_evidence_text(cards: list[EvidenceCard]) -> str:
    """Merge evidence snippets and normalize into sentence-friendly text."""
    merged = _plain_evidence_text(cards)
    if not merged.strip():
        return merged
    return "\n".join(split_sentences(merged))


def _category_display_label(category: str) -> str:
    """Human-readable label for a normalized schema category key."""
    return category.replace("_", " ")


def _grammar_list_intro(category: str, *, count: int) -> str:
    label = _category_display_label(category)
    if count == 1:
        return f"The document mentions this {label}:"
    return f"The document mentions these {label}s:"


def _compose_entity_list_answer(intro: str, entities: list[str]) -> str:
    lines = [intro]
    lines.extend(f"{index}. {item}" for index, item in enumerate(entities, start=1))
    return "\n".join(lines)


def _append_supporting_evidence(answer: str, cards: list[EvidenceCard]) -> str:
    if not cards:
        return answer
    lines = [answer, "", "Supporting evidence:"]
    for index, card in enumerate(cards[:4], start=1):
        preview = card.snippet.replace("[[", "").replace("]]", "")
        preview = re.sub(r"\s+", " ", preview).strip()
        if len(preview) > 160:
            preview = preview[:157] + "..."
        lines.append(f"- ({index}) {card.citation}: {preview}")
    return "\n".join(lines)


def compose_grammar_driven_answer(
    evidence_text: str,
    category: str,
    grammar: DiscoveredPattern,
    *,
    cards: list[EvidenceCard] | None = None,
    include_supporting_evidence: bool = True,
) -> tuple[str | None, GrammarExecutionResult | None]:
    """
    Build a numbered list answer by executing a discovered grammar on evidence text.

    Returns (answer_text, execution_result).
    """
    result = execute_discovered_grammar_with_result(evidence_text, grammar)
    if not result.success or not result.entities:
        return None, result

    min_entities = 1 if result.extraction_confidence >= 0.65 else 2
    if len(result.entities) < min_entities:
        return None, result

    intro = _grammar_list_intro(category, count=len(result.entities))
    answer = _compose_entity_list_answer(intro, result.entities)
    if include_supporting_evidence and cards:
        answer = _append_supporting_evidence(answer, cards)
    return answer, result


def _compose_architecture_answer(
    evidence_text: str,
    document_schema: DocumentSchema | None = None,
) -> str | None:
    found = extract_enumerated_phrases(
        evidence_text,
        "architecture",
        document_schema=document_schema,
    )
    if not found:
        return None

    lines = ["The document describes these architecture families:"]
    lines.extend(f"{index}. {label}" for index, label in enumerate(found, start=1))
    return "\n".join(lines)


def _compose_schema_category_answer(
    evidence_text: str,
    category: str,
    document_schema: DocumentSchema,
    *,
    cards: list[EvidenceCard] | None = None,
) -> tuple[str | None, GrammarExecutionResult | None]:
    from app.schema.registry import primary_grammar_for_category

    grammar = primary_grammar_for_category(document_schema, category)
    if grammar is not None:
        answer, result = compose_grammar_driven_answer(
            evidence_text,
            category,
            grammar,
            cards=cards,
            include_supporting_evidence=True,
        )
        if answer:
            return answer, result

    found = extract_enumerated_phrases(
        evidence_text,
        category,
        document_schema=document_schema,
    )
    if len(found) < 2:
        return None, None

    label = _category_display_label(category)
    intro = f"The document describes these {label} items:"
    answer = _compose_entity_list_answer(intro, found)
    if cards:
        answer = _append_supporting_evidence(answer, cards)
    return answer, None


def architecture_extraction_trace(evidence_text: str) -> list[str]:
    """Debug lines describing extracted and inferred architecture phrases."""
    entries = extract_enumerated_phrases_with_trace(evidence_text, "architecture")
    lines: list[str] = []
    for entry in entries:
        if entry.inference_type == "symbolic_inference":
            lines.append(
                f"extracted={entry.value} inference={entry.pattern_name} "
                f"source={entry.source_sentence[:120]}"
            )
        else:
            lines.append(
                f"extracted={entry.value} pattern={entry.pattern_name} "
                f"inference=explicit_pattern source={entry.source_sentence[:120]}"
            )
    return lines


def grammar_execution_debug_lines(
    result: GrammarExecutionResult | None,
) -> list[str]:
    """Debug trace lines for grammar execution."""
    if result is None:
        return ["grammar_execution_success=False", "extracted_entities_count=0"]
    entities_preview = ", ".join(result.entities[:8])
    return [
        f"grammar_execution_success={str(result.success)}",
        f"extracted_entities_count={result.match_count}",
        f"extracted_entities=[{entities_preview}]",
        f"extraction_confidence={result.extraction_confidence:.2f}",
    ]


def _compose_lineage_answer(evidence_text: str) -> str | None:
    evidence_lower = evidence_text.lower()
    found: list[str] = []
    for phrase, label in _LINEAGE_PHRASES:
        if phrase in evidence_lower:
            found.append(label)

    if not found:
        return None

    lines = ["The document describes lineage using these extracted points:"]
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
    document_schema: DocumentSchema | None = None,
) -> str | None:
    """
    Build a short extractive answer from evidence snippets when confident.

    Returns None when the question is not list-like, evidence is missing,
    or enumeration cannot be extracted deterministically from source text.
    """
    if not cards:
        return None
    if not _should_attempt_structured_answer(question):
        return None

    evidence_text = _plain_evidence_text(cards)
    if not evidence_text.strip():
        return None

    lower_question = question.lower()

    if document_schema is not None:
        from app.schema.discovery import match_question_to_schema_category

        matched_category = match_question_to_schema_category(
            question, document_schema
        )
        if (
            matched_category is not None
            and matched_category.normalized_name != "architecture"
        ):
            schema_text = architecture_evidence_text(cards)
            schema_answer, _ = _compose_schema_category_answer(
                schema_text,
                matched_category.normalized_name,
                document_schema,
                cards=cards,
            )
            if schema_answer:
                return schema_answer

    if "architect" in lower_question:
        architecture_text = architecture_evidence_text(cards)
        architecture_answer = _compose_architecture_answer(
            architecture_text,
            document_schema=document_schema,
        )
        if architecture_answer:
            return architecture_answer

    if _is_lineage_question(question):
        lineage_answer = _compose_lineage_answer(evidence_text)
        if lineage_answer:
            return lineage_answer

    if not is_list_enumeration_question(question):
        return None

    items = _extract_generic_enumeration(evidence_text)
    if len(items) >= 2:
        return _compose_generic_enumeration_answer(question, items)

    return None
