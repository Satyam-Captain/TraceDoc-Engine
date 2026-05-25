# Agent router — what you tell each Cursor agent

**Your job only:** paste outputs into `TEST_RESULTS.md` → come back here → copy the next prompt to the right agent.

**Not one-PDF fixes:** every task must work for **any** PDF/DOCX/TXT via libraries + flags, never hardcoded heading strings for one file.

---

## Agents (use separate Cursor chats)

| Agent | Chat name suggestion | Does |
|-------|---------------------|------|
| **BUILD** | TraceDoc BUILD | Implements `CODER_TASKS.md` on branch `feat/deterministic-stack-v2` |
| **TEST** | TraceDoc TEST | Runs pytest, eval, preflight; updates `TEST_RESULTS.md` technical sections |
| **YOU** | — | Streamlit UI, paste UI answers into `TEST_RESULTS.md`, tell architect "review Round N" |

---

## Continuous loop (implement + test every step)

```text
BUILD completes task slice → TEST runs preflight/pytest → YOU paste UI if GREEN → Architect reviews → next BUILD prompt
```

Do **not** wait until all of P1–P4 finish before testing. Test after **each slice** below.

---

## Current sprint order (generic stack)

| Slice | BUILD finishes | TEST runs | YOU tests UI when |
|-------|----------------|-----------|-------------------|
| S0 | P0 setup + deps | `pytest -q` | Never |
| S1 | P1 Docling + flag | preflight v1 vs v2 on **2+ files** | TEST says GREEN on your PDF |
| S2 | P2 Whoosh + flag | pytest + preflight | optional BM25 questions |
| S3 | P3 EntityRuler | pytest | requirement-style questions |
| S4 | P4 full flags | `eval/run_eval.py` | full question set in TESTER_GUIDE |

**Regression guard:** after each slice, TEST must run preflight on:

1. `eval/benchmark_docs/symbolic_architecture_doc.txt` (must stay GREEN+)
2. Your failing PDF (should improve vs Round 0, not only pass one question)

---

## COPY-PASTE PROMPTS (use now)

### → BUILD agent (start now if S0 not done)

```
You are the BUILD agent for TraceDoc.

Branch: feat/deterministic-stack-v2
Read: coordination/ARCHITECT_CONTEXT.md and coordination/CODER_TASKS.md

Rules:
- Generic solutions only (Docling, Whoosh, spaCy blank EntityRuler). NO new hardcoded heading strings in pdf_layout for one document.
- No LLM, no embeddings, no en_core_web_sm.
- Implement P0 then P1 completely. Mark [x] in CODER_TASKS.md when done.
- Commit and push when P1 tests pass.

When done, reply exactly:
BUILD_DONE slice=S1
Files changed: (list)
Commands to verify: (list)
```

### → TEST agent (after BUILD says BUILD_DONE slice=S1)

```
You are the TEST agent for TraceDoc.

Branch: feat/deterministic-stack-v2
Read: coordination/TESTER_GUIDE.md

Run:
1. pytest -q
2. preflight v1: python scripts/preflight_tester.py eval/benchmark_docs/symbolic_architecture_doc.txt
3. preflight v2: $env:TRACEDOC_EXTRACTOR="v2"; python scripts/preflight_tester.py eval/benchmark_docs/symbolic_architecture_doc.txt
4. If samples/*.pdf exist, preflight those too v1 and v2.

Append all terminal output to coordination/TEST_RESULTS.md under "## Round 1 - TEST agent auto"
Compare section counts v1 vs v2 (generic improvement, not one-doc hack).

Reply exactly:
TEST_DONE slice=S1 gate=(RED|YELLOW|GREEN|GREEN+)
pytest: PASS|FAIL
eval: skip until S4
```

### → YOU (human) — after TEST_DONE gate=GREEN or GREEN+

1. Set env (PowerShell):

```powershell
$env:TRACEDOC_EXTRACTOR="v2"
streamlit run app/main.py
```

2. Upload **same PDF** as Round 0.
3. Ask the 3 questions from `coordination/TESTER_GUIDE.md`.
4. Paste into `TEST_RESULTS.md` → **Round 1 — UI (human)** table.
5. Tell **architect chat**: `review Round 1`

### → BUILD agent (slice S2, after architect approves S1 or fixes listed)

```
BUILD agent: implement CODER_TASKS P2 (Whoosh) on feat/deterministic-stack-v2.
Keep SQLite BM25 as fallback. TRACEDOC_RETRIEVAL=whoosh|hybrid.
Generic only. Commit push. Reply: BUILD_DONE slice=S2
```

### → TEST agent (slice S2)

```
TEST agent: pytest -q, preflight with TRACEDOC_EXTRACTOR=v2 and TRACEDOC_RETRIEVAL=hybrid on benchmark txt + user PDF path if documented in TEST_RESULTS.
Update TEST_RESULTS.md. Reply: TEST_DONE slice=S2 gate=...
```

### → BUILD agent (slice S3–S4)

Same pattern: P3 EntityRuler → TEST → P4 integration + eval → TEST runs eval → YOU UI test → architect review Round 2.

---

## What architect needs from you

Minimum message when pasting results:

```text
review Round 0
```

or

```text
review Round 1
(BUILD_DONE S1, TEST_DONE GREEN, UI pasted in TEST_RESULTS)
```

---

## If BUILD and TEST are one Cursor agent

Use one chat but **two phases** in the prompt:

```
Phase 1: Implement P1 per CODER_TASKS.md, commit push.
Phase 2: Run pytest and preflight v1/v2, write output to TEST_RESULTS.md Round 1.
End with: BUILD_TEST_DONE slice=S1 gate=...
```

Then you only do UI paste + `review Round 1` to architect.

---

## Status board (human updates mentally)

| Slice | BUILD | TEST | UI (you) | Architect |
|-------|-------|------|----------|-----------|
| S0 | ⬜ | ⬜ | — | — |
| S1 | ⬜ | ⬜ | ⬜ | ⬜ |
| S2 | ⬜ | ⬜ | ⬜ | ⬜ |
| S3 | ⬜ | ⬜ | ⬜ | ⬜ |
| S4 | ⬜ | ⬜ | ⬜ | ⬜ |

---

## Anti-patterns (reject in code review)

- Adding your PDF filename or title strings to `pdf_layout.py` `_KNOWN_INLINE_HEADINGS`
- Skipping tests because "it works on my PDF once"
- Merging without benchmark `eval/run_eval.py` PASS on v2 flags
