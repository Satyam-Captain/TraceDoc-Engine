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

## Layout

- `app/` — ingestion, structure, indexing, query, retrieval, evidence, audit, storage
- `config/` — configuration
- `data/` — uploads and index artifacts
- `tests/` — test suite
- `docs/` — design and architecture
