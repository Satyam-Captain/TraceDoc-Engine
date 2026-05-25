# Coder tasks — S1.5 hotfix (before S2 Whoosh)

**Triggered by:** Round 1 architect review — title-section trap + empty tree fallback.

**Branch:** `feat/deterministic-stack-v2`

---

## T1.5.1 — Penalize title-only sections in section search (GENERIC)

**File:** `app/retrieval/section_searcher.py` and/or `section_boost.py`

When scoring candidate sections:

- If section body is ≤2 lines AND title matches document filename/title → score penalty (e.g. multiply by 0.25) or exclude from `selected_section` unless no other candidate ≥ threshold.
- Must not hardcode "Deterministic Document..." string — use rule: `end_line - start_line <= 2` and high title/token overlap with document name.

**Test:** `tests/test_section_retrieval_bugfix.py` or new test with synthetic sections.

---

## T1.5.2 — Empty tree section → BM25 fallback inside document

**File:** `app/qa_context.py`

When `tree_section_empty_fallback=True` and `extraction_sentence_count=0`:

- Do not return title-only `extraction_text` as final context.
- Fall back to BM25 search scoped to chunks in/under that section OR top document BM25 hits (same as `using_bm25_fallback=True`).

**Test:** unit test with empty tree section + chunk with real body in child section.

---

## T1.5.3 — Surface extractor version in process UI summary (optional, 10 min)

**File:** `app/main.py` — show `metadata.extractor_version` and warning `docling_partial_success` after process.

---

## Verify

```powershell
pytest -q tests/test_section_retrieval*.py tests/test_tree*.py
$env:TRACEDOC_EXTRACTOR="v2"
python scripts/preflight_tester.py "docs/Deterministic Document Question Answering Without AI or LLMs.pdf"
```

Reply: `BUILD_DONE slice=S1.5`

---

## Done notes

| Task | Status | Notes |
|------|--------|-------|
| T1.5.1 | | |
| T1.5.2 | | |
| T1.5.3 | | |
