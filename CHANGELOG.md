# Changelog

All notable changes to TraceDoc Engine are documented in this file.

## [0.1.0] - 2026-05-24

First stable **demo release**: deterministic symbolic document QA for local laptops—no LLM, embeddings, or external APIs.

### Capabilities

- **Ingestion** — PDF, DOCX, and TXT extraction with SHA-256 deduplication
- **Structure & indexing** — Heading detection, line-anchored chunks, inverted index, BM25 retrieval
- **Semantic tree** — Document → section → paragraph → sentence tree for section-level extraction
- **Schema discovery** — Dynamic categories and symbolic grammar patterns from document headings
- **Knowledge graph** — Deterministic subject–relation–object edges (`uses`, `contains`, `implements`, …)
- **Question graph & matcher** — Symbolic query graph matched against the document graph
- **Answer modes**
  - `STRUCTURED_EXTRACTIVE` — Section/tree + grammar enumeration
  - `GRAPH_STRUCTURED` — Relationship answers from graph matches
  - `EVIDENCE_ONLY` — Citation-first evidence cards
  - `NO_EVIDENCE` — Explicit fallback when nothing reliable is found
- **Query interpreter** — Rule-based intent detection (definition, where-mentioned, list, requirement ID, …)
- **Audit** — Append-only local SQLite event log
- **Streamlit UI** — Upload, process, ask, capabilities panel, suggested demo questions
- **Evaluation benchmark** — `eval/run_eval.py` with PASS/FAIL regression suite
- **CI** — GitHub Actions on Python 3.11 and 3.12 (pytest, smoke test, eval)

### Limitations (v0.1.0)

- Single-machine, single-user; not a multi-tenant product
- Lexical retrieval only—no embeddings, synonym expansion, or semantic search
- Answers are extractive or graph-derived, not generative summaries
- Section and list quality depend on heading detection and PDF layout reconstruction
- Graph answers require matching entities and relations present in the built graph
- No multi-hop reasoning or cross-document inference beyond simple helpers
- PDF/DOCX quality varies with source formatting

### Release & demo commands

```bash
git clone https://github.com/Satyam-Captain/TraceDoc-Engine.git
cd TraceDoc-Engine
git checkout v0.1.0

python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate           # macOS/Linux
pip install -r requirements.txt

python -m pytest
python scripts/smoke_test.py
python eval/run_eval.py
streamlit run app/main.py
```

Recommended demo documents: `samples/system_architectures.txt`, `eval/benchmark_docs/symbolic_architecture_doc.txt`, `samples/hpc6_policy.txt`. See [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md).

[0.1.0]: https://github.com/Satyam-Captain/TraceDoc-Engine/releases/tag/v0.1.0
