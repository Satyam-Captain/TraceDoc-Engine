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

## Layout

- `app/` — ingestion, structure, indexing, query, retrieval, evidence, audit, storage
- `config/` — configuration
- `data/` — uploads and index artifacts
- `tests/` — test suite
- `docs/` — design and architecture
