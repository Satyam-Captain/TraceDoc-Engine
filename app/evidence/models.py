"""Data models for evidence cards and answer packages."""

from dataclasses import dataclass, field


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
    no_evidence_message: str | None = None
    explanation: str = ""
