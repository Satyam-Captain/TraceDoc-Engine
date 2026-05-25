# Architect context (source of truth)

**Last updated:** 2026-05-25 (continuous loop + agent router)  
**Branch:** `feat/deterministic-stack-v2`  
**Architect role:** Plan, gate merges, read `TEST_RESULTS.md`, update `CODER_TASKS.md`. Do not implement production code unless blocking.

**Human coordinator:** paste UI/terminal into `TEST_RESULTS.md`; use `AGENT_ROUTER.md` for which Cursor agent to prompt next.

**Strategy clarification:** We are **not** fixing one PDF at a time. We replace **generic layers** (parse → retrieve → extract). Testing is **continuous** after each slice (S1–S4), with benchmark + your PDF as regression guards.

---

## Mission (few-hour sprint)

Replace brittle paths with a **deterministic 3-layer stack** (Copilot plan) **without LLM, embeddings, or statistical NLP models**.

| Layer | Library | Replaces / augments |
|-------|---------|---------------------|
| 1 Parse | **Docling** (PDF), keep python-docx/txt; optional Tika later | `pypdf` + `pdf_layout` heuristics |
| 2 Retrieve | **Whoosh** BM25 index per document | Custom SQLite BM25 remains fallback until parity |
| 3 Extract | **spaCy `Language.blank("en")` + EntityRuler only** | Extra patterns for requirements; no `en_core_web_sm` |

**Non-negotiables**

- No OpenAI/Anthropic/local LLM APIs
- No vector DB / embeddings
- No spaCy statistical pipelines (`en_core_web_sm`, NER, parser with models)
- Same answer modes: `GRAPH_STRUCTURED`, `STRUCTURED_EXTRACTIVE`, `EVIDENCE_ONLY`, `NO_EVIDENCE`
- Feature flags for safe rollback

---

## Why it fails today

```
Bad PDF lines → sections wrong → section retrieval misses → BM25 fallback → weak/wrong answers
```

`pdf_layout.py` uses hardcoded heading strings — does not generalize.

---

## Target architecture (v2 behind flags)

```
Upload
  → extract_document()  [TRACEDOC_EXTRACTOR=v2 → docling PDF path]
  → structure_document()  [unchanged detector]
  → prepare_document_chunks()  [unchanged]
  → optional: whoosh index build  [TRACEDOC_RETRIEVAL=whoosh]
  → SQLite persist (unchanged)
Question
  → interpret_query (unchanged)
  → if TRACEDOC_RETRIEVAL=whoosh: search whoosh first, else existing BM25
  → section path unchanged
  → optional EntityRuler pass on section text  [TRACEDOC_EXTRACTION=ruler]
  → compose answers (unchanged)
```

---

## Environment flags (coder must implement)

| Variable | Values | Default |
|----------|--------|---------|
| `TRACEDOC_EXTRACTOR` | `v1`, `v2` | `v1` |
| `TRACEDOC_RETRIEVAL` | `sqlite`, `whoosh`, `hybrid` | `sqlite` |
| `TRACEDOC_EXTRACTION` | `grammar`, `ruler`, `both` | `grammar` |

`hybrid` = Whoosh top-k merged with SQLite BM25 scores (deterministic merge: max score, tie by chunk_id).

---

## Sprint slices (implement + test each slice before next)

| Slice | BUILD | TEST (agent) | YOU (paste UI) |
|-------|-------|--------------|----------------|
| S0 | P0 deps | pytest baseline | — |
| S1 | P1 Docling | preflight v1 vs v2 on benchmark + your PDF | UI if GREEN+ |
| S2 | P2 Whoosh | pytest + preflight hybrid | optional |
| S3 | P3 Ruler | pytest | optional |
| S4 | P4 + eval | eval PASS + preflight | full UI round |

See `coordination/AGENT_ROUTER.md` for copy-paste prompts.

---

## Acceptance criteria (sprint exit)

1. `pytest` passes on branch
2. `python eval/run_eval.py` passes with `TRACEDOC_EXTRACTOR=v2` (and retrieval flags documented in TESTER_GUIDE)
3. Preflight on benchmark doc: **READY_FOR_QA** + ≥4 sections including "Existing architectures"
4. User-uploaded failing PDF: preflight improves vs v1 (more sections OR more heading lines)
5. No new dependency that downloads ML weights at runtime

---

## File map (coder touch list)

```
app/ingestion/docling_extractor.py      NEW
app/ingestion/extractor.py              dispatch v2
app/retrieval/whoosh_index.py           NEW
app/retrieval/whoosh_searcher.py        NEW
app/evidence/entity_ruler.py            NEW
requirements-v2.txt                     NEW optional deps
scripts/preflight_tester.py             preflight CLI
coordination/CODER_TASKS.md               task queue
coordination/TEST_RESULTS.md              user paste results
coordination/TESTER_GUIDE.md              when to test
```

---

## Architect decisions log

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Docling before Tika | Python-native, no JVM in 4h sprint |
| D2 | Keep SQLite BM25 as fallback | Avoid breaking storage; Whoosh is additive |
| D3 | spaCy blank only | Copilot compliance without ML models |
| D4 | Do not rewrite graph/schema/qa routing | Too risky in hours; fix foundation first |
| D5 | Preflight script mandatory before UI test | Saves user time |

---

## Current status

| Item | State |
|------|-------|
| Branch `feat/deterministic-stack-v2` | Created |
| Coordination docs | Created |
| P1 Docling | **NOT STARTED** — see CODER_TASKS.md |
| P2 Whoosh | **NOT STARTED** |
| P3 EntityRuler | **NOT STARTED** |
| User test round 1 | **WAITING** |

---

## How architect uses this repo

1. Read this file first every session
2. Read `TEST_RESULTS.md` after user tests
3. Update `CODER_TASKS.md` with next tasks only (no scope creep)
4. Never approve merge to `master` until acceptance criteria met
