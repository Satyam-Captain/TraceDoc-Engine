# TraceDoc Engine

A local, deterministic document question-answering system.

No LLMs, ML models, embeddings, or external APIs — runs entirely on your laptop.

## Status

Project initialized. Implementation steps follow the architecture in `docs/architecture.md`.

## Step 2: Document ingestion

Deterministic ingestion extracts raw text and metadata from local files. No AI, LLM, embeddings, or external APIs are used.

**Supported file types:** `.pdf`, `.docx`, `.txt`

**Usage (Python):**

```python
from app.ingestion import extract_document

result = extract_document("path/to/document.pdf")
print(result.text, result.checksum_sha256, result.extraction_warnings)
```

**Run tests:**

```bash
pip install -r requirements.txt
pytest
```

## Step 3: Structure extraction and chunking

After ingestion, TraceDoc converts raw text into **sections** and **line-anchored chunks** using deterministic rules only. No AI, LLM, embeddings, or external APIs are used.

**Heading detection** uses explainable patterns (markdown `#` headings, numbered outlines like `1.1 Scope`, uppercase titles, `Appendix A`, `Section 4`, and numbered titles like `4 Requirements`).

**Chunking** preserves original line numbers, prefers section and paragraph boundaries, and only splits inside a paragraph when it exceeds `max_chars` (default `1200`). Chunks carry stable IDs and optional `section_id` / `section_title` for evidence anchors.

Chunking is required before indexing so retrieval can return precise, citable spans instead of whole documents.

**Usage (Python):**

```python
from app.structure import structure_document

sections, chunks = structure_document("report.pdf", extracted_text)
print(len(sections), len(chunks), chunks[0].chunk_id)
```

**Run tests:**

```bash
python -m pytest
```

## Step 4: Knowledge preparation and lexical indexing

The Knowledge Preparation Layer turns structured chunks into **classical IR artifacts**: tokenized terms, an inverted index, and BM25 statistics. This is deterministic lexical search—not semantic search. No embeddings, vector databases, AI models, or external APIs are used.

**Techniques:**
- **Tokenization & normalization** — explainable splitting; preserves identifiers like `REQ-001`, `HPC6`, `ISO27001`
- **Stopwords** — configurable filtering (off by default during indexing)
- **Inverted index** — `term → chunk` postings with frequencies and positions
- **BM25 preparation** — document frequency (df), inverse document frequency (idf), and average chunk length (avgdl) for a later retrieval step

Every indexed term maps to explicit chunk evidence, making ranking auditable and reproducible on a laptop.

**Usage (Python):**

```python
from app.indexing import prepare_document_chunks
from app.structure import structure_document

_, chunks = structure_document("policy.txt", extracted_text)
index, bm25_stats = prepare_document_chunks(chunks)
print(index.vocabulary_size, bm25_stats["avgdl"])
```

**Run tests:**

```bash
python -m pytest
```

## Step 5: Deterministic retrieval/search

The Deterministic Retrieval Core accepts a plain-text query, prepares lexical terms (tokenize, normalize, stopword removal with fallback), looks up candidates in the inverted index, and ranks chunks with **BM25**. No AI, embeddings, vector search, or external APIs are involved.

**Query preparation** reuses the indexing tokenizer/normalizer and drops common stopwords unless that would leave an empty query.

**Scoring** applies the standard BM25 formula using precomputed `df`, `idf`, and `avgdl` from Step 4. Each result includes `matched_terms`, per-term scores, and a `why_matched` explanation for auditability.

**Usage (Python):**

```python
from app.indexing import prepare_document_chunks
from app.retrieval import search_chunks

index, bm25_stats = prepare_document_chunks(chunks)
results = search_chunks("HPC6 memory requirements", index, bm25_stats, top_k=5)
for hit in results:
    print(hit.score, hit.text, hit.why_matched)
```

**Run tests:**

```bash
python -m pytest
```

## Step 6: Local SQLite storage and index persistence

The Local Storage Layer persists documents, sections, chunks, lexical index postings, BM25 statistics, and audit events in a single **SQLite** database (`sqlite3` only — no ORM). All data stays on disk under your project path (for example `data/index/tracedoc.db`).

**Tables:** `documents`, `sections`, `chunks`, `index_terms`, `chunk_term_frequencies`, `bm25_statistics`, `audit_events`

**Duplicate handling:** the same `checksum_sha256` is not stored twice; `save_document_bundle` returns the existing document id.

**Usage (Python):**

```python
from app.storage import (
    initialize_database,
    save_document_bundle,
    save_index_bundle,
    load_index_for_document,
    load_bm25_statistics,
)
from app.indexing import prepare_document_chunks
from app.structure import structure_document

db_path = "data/index/tracedoc.db"
initialize_database(db_path)

sections, chunks = structure_document("policy.txt", text)
document_id, created = save_document_bundle(db_path, extraction, sections, chunks)
index, bm25_stats = prepare_document_chunks(chunks)
save_index_bundle(db_path, document_id, index, bm25_stats)

loaded_index = load_index_for_document(db_path, document_id)
loaded_stats = load_bm25_statistics(db_path, document_id)
```

**Run tests:**

```bash
python -m pytest
```

## Step 7: End-to-end document processing pipeline

`process_document()` orchestrates the full deterministic backend flow in one call:

**ingest → structure → chunk → index → persist**

No AI, LLM, embeddings, or external APIs are used. The SQLite database stores the document bundle and lexical index. Duplicate files (same SHA-256 checksum) return `duplicate=True` and reuse the existing `document_id` without creating duplicate rows.

**Usage (Python):**

```python
from app.pipeline import process_document

result = process_document("data/uploads/policy.txt", db_path="data/tracedoc.db")
print(result.document_id, result.chunk_count, result.duplicate, result.warnings)
```

**Batch processing:**

```python
from app.pipeline import process_documents

results = process_documents(["doc1.txt", "doc2.pdf"], db_path="data/tracedoc.db")
```

**Run tests:**

```bash
python -m pytest
```

## Step 8: Evidence engine and answer cards

The Evidence Engine and Answer Card Composer turn BM25 search hits into **citation-first, evidence-only** responses. TraceDoc does not generate ChatGPT-style prose; it returns exact snippets from uploaded documents with line anchors and match explanations.

**Features:**
- **Evidence selection** — filter by score, deduplicate normalized snippets, keep top cards
- **Snippets** — full chunk text, trimmed around the first matched term when over 700 characters
- **Highlighting** — `[[term]]` markers with original casing preserved
- **Confidence** — `HIGH` / `MEDIUM` / `LOW` from BM25 score and matched-term count
- **Citations** — `document | section: … | lines start-end`

This design prevents hallucination: every visible statement traces to a retrieved chunk. No AI, LLM, or embeddings are used.

**Usage (Python):**

```python
from app.evidence import compose_answer_package
from app.retrieval import search_chunks

results = search_chunks("HPC6 memory", index, bm25_stats, top_k=5)
package = compose_answer_package("What are the HPC6 memory requirements?", results)

for card in package.cards:
    print(card.confidence, card.citation, card.snippet)
```

**Run tests:**

```bash
python -m pytest
```

## Step 9: Document question-answer orchestration

`ask_document()` connects the **Local Storage Layer**, **Deterministic Retrieval Core**, and **Evidence Engine** into one backend call:

**load document → load index & BM25 → search → compose evidence cards**

Responses are **evidence-only** (`EVIDENCE_ONLY` or `NO_EVIDENCE`). No generative answer text is produced. No AI, LLM, embeddings, or external APIs are used.

**Usage (Python):**

```python
from app.pipeline import process_document
from app.qa import ask_document

process_result = process_document("data/uploads/policy.txt", db_path="data/tracedoc.db")
answer = ask_document(
    "What are the HPC6 memory requirements?",
    process_result.document_id,
    db_path="data/tracedoc.db",
)

for card in answer.cards:
    print(card.confidence, card.citation, card.snippet)
```

**Run tests:**

```bash
python -m pytest
```

## Step 10: Local Streamlit UI

A minimal local UI exposes the deterministic backend:

1. **Upload** a PDF, DOCX, or TXT file (saved under `data/uploads/`)
2. **Process** via `process_document()` into `data/tracedoc.db`
3. **Select** an indexed document
4. **Ask a question** and view **evidence cards** (not an AI-generated answer)

No LLM, embeddings, vector search, or external APIs are used.

**Run the app:**

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

**Run tests:**

```bash
python -m pytest
```

## Layout

- `app/` — ingestion, structure, indexing, query, retrieval, evidence, audit, storage
- `config/` — configuration
- `data/` — uploads and index artifacts
- `tests/` — test suite
- `docs/` — design and architecture
