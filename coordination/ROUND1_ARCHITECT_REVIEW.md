# Round 1 — Architect review (2026-05-25)

**Document:** `docs/Deterministic Document Question Answering Without AI or LLMs.pdf`  
**Raw UI paste:** see `TEST_RESULTS.md`

## Results

| # | Question | Mode | Satisfied? |
|---|----------|------|------------|
| 1 | enterprise usecases before generative AI | EVIDENCE_ONLY (title snippet only) | **NO** |
| 2 | where does deterministic system wins? | EVIDENCE_ONLY (good BM25 hit) | **YES** |
| 3 | explain use cases before generative AI | EVIDENCE_ONLY (title snippet only) | **NO** |

## Diagnosis (generic, not one-PDF hack)

1. **Stale index:** UI shows `chunk_count=105`; fresh v2 preflight shows **43 chunks**. You likely processed before v2 install or duplicate checksum kept old v1 data.
2. **Title-section trap:** Section retrieval picked `Deterministic Document Question Answering Without AI or LLMs` (lines 1–2). Debug: `tree_section_empty_fallback=True`, `extraction_text_preview` = title only.
3. **Docling OK on fresh run:** GREEN+ with sections including Existing architectures, Comparison with LLM-based RAG. Warnings: `docling_partial_success` (pages 6–8 memory) — still usable.

## Verdict

**Round 1 NOT SATISFIED.** S2 Whoosh **blocked** until S1.5 + Round 1b.

## Your actions (Round 1b)

1. Stop Streamlit (Ctrl+C)
2. Delete `data/tracedoc.db`
3. Restart:
   ```powershell
   $env:TRACEDOC_EXTRACTOR="v2"
   .\.venv\Scripts\streamlit run app/main.py
   ```
4. Upload PDF again → Process (wait for Docling; may take ~1 min)
5. Confirm process summary shows **43 chunks** (not 105)
6. Re-ask same 3 questions; paste into `TEST_RESULTS.md` under heading `## Round 1b`
7. Message architect: `review Round 1b`

## Better test questions (match doc structure)

After re-index, also try:

- `what are different architectures mentioned in the pdf?` → expect STRUCTURED_EXTRACTIVE
- `what are different design patterns mentioned in the pdf?` → expect STRUCTURED_EXTRACTIVE

Your original questions are valid GENERAL_SEARCH — should return **body** evidence after S1.5 fix, not only title.

## Next agent: BUILD (S1.5)

See `coordination/CODER_TASKS_S1.5.md` — copy BUILD prompt from `AGENT_ROUTER.md` when added.
