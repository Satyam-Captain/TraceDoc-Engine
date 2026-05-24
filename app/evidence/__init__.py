"""Evidence engine and answer card composition."""

from app.evidence.composer import compose_answer_package
from app.evidence.context import expand_result_context, needs_context_expansion
from app.evidence.highlighter import highlight_terms
from app.evidence.models import (
    ANSWER_MODE_EVIDENCE_ONLY,
    ANSWER_MODE_NO_EVIDENCE,
    ANSWER_MODE_STRUCTURED_EXTRACTIVE,
    AnswerPackage,
    EvidenceCard,
)
from app.evidence.structured_composer import (
    compose_structured_answer,
    is_list_enumeration_question,
)
from app.evidence.selector import (
    classify_confidence,
    extract_snippet,
    format_citation,
    normalize_snippet,
    select_evidence_cards,
)

__all__ = [
    "ANSWER_MODE_EVIDENCE_ONLY",
    "ANSWER_MODE_NO_EVIDENCE",
    "ANSWER_MODE_STRUCTURED_EXTRACTIVE",
    "AnswerPackage",
    "EvidenceCard",
    "classify_confidence",
    "compose_answer_package",
    "compose_structured_answer",
    "is_list_enumeration_question",
    "expand_result_context",
    "needs_context_expansion",
    "extract_snippet",
    "format_citation",
    "highlight_terms",
    "normalize_snippet",
    "select_evidence_cards",
]
