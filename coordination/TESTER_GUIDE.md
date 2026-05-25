# Tester guide — when and how to test

**You are the tester.** The coder implements; the architect judges `TEST_RESULTS.md`.

---

## Testing gates (read preflight first)

Run preflight **before** opening Streamlit:

```powershell
cd c:\Users\satti\Desktop\tracedoc-engine
$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
$env:TRACEDOC_EXTRACTION="both"
python scripts/preflight_tester.py "C:\path\to\your\document.pdf"
```

| Gate | Meaning | What you should do |
|------|---------|-------------------|
| **RED — NOT_READY** | Extraction failed or text almost empty | Do not UI test; paste output in TEST_RESULTS.md; wait for coder P1 |
| **YELLOW — STRUCTURE_WEAK** | &lt; 2 sections or no line-break headings | UI test only evidence questions; list questions will likely fail |
| **GREEN — READY_FOR_QA** | ≥ 2 sections, extractor ok | Upload in Streamlit, run suggested questions below |
| **GREEN+ — READY_FOR_EVAL** | Benchmark sections detected | Run `python eval/run_eval.py` then UI |

---

## Right time to test (timeline)

| When | Action |
|------|--------|
| **Now (P0 done)** | Baseline only: preflight with `TRACEDOC_EXTRACTOR=v1` on your failing PDF — record in TEST_RESULTS |
| **After coder marks P1 done** | Preflight v2 on same PDF; compare section count and titles |
| **After coder marks P2 done** | Preflight + ask BM25-style question in UI with `TRACEDOC_RETRIEVAL=whoosh` |
| **After coder marks P3–P4 done** | Full UI session + eval benchmark |
| **After architect OK** | Merge branch (architect instructs) |

**Do not** spend time on Streamlit until preflight is at least **YELLOW** for your document.

---

## One-time install (required before v2 UI)

Streamlit uses your project `.venv`. Docling is **not** in `requirements.txt` only — install v2 stack once:

```powershell
cd c:\Users\satti\Desktop\tracedoc-engine
.\.venv\Scripts\pip install -r requirements.txt -r requirements-v2.txt
.\.venv\Scripts\python -c "import docling; print('docling OK')"
```

If you see `No module named 'docling'`, you skipped this step or Streamlit is not using `.venv`.

**Restart Streamlit** after install (stop terminal Ctrl+C, start again).

## Environment for UI test (PowerShell)

```powershell
$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
$env:TRACEDOC_EXTRACTION="both"
.\.venv\Scripts\streamlit run app/main.py
```

Clear old DB if you need a clean run (UI or delete `data/tracedoc.db`).

---

## Suggested questions (paste answers into TEST_RESULTS.md)

Use questions that match your doc. For architecture-style PDFs like the benchmark:

1. `what are different architectures mentioned in the pdf?`  
   - **Expect:** `STRUCTURED_EXTRACTIVE`, section "Existing architectures", numbered list entities

2. `what are different design patterns mentioned in the pdf?`  
   - **Expect:** `STRUCTURED_EXTRACTIVE`, section "Design patterns…"

3. `What does Enterprise search stack use?`  
   - **Expect:** `GRAPH_STRUCTURED` or strong evidence with "repository connectors"

4. One **your own** question that failed before

---

## What preflight predicts (not guarantees)

Preflight prints **likely** outcomes based on structure only:

- If your list section is detected → predicts `STRUCTURED_EXTRACTIVE` for list questions
- If graph keywords in text but graph not built until process → UI still needs upload/process first
- Whoosh flag off → predicts BM25_CHUNK fallback for non-section questions

**Final answers only exist after:** process document in UI + ask question.

---

## What to record in TEST_RESULTS.md

For each test round:

1. File name and checksum (from preflight)
2. Env flags used
3. Preflight gate (RED/YELLOW/GREEN)
4. Section titles listed by preflight
5. Each question + **Answer mode** + first 3 lines of answer + debug trace lines (optional)
6. Satisfied? YES/NO and what was wrong

---

## Quick eval (regression)

```powershell
$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
python eval/run_eval.py
```

All PASS → safe for architect review.
