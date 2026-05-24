"""Data models for lexical indexing."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexedToken:
    """Token statistics for a single chunk."""

    token: str
    normalized_token: str
    frequency: int
    positions: list[int] = field(default_factory=list)


@dataclass
class ChunkIndexEntry:
    """Lexical index record for one document chunk."""

    chunk_id: str
    document_name: str
    chunk_type: str
    section_title: str | None
    text: str
    token_count: int
    unique_token_count: int
    normalized_text: str
    token_frequencies: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InvertedIndex:
    """Deterministic inverted index over document chunks."""

    term_to_chunks: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    chunk_statistics: dict[str, ChunkIndexEntry] = field(default_factory=dict)
    document_count: int = 0
    total_chunk_count: int = 0
    average_chunk_length: float = 0.0
    vocabulary_size: int = 0
    searchable_term_map: dict[str, str] = field(default_factory=dict)
    field_weights: dict[str, float] = field(default_factory=dict)
