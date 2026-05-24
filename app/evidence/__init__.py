"""Evidence engine and answer card composition."""

from app.evidence.composer import compose_answer_package
from app.evidence.highlighter import highlight_terms
from app.evidence.models import AnswerPackage, EvidenceCard
from app.evidence.selector import (
    classify_confidence,
    extract_snippet,
    format_citation,
    normalize_snippet,
    select_evidence_cards,
)

__all__ = [
    "AnswerPackage",
    "EvidenceCard",
    "classify_confidence",
    "compose_answer_package",
    "extract_snippet",
    "format_citation",
    "highlight_terms",
    "normalize_snippet",
    "select_evidence_cards",
]
