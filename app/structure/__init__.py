"""Structure extraction: sections and deterministic chunks."""

from app.structure.chunker import chunk_document, structure_document
from app.structure.detector import detect_sections
from app.structure.heading_heuristics import is_probable_heading, score_heading_probability
from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection
from app.structure.section_assignment import reassign_chunk_sections

__all__ = [
    "DocumentChunk",
    "DocumentSection",
    "build_section_hierarchy",
    "chunk_document",
    "detect_sections",
    "infer_section_ranges",
    "is_probable_heading",
    "reassign_chunk_sections",
    "score_heading_probability",
    "structure_document",
]
