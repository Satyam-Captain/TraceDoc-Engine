"""Whoosh BM25 index build and path helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import whoosh.index as whoosh_index
from whoosh.fields import ID, Schema, STORED, TEXT

from app.structure.models import DocumentChunk

_RETRIEVAL_ENV = "TRACEDOC_RETRIEVAL"
_DEFAULT_WHOOSH_ROOT = Path("data/index/whoosh")

_WHOOSH_SCHEMA = Schema(
    chunk_id=ID(stored=True, unique=True),
    text=TEXT(stored=True),
    section_id=ID(stored=True),
    document_name=STORED,
    start_line=STORED,
    end_line=STORED,
    section_title=STORED,
    chunk_type=STORED,
)


def get_retrieval_mode() -> str:
    """Return TRACEDOC_RETRIEVAL (sqlite, whoosh, or hybrid)."""
    return os.environ.get(_RETRIEVAL_ENV, "sqlite").lower()


def should_build_whoosh_index() -> bool:
    return get_retrieval_mode() in ("whoosh", "hybrid")


def whoosh_index_dir(
    document_id: int,
    base_dir: Path | None = None,
) -> Path:
    """Directory for one document's Whoosh index."""
    root = base_dir if base_dir is not None else _DEFAULT_WHOOSH_ROOT
    return root / str(document_id)


def whoosh_index_exists(index_dir: Path) -> bool:
    return index_dir.is_dir() and whoosh_index.exists_in(index_dir)


def build_whoosh_index(
    document_id: int,
    chunks: list[DocumentChunk],
    index_dir: Path,
) -> Path:
    """
    Build a fresh Whoosh BM25 index for document chunks.

    Uses Whoosh default BM25 similarity (BM25F).
    """
    index_dir = Path(index_dir)
    if index_dir.exists():
        shutil.rmtree(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    ix = whoosh_index.create_in(str(index_dir), _WHOOSH_SCHEMA)
    writer = ix.writer()

    for chunk in chunks:
        writer.add_document(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            section_id=chunk.section_id or "",
            document_name=chunk.document_name,
            start_line=str(chunk.start_line),
            end_line=str(chunk.end_line),
            section_title=chunk.section_title or "",
            chunk_type=chunk.chunk_type,
        )

    writer.commit()
    return index_dir
