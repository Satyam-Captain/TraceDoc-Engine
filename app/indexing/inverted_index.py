"""Inverted index construction."""

from __future__ import annotations

from collections import defaultdict

from app.indexing.models import ChunkIndexEntry, IndexedToken, InvertedIndex
from app.indexing.normalizer import normalize_token
from app.indexing.stopwords import is_stopword
from app.indexing.tokenizer import tokenize
from app.structure.models import DocumentChunk

DEFAULT_FIELD_WEIGHTS = {
    "text": 1.0,
    "section_title": 1.5,
    "chunk_type_section": 1.2,
}


def _normalize_text(text: str) -> str:
    tokens = [normalize_token(token) for token in tokenize(text)]
    return " ".join(token for token in tokens if token)


def _index_token_stream(
    raw_tokens: list[str],
    remove_stopwords: bool,
) -> tuple[list[IndexedToken], dict[str, int]]:
    indexed: dict[str, IndexedToken] = {}
    frequencies: dict[str, int] = defaultdict(int)

    for position, raw_token in enumerate(raw_tokens):
        normalized = normalize_token(raw_token)
        if not normalized:
            continue
        if remove_stopwords and is_stopword(normalized):
            continue

        frequencies[normalized] += 1
        if normalized not in indexed:
            indexed[normalized] = IndexedToken(
                token=raw_token,
                normalized_token=normalized,
                frequency=0,
                positions=[],
            )
        entry = indexed[normalized]
        entry.frequency += 1
        entry.positions.append(position)

    return list(indexed.values()), dict(frequencies)


def build_inverted_index(
    chunks: list[DocumentChunk],
    remove_stopwords: bool = False,
) -> InvertedIndex:
    """
    Build a deterministic inverted index from document chunks.

    Tokenizes and normalizes chunk text, records term frequencies and
    positions, and computes corpus-level chunk length statistics.
    """
    term_to_chunks: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    chunk_statistics: dict[str, ChunkIndexEntry] = {}
    searchable_term_map: dict[str, str] = {}
    document_names: set[str] = set()
    total_token_count = 0
    indexed_chunk_count = 0

    for chunk in chunks:
        document_names.add(chunk.document_name)
        raw_tokens = tokenize(chunk.text)
        if chunk.section_title:
            raw_tokens.extend(tokenize(chunk.section_title))

        if not raw_tokens:
            continue

        indexed_tokens, frequencies = _index_token_stream(
            raw_tokens, remove_stopwords=remove_stopwords
        )
        if not frequencies:
            continue

        token_count = sum(frequencies.values())
        total_token_count += token_count
        indexed_chunk_count += 1

        for indexed_token in indexed_tokens:
            searchable_term_map.setdefault(
                indexed_token.normalized_token, indexed_token.token
            )

        entry = ChunkIndexEntry(
            chunk_id=chunk.chunk_id,
            document_name=chunk.document_name,
            chunk_type=chunk.chunk_type,
            section_title=chunk.section_title,
            token_count=token_count,
            unique_token_count=len(frequencies),
            normalized_text=_normalize_text(chunk.text),
            token_frequencies=frequencies,
            metadata={
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "section_id": chunk.section_id,
                "indexed_tokens": [
                    {
                        "token": item.token,
                        "normalized_token": item.normalized_token,
                        "frequency": item.frequency,
                        "positions": item.positions,
                    }
                    for item in indexed_tokens
                ],
                "title_token_count": len(tokenize(chunk.section_title or "")),
            },
        )
        chunk_statistics[chunk.chunk_id] = entry

        for term, frequency in frequencies.items():
            token_entry = next(
                item for item in indexed_tokens if item.normalized_token == term
            )
            term_to_chunks[term][chunk.chunk_id] = {
                "frequency": frequency,
                "positions": list(token_entry.positions),
            }

    average_chunk_length = (
        total_token_count / indexed_chunk_count if indexed_chunk_count else 0.0
    )

    return InvertedIndex(
        term_to_chunks={term: dict(postings) for term, postings in term_to_chunks.items()},
        chunk_statistics=chunk_statistics,
        document_count=len(document_names),
        total_chunk_count=indexed_chunk_count,
        average_chunk_length=average_chunk_length,
        vocabulary_size=len(term_to_chunks),
        searchable_term_map=searchable_term_map,
        field_weights=dict(DEFAULT_FIELD_WEIGHTS),
    )
