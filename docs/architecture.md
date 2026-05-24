# TraceDoc Engine — Architecture (v0.1.0)

**Version:** 0.1.0  
**Status:** Implemented demo release  
**Audience:** Solution architects, technical leads, security reviewers  
**Diagrams:** [`architecture.drawio`](architecture.drawio) (open in [diagrams.net](https://app.diagrams.net))  
**Exported images:** [`images/`](images/) (place PNG/SVG after export — see [`images/README.md`](images/README.md))

---

## 1. Executive summary

TraceDoc Engine is a **local, deterministic document question-answering system**. Users upload PDF, DOCX, or TXT files; the engine builds lexical indexes, a semantic tree, a discovered schema, and a symbolic knowledge graph. Questions receive **verifiable answers** in one of four modes—never free-form generative text.

| Guarantee | Mechanism |
|-----------|-----------|
| No LLM / generative AI | Answers assembled from spans, grammars, and graph edges only |
| No embeddings / vector DB | Inverted index + BM25 + section title matching |
| No external APIs | SQLite + local file I/O |
| Reproducibility | Fixed rules, scores, and tie-breaking |
| Traceability | Evidence cards + append-only audit log + debug trace |

**Entry points:** `app/main.py` (Streamlit), `app/pipeline.py` (`process_document`), `app/qa.py` (`ask_document`), `eval/run_eval.py` (regression benchmark).

---

## 2. Design principles

| Principle | Implementation |
|-----------|----------------|
| Evidence-first | Every claim maps to citation, line range, or graph source sentence |
| Determinism | Same document version + question → same mode, ranking, and extractive text |
| Separation of paths | **Offline** document preparation vs **online** question answering |
| Single extraction source (section path) | Semantic tree section text drives structured answers and evidence (`app/qa_context.py`) |
| Governance by exclusion | ML, embeddings, and cloud inference are out of scope—not runtime toggles |

---

## 3. System context

```
┌─────────────────────────────────────────────────────────────────┐
│  User (browser / CLI / tests)                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
  app/main.py          app/pipeline.py      app/qa.py
  (Streamlit UI)       process_document()   ask_document()
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
                             ▼
              app/storage/  →  SQLite (data/tracedoc.db)
              data/uploads/ , data/index/
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
  eval/run_eval.py                      scripts/smoke_test.py
  (benchmark regression)                (CI + local validation)
```

**Companion diagram pages** in `architecture.drawio`:

1. **System Overview** — components and governance boundary  
2. **Document Processing** — full ingest pipeline  
3. **Question Answering** — retrieval, graph match, answer modes  
4. **Storage & Modules** — SQLite tables and `app/` package map  

---

## 4. Document processing pipeline (offline)

Orchestrated by `process_document()` in `app/pipeline.py`.

```
Upload file
    → app/ingestion/extractor.py
        PDF: pdf_extractor + pdf_layout.reconstruct_pdf_layout()
        DOCX: docx_extractor
        TXT: txt_extractor
        Output: normalized text, SHA-256 checksum, warnings
    → app/structure/ (structure_document)
        detector, heading_heuristics, hierarchy, chunker
        section_assignment, chunk_section
        Output: DocumentSection[], DocumentChunk[]
    → app/indexing/preparation.py (prepare_document_chunks)
        tokenizer, normalizer, stopwords, inverted_index, bm25
    → app/storage/repository.py (save_document_bundle)
        Persist documents, sections, chunks
    → [if new document, not duplicate checksum]
        app/schema/discovery.py → document_schemas
        app/tree/builder.py → document_trees
        app/graph/builder.py → document_graphs
        save_index_bundle → index_terms, chunk_term_frequencies, bm25_statistics
    → app/audit/logger.py → audit_events (document_processed)
```

### 4.1 Ingestion (`app/ingestion/`)

| Module | Role |
|--------|------|
| `extractor.py` | Route by extension; unified `ExtractionResult` |
| `pdf_extractor.py` | Page text via pypdf |
| `pdf_layout.py` | Reconstruct inline headings / paragraph breaks (deterministic regex) |
| `docx_extractor.py` | Paragraphs and tables via python-docx |
| `txt_extractor.py` | Plain text read |

### 4.2 Structure (`app/structure/`)

| Module | Role |
|--------|------|
| `detector.py` | Line-based structure detection |
| `heading_heuristics.py` | Promote probable headings (PDF/plain) |
| `hierarchy.py` | Section levels, parent links, line ranges |
| `chunker.py` | Line-anchored chunks with metadata |
| `section_assignment.py` | Assign chunks to deepest matching section |
| `chunk_section.py` | Section-scoped chunk helpers |

### 4.3 Semantic tree (`app/tree/`)

Built after sections/chunks exist. Stored as JSON in `document_trees`.

```
document
└── section (title, level, line range)
    └── paragraph
        ├── sentence
        ├── list_item
        └── table_row
```

| Module | Role |
|--------|------|
| `builder.py` | `build_document_tree(sections, chunks)` |
| `traversal.py` | `get_section_text()`, `get_section_sentences()`, `iter_nodes()` |
| `models.py` | `DocumentTree`, `TreeNode` |

Section Q&A uses tree text as **primary extraction source**; chunk overlap is fallback when a section has no body nodes.

### 4.4 Schema discovery (`app/schema/`)

| Module | Role |
|--------|------|
| `discovery.py` | Categories from headings; grammar attachment |
| `normalization.py` | Heading → normalized category names |
| `grammar_discovery.py` | Ordinal templates (“The first … is …”) |
| `query_category.py` | Map questions → `architecture`, `design_pattern`, etc. |
| `registry.py` | Pattern registry per category |
| `graph_candidates.py` | Triple candidates for graph builder |

Persisted in `document_schemas.schema_json`: categories, `DiscoveredPattern`, `GraphCandidate`, discovered sections.

### 4.5 Knowledge graph (`app/graph/`)

| Module | Role |
|--------|------|
| `builder.py` | Tree + schema → `KnowledgeGraph` |
| `extractor.py` | Relation patterns: uses, contains, implements, is_a, … |
| `matcher.py` | Match question graph to document graph (scored) |
| `answer_composer.py` | `GRAPH_STRUCTURED` numbered lists |
| `traversal.py` | Graph walk helpers |
| `models.py` | `GraphNode`, `GraphEdge`, `KnowledgeGraph` |

Persisted in `document_graphs.graph_json`.

### 4.6 Indexing (`app/indexing/`)

| Module | Role |
|--------|------|
| `tokenizer.py` | Deterministic tokenization |
| `normalizer.py` | Case folding, stemming rules |
| `stopwords.py` | Filter list |
| `inverted_index.py` | Term → chunk postings |
| `bm25.py` | Corpus statistics, scoring |
| `preparation.py` | Build index bundle per document |

---

## 5. Question answering pipeline (online)

Orchestrated by `ask_document()` in `app/qa.py`.

### 5.1 High-level flow

```
Question
  → app/query/interpreter.py (QueryIntent)
  → app/question_graph/builder.py (symbolic query graph)
  → load document_schema, document_tree, knowledge_graph
  → app/graph/matcher.py (GraphMatch[] — trace + optional answer)
  → if relationship question + score ≥ threshold → GRAPH_STRUCTURED
  → else if section retrieval triggered:
        app/retrieval/section_* + app/qa_context.py (section answer context)
        → STRUCTURED_EXTRACTIVE or EVIDENCE_ONLY
  → else BM25 chunk search (app/retrieval/searcher.py)
        → compose_answer_package → evidence cards
        → optional structured extraction (grammars, patterns)
  → DocumentQAResult + audit_events (question_asked)
```

### 5.2 Query interpreter (`app/query/`)

| Module | Role |
|--------|------|
| `interpreter.py` | `interpret_query()` → `QueryIntent` |
| `rules.py` | Intent patterns: DEFINITION_LOOKUP, WHERE_MENTIONED, LIST_REQUEST, REQUIREMENT_REFERENCE, … |
| `models.py` | `QueryIntent` dataclass |

`build_retrieval_query()` shapes terms for BM25.

### 5.3 Question graph (`app/question_graph/`)

| Module | Role |
|--------|------|
| `builder.py` | `build_question_graph()` — seed entity, relation, category |
| `intent_mapper.py` | Intent → graph seeds |
| `models.py` | `QuestionGraph`, nodes, edges |

Examples:

- `What does Enterprise search stack use?` → entity + `uses` relation  
- `what are different architectures mentioned?` → `mentions` + category `architecture`

### 5.4 Retrieval (`app/retrieval/`)

| Strategy | When | Module |
|----------|------|--------|
| `SECTION_LEVEL` | List/enumeration triggers, section title overlap | `section_searcher.py`, `section_trigger.py`, `section_boost.py` |
| `BM25_CHUNK` | Default / fallback | `searcher.py`, `scorer.py` |

Section path collects chunks inside best section (cap ~20), builds unified `AnswerContext` in `app/qa_context.py`.

### 5.5 Evidence & answers (`app/evidence/`)

| Module | Role |
|--------|------|
| `composer.py` | `compose_answer_package()` — cards from search results |
| `structured_composer.py` | List/ordinal structured answers |
| `extraction_runtime.py` | Execute discovered grammars (regex) |
| `extraction_validator.py` | Category boundary / contamination filter |
| `pattern_extractor.py` | Architecture phrases, bullets, ordinals |
| `symbolic_inference.py` | Deterministic follow-on entity rules |
| `context.py` | Snippet expansion |
| `highlighter.py`, `selector.py` | Card text and ranking helpers |
| `models.py` | `EvidenceCard`, answer mode constants |

### 5.6 Answer mode decision (priority)

| Priority | Mode | Condition |
|----------|------|-----------|
| 1 | `GRAPH_STRUCTURED` | Relationship-style question; `should_use_graph_answer()`; graph cards exist; match score ≥ ~8.0 |
| 2 | `STRUCTURED_EXTRACTIVE` | Section/tree path; grammar or pattern extraction succeeds |
| 3 | `EVIDENCE_ONLY` | Cards returned; no confident structured/graph list |
| 4 | `NO_EVIDENCE` | No reliable spans |

Enumeration questions (`architectures mentioned`, `design patterns`) **skip** graph composition and use section + grammar path even when a graph exists.

Final package selection in `ask_document()`:

```text
if graph_package: use graph
elif section_package: use section
else: BM25 package + _apply_structured_answer()
```

### 5.7 Unified section context (`app/qa_context.py`)

| Function | Role |
|----------|------|
| `resolve_document_tree()` | Load or rebuild tree for Q&A |
| `build_section_answer_context()` | Single `extraction_text` from tree |
| `finalize_answer_context()` | One bundled search result, grammar run, cards |
| `context_debug_trace()` | `extraction_source=DOCUMENT_TREE`, section id, etc. |

Fixes divergence between narrow chunk slices and expanded evidence context.

---

## 6. Persistence (SQLite)

Schema defined in `app/storage/database.py`. Default path: `data/tracedoc.db`.

| Table | Contents |
|-------|----------|
| `documents` | File metadata, full text, checksum (unique), warnings JSON |
| `sections` | Section id, title, level, line range, parent |
| `chunks` | Chunk id, text, type, lines, section link |
| `index_terms` | Vocabulary + document frequency |
| `chunk_term_frequencies` | Term positions per chunk |
| `bm25_statistics` | avgdl, idf/df JSON, chunk lengths, field weights |
| `document_schemas` | `schema_json` per document |
| `document_trees` | `tree_json` per document |
| `document_graphs` | `graph_json` per document |
| `audit_events` | Append-only: process, question, failures |

**Files on disk:** `data/uploads/` (raw uploads), `data/index/` (optional index artifacts).

**Repository API:** `app/storage/repository.py` — save/load bundles, `clear_local_data()` for UI reset.

---

## 7. Cross-cutting concerns

### 7.1 Audit (`app/audit/`)

`log_audit_event()` — event types include `document_processed`, `duplicate_document_detected`, `question_asked`, `question_failed`, `document_processing_failed`.

### 7.2 Evaluation (`app/eval/`, `eval/`)

| Artifact | Role |
|----------|------|
| `eval/benchmark_docs/symbolic_architecture_doc.txt` | Fixed benchmark document |
| `eval/questions.yaml` | Expected modes and substring checks |
| `eval/run_eval.py` | CLI; temp DB; exit code 1 on failure |
| `app/eval/runner.py` | `run_benchmark()`, metrics |

### 7.3 UI (`app/main.py`)

Streamlit: upload/process summary, capabilities panel, suggested questions, answer sections A/B/C, collapsed debug trace.

### 7.4 CI (`.github/workflows/ci.yml`)

Python 3.11 & 3.12: pytest, smoke test, eval benchmark.

---

## 8. Module map (`app/`)

```
app/
├── main.py                 Streamlit UI
├── pipeline.py             process_document()
├── qa.py                   ask_document(), ask_all_documents()
├── qa_context.py           Section answer context (tree-backed)
├── ingestion/              PDF, DOCX, TXT extractors
├── structure/              Sections, chunks, headings
├── tree/                   Semantic document tree
├── schema/                 Category & grammar discovery
├── graph/                  Knowledge graph build, match, answer
├── question_graph/         Symbolic query graph from question
├── indexing/               Tokenizer, inverted index, BM25
├── retrieval/              Section + BM25 search
├── evidence/               Cards, structured extractive, validation
├── query/                  Intent interpreter
├── storage/                SQLite schema + repository
├── audit/                  Event logging
└── eval/                   Benchmark runner library
```

**Tests:** `tests/` (281+ cases). **Samples:** `samples/`. **Scripts:** `scripts/smoke_test.py`.

---

## 9. Deployment view (v0.1.0)

| Attribute | Value |
|-----------|--------|
| Topology | Single Python process (Streamlit or script) |
| Network | None required for core QA |
| Database | Local SQLite per machine |
| Hosting | Streamlit Cloud, LAN (`0.0.0.0`), VM, or tunnel — see README |
| Scale | Single-user demo; not multi-tenant |

---

## 10. Quality attributes

| Attribute | How TraceDoc achieves it |
|-----------|---------------------------|
| Explainability | Mode label, evidence cards, debug trace, audit JSON |
| Privacy | Data stays on host unless operator copies files |
| Testability | Unit tests + smoke + eval benchmark in CI |
| Maintainability | Pipeline stages map 1:1 to packages |

---

## 11. Limitations (v0.1.0)

- Lexical retrieval only — no synonyms or semantic similarity  
- Heading-dependent sections and lists — PDF layout heuristics may miss boundaries  
- Graph answers require entities/edges present in built graph  
- No generative summarization or multi-hop reasoning  
- Duplicate checksum skips re-indexing (schema/tree/graph not rebuilt)  
- Multi-document QA limited to `ask_all_documents()` helper  
- Streamlit Cloud: ephemeral disk — re-upload documents per session  

---

## 12. Future enterprise path (documented, not implemented)

Dashed in diagrams and out of scope for v0.1.0:

- SSO / RBAC  
- Multi-tenant storage partitioning  
- Central policy service (retention, redaction)  
- Connectors (SharePoint, Confluence)  
- Observability export to corporate platforms  

The deterministic core (ingest → index → symbolic QA) should remain unchanged; enterprise features wrap the API boundary.

---

## 13. Diagram export checklist

1. Open `docs/architecture.drawio` in diagrams.net.  
2. Export each of the **4 pages** to `docs/images/` (see [`images/README.md`](images/README.md)).  
3. Optionally embed in README:  
   `![Overview](docs/images/architecture-overview.png)`

---

## 14. Implementation status

| Area | Status |
|------|--------|
| Ingestion → structure → index | ✅ v0.1.0 |
| Semantic tree | ✅ v0.1.0 |
| Schema + grammar discovery | ✅ v0.1.0 |
| Knowledge graph + matcher | ✅ v0.1.0 |
| Question graph | ✅ v0.1.0 |
| GRAPH / STRUCTURED / EVIDENCE / NO_EVIDENCE modes | ✅ v0.1.0 |
| Streamlit demo UI | ✅ v0.1.0 |
| Eval benchmark + GitHub Actions CI | ✅ v0.1.0 |
| Enterprise envelope | 📋 Documented only |

Release tag: **v0.1.0** — see [`CHANGELOG.md`](../CHANGELOG.md).
