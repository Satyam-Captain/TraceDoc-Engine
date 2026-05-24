"""Structure extraction: sections and deterministic chunks."""

from app.structure.chunker import chunk_document, structure_document
from app.structure.detector import detect_sections
from app.structure.hierarchy import build_section_hierarchy, infer_section_ranges
from app.structure.models import DocumentChunk, DocumentSection

__all__ = [
    "DocumentChunk",
    "DocumentSection",
    "build_section_hierarchy",
    "chunk_document",
    "detect_sections",
    "infer_section_ranges",
    "structure_document",
]
