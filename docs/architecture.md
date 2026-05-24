# TraceDoc Engine — Architecture

**Version:** 0.1 (architecture baseline)  
**Audience:** Solution architects, technical leads, security reviewers  
**Companion artifact:** [`architecture.drawio`](architecture.drawio)

---

## 1. Executive summary

TraceDoc Engine is a **local, deterministic document question-answering system**. Users upload documents, ask natural-language questions, and receive **answer cards**: structured responses composed from cited source spans, with full provenance and reproducible ranking.

The system is intentionally **non-generative**. It does not call LLMs, embedding models, or external APIs. All behavior is driven by explicit rules, lexical indexes, and deterministic scoring—making outcomes auditable and suitable for regulated or offline environments.

---

## 2. Design principles

| Principle | Implication |
|-----------|-------------|
| **Determinism** | Same document set, index version, and question yield the same ranked evidence and answer card. |
| **Evidence-first** | Answers are assemblies of cited spans, not paraphrased prose from a model. |
| **Local-only** | Processing and storage remain on the host machine; no network dependency for core paths. |
| **Separation of paths** | Document preparation (offline) and question answering (online) are distinct pipelines sharing storage. |
| **Governance by construction** | Forbidden capabilities (ML, embeddings, cloud inference) are architectural exclusions, not runtime options. |

---

## 3. Logical architecture

The logical architecture comprises twelve concerns. The diagram groups them into presentation, orchestration, two processing pipelines, cross-cutting governance, persistence, and a deferred enterprise envelope.

### 3.1 User Interface

Presents upload workflows, question input, and answer-card browsing. The UI does not implement retrieval logic; it delegates to the Application API Layer.

### 3.2 Application API Layer

The single integration boundary for clients (web UI, CLI, automation). Responsibilities include:

- Request validation and error contracts  
- Orchestration of ingest jobs and query sessions  
- Correlation IDs for audit linkage  
- Response serialization (answer cards, job status, health)

### 3.3 Document Ingestion Pipeline

Accepts source files (initial targets: plain text and common office formats), detects format, normalizes encoding and line endings, computes integrity checksums, and registers a **document manifest** in local storage. No semantic interpretation occurs at this stage.

**Code mapping (planned):** `app/ingestion/`

### 3.4 Structure Extraction Layer

Transforms normalized bytes into a **structured document model**: hierarchical sections, headings, paragraphs, tables, and lists, each with stable anchors (e.g., `docId:section:offset`). Structure is rule- and parser-based, not learned.

**Code mapping (planned):** `app/structure/`

### 3.5 Knowledge Preparation Layer

Builds **lexical artifacts** from the structured model: inverted indexes, term statistics, span registry entries, and document-level metadata required for retrieval. This layer replaces vector embeddings with explicit, inspectable indexes.

**Code mapping (planned):** `app/indexing/`

### 3.6 Rule-Based Query Interpreter

Parses user questions into a **query plan**: tokenized terms, phrase constraints, boolean operators (where supported), document filters, and intent hints derived from pattern rules (e.g., “who”, “when”, “list all”). No neural intent classification.

**Code mapping (planned):** `app/query/`

### 3.7 Deterministic Retrieval Core

Executes the query plan against prepared indexes using reproducible algorithms: exact term lookup, phrase matching, boolean composition, and rank fusion with fixed tie-breaking. Given identical inputs, rank order is stable.

**Code mapping (planned):** `app/retrieval/`

### 3.8 Evidence Engine

Scores candidate spans using transparent rules: term overlap, phrase coverage, structural proximity, and optional confidence thresholds. Attaches **provenance** (document, anchor, snippet offsets) to every candidate. Rejects or downgrades spans that fail governance checks.

**Code mapping (planned):** `app/evidence/`

### 3.9 Answer Card Composer

Assembles the final **answer card**: ordered cited excerpts, source references, match metadata, and a concise structured summary (template-driven, not generated). Returns the card to the API layer for the client.

**Code mapping (planned):** `app/evidence/` (composition) with API response shaping at the boundary.

### 3.10 Local Storage Layer

Persists all durable artifacts on disk:

| Store | Contents |
|-------|----------|
| Raw uploads | Original files under `data/uploads/` |
| Structured artifacts | Parsed document models |
| Indexes | Lexical indexes and span registry |
| Audit log | Append-only decision and request events |
| Answer cache | Optional memoization keyed by (index version, query plan) |

**Code mapping (planned):** `app/storage/`, `data/index/`

### 3.11 Governance / Constraints

A cross-cutting policy envelope (shown as a boundary in the diagram) that defines **non-negotiable exclusions**:

- No large language models or generative AI  
- No machine-learning rankers or classifiers  
- No embedding indexes or approximate nearest-neighbor search  
- No external API calls in core paths  

Audit events record ingest, retrieval, and evidence decisions for later inspection.

**Code mapping (planned):** `app/audit/`, configuration in `config/`

### 3.12 Future Enterprise Upgrade Path

Explicitly **out of scope for v1**, documented to guide extension without compromising the deterministic core:

- SSO / role-based access control  
- Multi-tenant storage partitioning  
- Central policy service (retention, redaction rules)  
- Enterprise connectors (SharePoint, Confluence, etc.)  
- Observability export (metrics, traces) to corporate platforms  

Integration points are shown as dashed hooks from the API layer; v1 implementations must not require these modules.

---

## 4. Data flows

### 4.1 Document preparation (offline)

```
Upload → Ingestion → Structure Extraction → Knowledge Preparation → Local Storage
```

Triggered by user upload or batch ingest API. Produces versioned index artifacts consumed by retrieval.

### 4.2 Question answering (online)

```
Question → Query Interpreter → Retrieval Core ← Local Storage (indexes)
         → Evidence Engine → Answer Card Composer → API → UI
```

Read-heavy on indexes; write append-only audit records. Does not mutate source documents.

---

## 5. Deployment view

| Attribute | v1 target |
|-----------|-----------|
| Topology | Single process or small set of co-located modules on one laptop |
| Network | None required for core operation |
| Dependencies | Python standard library plus explicit document parsers (added per implementation step) |
| Data directories | `data/uploads/`, `data/index/` |

---

## 6. Quality attributes

- **Reproducibility:** Retrieval and evidence scores are pure functions of inputs and index version.  
- **Explainability:** Every answer card line traces to a source anchor.  
- **Privacy:** Documents never leave the machine unless the operator copies them.  
- **Maintainability:** Pipeline stages are independently testable; see `tests/`.  

---

## 7. Non-goals (v1)

- Semantic search via embeddings or transformers  
- Automatic summarization or “chatty” responses  
- Multi-user collaboration or cloud sync  
- Real-time collaborative editing  

---

## 8. Implementation status

Architecture baseline is complete. Application modules under `app/` remain empty placeholders; implementation proceeds step-by-step per the project plan. Update this document when component contracts stabilize.
