# TraceDoc Engine

**Deterministic evidence-based document QA engine** for local laptops.

TraceDoc ingests PDF, DOCX, and TXT files, builds a lexical index, and returns **citation-first evidence cards** for each question. For list-like questions it can also show a **structured extractive answer** built only from retrieved snippets—still no LLM or invented content.

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
| Evidence | `app/evidence/` | Evidence cards, context expansion, structured extractive answers |
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
4. Review **extractive answers** (when applicable), **supporting evidence cards**, and the audit log

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
| [`samples/system_architectures.txt`](samples/system_architectures.txt) | Architecture families for structured list answers |
| [`samples/lineage_capabilities.txt`](samples/lineage_capabilities.txt) | Lineage / SPDM concepts for explanation-style questions |

## Step 16: PDF semantic heading detection

PDF text extraction often loses markdown-style structure, so headings like *Existing architectures* may appear as plain lines. TraceDoc now applies **deterministic layout heuristics** (line length, title casing, blank-line context, known prefixes, paragraph-follow signals) to promote semantic section boundaries before chunking and indexing.

- **No ML/OCR** — rule-based scoring only
- **Improves section retrieval** — list questions can match section titles such as *Existing architectures*
- **Limitations** — unusual fonts, multi-column PDFs, or heading-like sentences in body text may still be missed or over-detected; thresholds aim for meaningful sections only

Sample: `samples/pdf_style_document.txt`

## Step 20: Symbolic relationship inference

When PDF text describes architectures indirectly (for example OpenEphyra as a modular QA implementation, or *this pipeline* in a follow-on sentence), explicit regex extraction is not enough. `app/evidence/symbolic_inference.py` adds **deterministic symbolic rules**:

- **Relationship graph** — registered implications (for example OpenEphyra → Classic QA pipeline)
- **Co-reference resolution** — backward scan for *this/that pipeline|architecture* without NLP coreference libraries
- **Merged with explicit patterns** — `pattern_extractor.py` runs symbolic inference after explicit rules, preserves source order, deduplicates

Each `ExtractedPhrase` records `inference_type` (`explicit_pattern` or `symbolic_inference`) and `pattern_name` for debug trace lines such as `inference=open_ephyra_pipeline_inference`.

Still **no LLM, embeddings, or external APIs**.

## Step 19: Robust deterministic pattern extraction

Architecture structured answers use **sentence segmentation** (`sentence_splitter.py`) and **grammar-style rules** (`pattern_extractor.py`) before composition:

- Split evidence on `. ? !` with simple abbreviation protection
- Extract phrases from patterns such as `The most common … architecture is X`, stopping at `:`, `;`, or clause introducers (`which`, `that`, `where`, `with`)
- Detect **Classic QA pipeline** from contextual sentences (for example near *cleanest conceptual answer*) when ordinal wording is absent
- Fall back to **evidence-grounded noun-phrase recognition** only when the phrase literally appears in retrieved text
- `clean_extracted_phrase()` normalizes articles, punctuation, and acronyms (QA, RDF, BM25, …)

Still **no LLM, embeddings, or external APIs**. Debug trace may list `extracted=… pattern=…` lines for architecture questions.

## Step 18: Generic deterministic pattern extraction

Structured architecture answers no longer rely on a hardcoded list of family names. `app/evidence/pattern_extractor.py` applies **symbolic, rule-based extraction** to evidence text (for example `The most common … architecture is X`, `A second architecture is X`) and normalizes phrases for display.

- **No ML/LLM/embeddings** — regex rules, validation heuristics, and category-specific extractors only
- **Extensible categories** — `architecture` is implemented; `capability`, `pattern`, and `technology` can add rules in the same registry
- **Traceability** — each extracted phrase can retain its source sentence for debugging and future UI

Re-process documents after upgrading if stored answers were built from older hardcoded matching.

## Step 17: PDF layout reconstruction

pypdf and similar extractors flatten page text into long paragraphs, so headings such as *Existing architectures* can appear inline (`...mechanism. Existing architectures The most common...`) instead of on their own line. Section detection then fails because heading heuristics never see isolated lines.

Before structure detection, `app/ingestion/pdf_layout.py` runs **`reconstruct_pdf_layout()`** on PDF-extracted text:

- Inserts blank-line breaks around probable inline headings (title-case phrases, known prefixes, sentence-boundary signals)
- Rejects URLs, over-long phrases, heavy punctuation, and mostly-lowercase spans
- **No LLM, embeddings, OCR, or external APIs** — deterministic regex and phrase rules only

This restores semantic section boundaries so stored section counts and section-level retrieval work on real PDFs. Re-process uploaded PDFs after upgrading (or use **Clear all local data** in the UI) so layout reconstruction applies to stored content.

## Step 15: Section-level retrieval

Chunk-only BM25 can return only the first matching chunk near a heading. For broader questions (for example *different architectures*, *what architectures are mentioned*, *explain lineage*), TraceDoc now:

1. Ranks document **sections** by title overlap (with weak-word filtering and singular/plural normalization)
2. Collects **all chunks inside the best section** (up to a deterministic cap)
3. Passes section-level evidence to structured extractive composition

- **No AI/LLM** — section scoring and extraction use tokenizer, normalizer, and regex rules only
- **BM25 fallback preserved** — if no relevant section/chunks are found, chunk BM25 search still runs
- **Limitations** — depends on heading detection quality; unstructured PDFs may still miss section boundaries

## Step 14: Structured extractive answers

For list-style questions (for example *different architectures?*, *what are the types of …*, *list …*), TraceDoc can compose a short **structured extractive answer** from retrieved evidence only.

- **Not LLM generation** — no model invents text; items must appear in evidence snippets.
- **Deterministic rules** — architecture phrases, numbered/bullet lines, and ordinal sentences (`The first … is …`) are matched with regex.
- **Useful for enumerations** — readable bullet summaries above supporting evidence cards.
- **Limitations** — if extraction is uncertain, the UI falls back to `EVIDENCE_ONLY` with cards only; lexical retrieval gaps still apply.

Try: process `samples/system_architectures.txt`, then ask *different architectures?*

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
- Structured answers only when extractable phrases exist in retrieved section/chunk evidence
- Section-level retrieval requires detectable headings and section ranges
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
