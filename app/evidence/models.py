"""Data models for evidence cards and answer packages."""

from dataclasses import dataclass, field

ANSWER_MODE_EVIDENCE_ONLY = "EVIDENCE_ONLY"
ANSWER_MODE_STRUCTURED_EXTRACTIVE = "STRUCTURED_EXTRACTIVE"
ANSWER_MODE_GRAPH_STRUCTURED = "GRAPH_STRUCTURED"
ANSWER_MODE_NO_EVIDENCE = "NO_EVIDENCE"


@dataclass
class EvidenceCard:
    """Source-backed evidence extracted from a retrieved chunk."""

    chunk_id: str
    document_name: str
    section_title: str | None
    start_line: int
    end_line: int
    snippet: str
    matched_terms: list[str]
    score: float
    confidence: str
    why_matched: str
    citation: str


@dataclass
class AnswerPackage:
    """Non-generative answer composed only from retrieved evidence."""

    question: str
    answer_mode: str
    cards: list[EvidenceCard] = field(default_factory=list)
    structured_answer: str | None = None
    no_evidence_message: str | None = None
    explanation: str = ""
