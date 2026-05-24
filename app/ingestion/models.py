"""Data models for document ingestion."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentExtractionResult:
    """Raw text and metadata extracted from a local document file."""

    file_path: str
    file_name: str
    file_type: str
    file_size_bytes: int
    checksum_sha256: str
    page_count: int | None
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_warnings: list[str] = field(default_factory=list)
