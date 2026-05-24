# TraceDoc Engine

**Deterministic evidence-based document QA engine** for local laptops.

TraceDoc ingests PDF, DOCX, and TXT files, builds a lexical index, and returns **citation-first evidence cards** for each question. Every result traces to source text with line anchors—no generated prose answer.

## What it is

- A **classical information retrieval** pipeline: ingest → structure → chunk → index → BM25 search → evidence cards
- A **local SQLite** persistence layer with audit events
- A **rule-based query interpreter** for deterministic intent detection
- A minimal **Streamlit UI** for upload, process, ask, and traceability

## What it is not

- Not an LLM or chatbot
- Not semantic / vector search (no embeddings)
- Not a cloud service (no external APIs required)
- Not a system that invents answers—it shows retrieved evidence only

## No-AI guarantees

| Excluded | Used instead |
|----------|----------------|
| LLM / generative AI | Deterministic snippets from source chunks |
| ML rankers / classifiers | BM25 + explicit rules |
| Embeddings / vector DB | Inverted lexical index |
| External APIs | Local `sqlite3` and file I/O |

## Architecture summary

```
Upload → Ingestion → Structure/Chunking → Lexical Index → SQLite
                                              ↓
Question → Query Interpreter → BM25 Retrieval → Evidence Cards
                                              ↓
                                    Audit log (append-only)
```

Full logical architecture: [`docs/architecture.md`](docs/architecture.md) and [`docs/architecture.drawio`](docs/architecture.drawio).

## Current capabilities

| Layer | Module | Description |
|-------|--------|-------------|
| Ingestion | `app/ingestion/` | PDF, DOCX, TXT extraction + SHA-256 |
| Structure | `app/structure/` | Heading detection, line-anchored chunks |
| Indexing | `app/indexing/` | Tokenization, inverted index, BM25 stats |
| Retrieval | `app/retrieval/` | Deterministic BM25 ranking |
| Evidence | `app/evidence/` | Evidence cards with citations |
| Storage | `app/storage/` | SQLite persistence |
| Pipeline | `app/pipeline.py` | `process_document()` end-to-end |
| Q&A | `app/qa.py` | `ask_document()` orchestration |
| Query | `app/query/` | Rule-based intent detection |
| Audit | `app/audit/` | Append-only event logging |
| UI | `app/main.py` | Streamlit demo |

## Quick start

```bash
git clone https://github.com/Satyam-Captain/TraceDoc-Engine.git
cd TraceDoc-Engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows
pip install -r requirements.txt
```

## Run tests

```bash
python -m pytest
```

## Run smoke test

Repeatable demo validation (pytest + sample docs + four questions):

```bash
python scripts/smoke_test.py
```

Uses `data/demo_tracedoc.db` and sample files under `samples/`.

## Run Streamlit app

```bash
streamlit run app/main.py
```

1. Upload a document (or use files from `samples/`)
2. Process into the local database
3. Select a document and ask a question
4. Review **evidence cards** (not an AI answer) and the audit log

## Demo script (architect briefing)

Suggested flow—details in [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md):

1. Show **constraints** in the UI sidebar (no LLM, local-only).
2. Run `python scripts/smoke_test.py` to prove the pipeline end-to-end.
3. Open Streamlit; process `samples/hpc6_policy.txt`.
4. Ask: *What is HPC6 memory policy?* — show intent + evidence card + citation.
5. Ask: *What is REQ-001?* on `samples/requirements_sample.txt` — show requirement ID handling.
6. Open **Audit / Traceability** — show `document_processed` and `question_asked` events.

**Sample questions**

- What is HPC6 memory policy?
- Where is CPU binding mentioned?
- What is REQ-001?
- List all storage rules

## Sample documents

| File | Purpose |
|------|---------|
| [`samples/hpc6_policy.txt`](samples/hpc6_policy.txt) | HPC6 memory, CPU binding, NVMe, GPFS, table rows |
| [`samples/requirements_sample.txt`](samples/requirements_sample.txt) | REQ-001..003, shall/must language |

## Python API (minimal)

```python
from app.pipeline import process_document
from app.qa import ask_document

result = process_document("samples/hpc6_policy.txt", db_path="data/tracedoc.db")
answer = ask_document(
    "What is HPC6 memory policy?",
    result.document_id,
    db_path="data/tracedoc.db",
)
for card in answer.cards:
    print(card.confidence, card.citation, card.snippet)
```

## Limitations

- Single-machine, single-user focus in v1
- Lexical matching only (no synonym expansion or embeddings)
- No generative summarization or multi-hop reasoning
- PDF/DOCX extraction quality depends on source formatting
- Multi-document Q&A is limited to simple orchestration helpers

## Future enterprise path

Documented in architecture as out-of-scope for v1: SSO/RBAC, multi-tenant storage, central policy service, enterprise connectors (SharePoint, Confluence), observability export. The deterministic core remains unchanged.

## Project layout

```
tracedoc-engine/
  app/           Application code
  config/        Configuration placeholders
  data/          Local DB and uploads (gitignored contents)
  docs/          Architecture and demo walkthrough
  samples/       Demo TXT documents
  scripts/       smoke_test.py
  tests/         Pytest suite
```

## License / status

Active development. See git history for incremental step commits (ingestion through query interpreter).
