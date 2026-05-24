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

## Layout

- `app/` — ingestion, structure, indexing, query, retrieval, evidence, audit, storage
- `config/` — configuration
- `data/` — uploads and index artifacts
- `tests/` — test suite
- `docs/` — design and architecture
