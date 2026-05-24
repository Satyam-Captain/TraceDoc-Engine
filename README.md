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
Upload → Ingestion → Structure/Chunking → Semantic Tree → Lexical Index → SQLite
                                              ↓
Question → Query Interpreter → Section Tree Retrieval → Evidence Cards
                                              ↓
                                    Audit log (append-only)
```

Full logical architecture: [`docs/architecture.md`](docs/architecture.md) and [`docs/architecture.drawio`](docs/architecture.drawio).

### Document semantic tree

During processing, TraceDoc builds a deterministic tree stored in SQLite (`document_trees`):

```
document
├── section: Existing architectures
│   ├── paragraph
│   │   └── sentence: The most common pre-generative architecture is ...
│   └── ...
└── section: Design patterns for implementation
    └── ...
```

Section-level Q&A uses `get_section_text()` from this tree as the single extraction source for both structured answers and evidence cards (`extraction_source=DOCUMENT_TREE` in the debug trace). Chunk overlap is only a fallback when a tree section has no body nodes.

### Step 23: Deterministic knowledge graph builder

After the semantic tree and schema are built, TraceDoc constructs a **symbolic knowledge graph** (`document_graphs` in SQLite):

- **Built from** the semantic tree plus schema categories, grammar entities, and rule-based relation patterns (`uses`, `contains`, `includes`, `depends_on`, `refers_to`, `implements`, `is_a`, …).
- **Not AI** — no LLM, embeddings, or external APIs; only deterministic string rules and evidence-bound endpoints.
- **Future use** — relationship questions, graph traversal, and question-to-graph matching (not used for answering in this step).

Example triple:

`Enterprise search stack` —**uses**→ `repository connectors`

Debug trace during Q&A includes `graph_loaded`, `graph_node_count`, and `graph_edge_count`.

### Step 24: Question graph builder

Each user question is converted into a small **symbolic query graph** (`app/question_graph/`) before retrieval:

- Example: `What does Enterprise search stack use?` → `Enterprise search stack` —**uses?**→ `?`
- Example: `What architectures are mentioned?` → `?` —**mentions**→ `architecture`
- No LLM, embeddings, or external APIs — only deterministic pattern rules and existing token normalization.

Debug trace fields: `question_graph_built`, `qgraph_nodes`, `qgraph_edges`, `qgraph_target_relation`, `qgraph_target_category`.

A future step will **match** the question graph against the document knowledge graph; this step does not change answers yet.

### Step 25: Deterministic graph matcher

`app/graph/matcher.py` matches the question graph against the document knowledge graph using symbolic rules only:

- Forward relations (`uses`, `contains`, …): entity label + relation → target nodes
- Reverse relations (`implements`): target label + relation → source nodes
- Category/list queries: nodes whose type/category match `architecture`, `design_pattern`, etc.
- Definition queries: seed entity + `definition` / `refers_to` edges

Scoring is deterministic (exact label, relation, category type, source sentence, section). Results appear in the QA debug trace (`graph_match_count`, `graph_top_match`, `graph_answer_entities`).

### Step 26: Graph-based answer composition

Relationship-style questions (e.g. `What does X use?`, `What does X contain?`, `What implements Y?`) can now receive **`GRAPH_STRUCTURED`** answers when graph matches exceed a confidence threshold (default 8.0). Answers are numbered lists composed only from matched graph entities and source sentences — no LLM.

Enumeration questions (`what architectures are mentioned?`, `what design patterns are mentioned?`) still prefer the **section/tree structured** path.

### Step 27: Evaluation benchmark

A **repeatable, local-only** QA benchmark measures answer quality without manual UI testing:

- **Benchmark document** — `eval/benchmark_docs/symbolic_architecture_doc.txt` (architectures, design patterns, open-source building blocks, relationship examples)
- **Cases** — `eval/questions.yaml` (question, expected answer mode, required/forbidden substrings, optional section and retrieval strategy)
- **Runner** — `eval/run_eval.py` creates a temp DB, ingests the benchmark doc, runs every case, prints a PASS/FAIL table, and exits non-zero on failure
- **Library** — `app/eval/` (`runner.py`, `models.py`, `metrics.py`)

```bash
python eval/run_eval.py
```

Metrics reported: total/passed/failed cases, answer-mode accuracy, `expected_contains` pass rate, and `expected_not_contains` violations. No LLM, embeddings, or external APIs.

## Current capabilities

| Layer | Module | Description |
|-------|--------|-------------|
| Ingestion | `app/ingestion/` | PDF, DOCX, TXT extraction + SHA-256 |
| Structure | `app/structure/` | Heading detection, line-anchored chunks |
| Semantic tree | `app/tree/` | Deterministic document → section → paragraph → sentence tree |
| Knowledge graph | `app/graph/` | Deterministic subject → relation → object graph from tree + schema |
| Question graph | `app/question_graph/` | Symbolic query graph from user questions |
| Indexing | `app/indexing/` | Tokenization, inverted index, BM25 stats |
| Retrieval | `app/retrieval/` | Deterministic BM25 ranking |
| Evidence | `app/evidence/` | Evidence cards, context expansion, structured extractive answers |
| Storage | `app/storage/` | SQLite persistence |
| Pipeline | `app/pipeline.py` | `process_document()` end-to-end |
| Q&A | `app/qa.py`, `app/qa_context.py` | `ask_document()` orchestration; tree-backed section extraction |
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

## Stabilization: Symbolic QA pipeline

Section headings such as *Design patterns for implementation* are detected via semantic category heuristics; chunk `section_title` values are reassigned from inferred line ranges before retrieval. Section-level evidence cards always use the retrieved section title, and grammar execution runs only on chunks inside the selected section range for the matched `target_category`.

## Step 21.4: Semantic boundary enforcement

Extraction is validated against discovered **category boundaries** so grammars do not leak entities from other sections (for example architecture families into a design-pattern answer). `app/evidence/extraction_validator.py` provides `validate_extracted_entity()` and contamination filtering using:

- Category type phrases in the source sentence
- Section scope (entity must come from the category’s discovered section)
- Cross-category entity indexes built from section-scoped grammar runs
- Deterministic rejection of conflicting ordinal lines (e.g. `architecture is` inside a `design_pattern` query)

Grammar execution in `extraction_runtime.py` only scans ordinal enumeration sentences, trims entities at clause boundaries, and records rejected entities for debug trace (`entity_validation_enabled`, `rejected_entities`, `rejection_reason=category_boundary_violation`).

## Step 21.3: Grammar execution runtime

Discovered grammars are now **executable** via `app/evidence/extraction_runtime.py`. The runtime compiles ordinal sentence templates (with optional modifiers such as *critical*, *important*, *common*) into deterministic regexes, extracts `<ENTITY>` values in document order, deduplicates, and reports `extraction_confidence`.

`pattern_extractor.py` and `structured_composer.py` call `execute_discovered_grammar()` so structured answers list extracted entities (numbered list) instead of raw evidence chunks alone. Supporting evidence citations are appended below the structured list. Debug trace may include `grammar_execution_success`, `extracted_entities_count`, `extracted_entities`, and `extraction_confidence`.

## Step 21.2: Dynamic symbolic grammar discovery

After semantic categories are discovered, TraceDoc inspects section text for **repeated extraction grammars** (for example ordinal enumeration: `The first … is …`, `The second … is …`). Grammars are clustered into families such as `ordinal_pattern_enumeration` and stored as `DiscoveredPattern` metadata (`sentence_templates`, `type_phrases`, `confidence_score`).

`pattern_extractor.py` applies these grammars dynamically via `extract_using_discovered_grammar()` — no hand-coded design-pattern rules. Debug trace may include `discovered_grammar`, `grammar_confidence`, and `grammar_sentence_templates`.

## Step 21.1: Schema normalization hardening

Semantic categories are derived from headings via `app/schema/normalization.py`:

- Strips weak suffix phrases (`for implementation`, `overview`, …)
- Maps multi-word phrases (`design patterns`, `building blocks`, …) to stable keys (`design_pattern`, `building_block`)
- Singularizes tokens deterministically without corrupting full headings
- Applies confidence thresholds so vague headings like *Overview* are not stored

Section retrieval uses the loaded document schema to boost sections whose normalized category matches the question. Debug trace may show `normalized_heading='…' -> '…'`, `schema_category_confidence=…`, and `category_match_reason=semantic_heading_normalization`.

## Step 21: Deterministic schema discovery

Each uploaded document gets a **discovered schema** at processing time (`app/schema/`):

- **Semantic categories** from section headings (architecture, design_pattern, capability, …)
- **Extraction styles** from repeated ordinal and grammar forms in section text
- **Pattern registry** mapping categories → discovered pattern names for `pattern_extractor`
- **Graph candidates** — subject-relation-object triples (`uses`, `contains`, `depends on`, …) as a foundation for future graph reasoning

Schemas persist in SQLite (`document_schemas`). At question time, TraceDoc loads the schema, routes list questions to matching categories, and applies discovered patterns before generic fallback — **no LLM and no manual per-domain hardcoding** for each new category.

Debug trace may include: `discovered_categories=[…]`, `schema_category_match=…`, `schema_patterns=[…]`, `graph_candidates_count=NN`.

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
  eval/          Deterministic QA benchmark (docs, questions.yaml, run_eval.py)
  scripts/       smoke_test.py
  tests/         Pytest suite
```

## License / status

Active development. See git history for incremental step commits (ingestion through query interpreter).
