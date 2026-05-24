"""Knowledge preparation orchestration."""

from __future__ import annotations

from app.indexing.bm25 import compute_bm25_statistics
from app.indexing.inverted_index import build_inverted_index
from app.indexing.models import InvertedIndex
from app.structure.models import DocumentChunk


def prepare_document_chunks(
    chunks: list[DocumentChunk],
    remove_stopwords: bool = False,
) -> tuple[InvertedIndex, dict]:
    """
    Prepare lexical search artifacts for structured document chunks.

    Returns an inverted index and BM25 statistic bundle suitable for
    deterministic retrieval in later pipeline stages.
    """
    index = build_inverted_index(chunks, remove_stopwords=remove_stopwords)
    statistics = compute_bm25_statistics(index)
    statistics["searchable_term_map"] = dict(index.searchable_term_map)
    return index, statistics
