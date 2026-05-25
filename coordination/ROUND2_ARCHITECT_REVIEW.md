# Round 2 — Architect review (2026-05-25)

**Slice:** S2 Whoosh (hybrid)  
**Env:** `TRACEDOC_EXTRACTOR=v2`, `TRACEDOC_RETRIEVAL=hybrid`

## Automated (TEST agent)

| Check | Result |
|-------|--------|
| pytest | **PASS** 291 |
| test_whoosh_retrieval | **PASS** 5 |
| eval/run_eval.py | **PASS** 6/6 (100%) |

## UI (your paste)

| # | Question | Strategy | Satisfied? |
|---|----------|----------|------------|
| R2-1 | where does deterministic system wins? | BM25_CHUNK | **YES** — Comparison with LLM-based RAG |
| R2-2 | enterprise usecases before generative AI | BM25_CHUNK | **YES** — Enterprise use cases + architectures |
| R2-3 | what is this document about? | BM25_CHUNK | **NO** — top hit still title line only |
| R2-4 | Why IBM DOORS is mentioned? | SECTION_LEVEL (URL heading) | **PARTIAL** — right URL block, weak explanatory snippet |

## Verdict

**Round 2 SATISFIED** — S2 Whoosh/hybrid **accepted** for sprint.  
**S3 EntityRuler UNBLOCKED.**

Whoosh does not change UI copy ("BM25 over lexical index"); behavior is validated by tests + eval + Q1/Q2 stability vs Round 1b.

## Backlog (not blocking S3/S4)

| ID | Issue | Owner |
|----|-------|-------|
| B1 | URL strings promoted as section titles (DOORS link) | S2.5 or detector normalization |
| B2 | "What is document about" → prefer intro/body chunk not title | query intent or BM25 boost |
| B3 | Show `retrieval_backend=whoosh|sqlite|hybrid` in debug trace | BUILD cosmetic |

## Next

1. **BUILD** → P3 EntityRuler (`CODER_TASKS.md`)
2. After S3 → TEST + UI Round 3
3. After S4 → merge `feat/deterministic-stack-v2` → `master`
