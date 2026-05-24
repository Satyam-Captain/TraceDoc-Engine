"""Data models for structure extraction and chunking."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentSection:
    """A detected document section bounded by line numbers."""

    section_id: str
    title: str
    level: int
    start_line: int
    end_line: int
    parent_section_id: str | None = None


@dataclass
class DocumentChunk:
    """A searchable text chunk with evidence anchors."""

    chunk_id: str
    document_name: str
    text: str
    chunk_type: str
    start_line: int
    end_line: int
    section_title: str | None = None
    section_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
