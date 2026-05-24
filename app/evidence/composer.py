"""Answer package composition from retrieved evidence."""

from __future__ import annotations

from app.evidence.context import expand_result_context
from app.evidence.models import AnswerPackage
from app.evidence.selector import select_evidence_cards
from app.retrieval.models import SearchResult
from app.structure.models import DocumentChunk

NO_EVIDENCE_MESSAGE = "No reliable evidence found in the uploaded documents."
NO_EVIDENCE_EXPLANATION = (
    "No matching evidence passed the deterministic retrieval threshold."
)
EVIDENCE_EXPLANATION = (
    "This response is based only on exact evidence retrieved from the "
    "uploaded documents. No AI-generated answer was produced."
)


def compose_answer_package(
    question: str,
    search_results: list[SearchResult],
    max_cards: int = 3,
    all_chunks: list[DocumentChunk] | None = None,
) -> AnswerPackage:
    """
    Compose a non-generative answer package from search results.

    Does not synthesize prose answers; returns evidence cards only.
    """
    expanded_results = search_results
    if all_chunks:
        expanded_results = [
            expand_result_context(result, all_chunks) for result in search_results
        ]

    cards = select_evidence_cards(
        question=question,
        search_results=expanded_results,
        max_cards=max_cards,
    )

    if not cards:
        return AnswerPackage(
            question=question,
            answer_mode="NO_EVIDENCE",
            cards=[],
            no_evidence_message=NO_EVIDENCE_MESSAGE,
            explanation=NO_EVIDENCE_EXPLANATION,
        )

    return AnswerPackage(
        question=question,
        answer_mode="EVIDENCE_ONLY",
        cards=cards,
        no_evidence_message=None,
        explanation=EVIDENCE_EXPLANATION,
    )
