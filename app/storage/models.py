"""Storage layer data models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentRecord:
    """Persisted document metadata."""

    id: int
    file_path: str
    file_name: str
    file_type: str
    file_size_bytes: int
    checksum_sha256: str
    page_count: int | None
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_warnings: list[str] = field(default_factory=list)
    created_at: str | None = None


@dataclass
class AuditEventRecord:
    """Persisted audit trail entry."""

    id: int
    document_id: int | None
    event_type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None


@dataclass
class StoredSection:
    """Persisted section row used by section-level retrieval."""

    section_id: str
    title: str
    level: int
    start_line: int
    end_line: int
    parent_section_id: str | None = None


@dataclass
class StoredChunk:
    """Persisted chunk row used by section-level retrieval."""

    chunk_id: str
    document_name: str
    text: str
    chunk_type: str
    start_line: int
    end_line: int
    section_title: str | None = None
    section_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
