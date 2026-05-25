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

### → BUILD agent (slice S1.5 — NOW, before S2)

```
You are the BUILD agent for TraceDoc.

Branch: feat/deterministic-stack-v2
Read: coordination/CODER_TASKS_S1.5.md

Implement T1.5.1 and T1.5.2 (generic rules only, no document-specific strings).
pytest must pass. Commit push.

Reply: BUILD_DONE slice=S1.5
```

### → TEST agent (slice S2 — NOW)

```
You are the TEST agent for TraceDoc.

Branch: feat/deterministic-stack-v2
git pull

Run:
1. python -m pytest -q
2. $env:TRACEDOC_EXTRACTOR="v2"; $env:TRACEDOC_RETRIEVAL="hybrid"; python -m pytest tests/test_whoosh_retrieval.py -q
3. python eval/run_eval.py  (with same env vars)
4. Process + preflight optional on benchmark txt

Append output to coordination/TEST_RESULTS.md under "## Round 2 - TEST agent"

Reply: TEST_DONE slice=S2 pytest=PASS eval=PASS|FAIL
```

### → YOU (human) — after TEST_DONE pytest=PASS

**Re-process is required** — Whoosh index is built at process time.

```powershell
git pull
$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
.\.venv\Scripts\streamlit run app/main.py
```

1. Delete `data/tracedoc.db` OR upload with new name (so document re-processes)
2. Process PDF — check warnings mention whoosh index / no index failure
3. Ask:
   - `where does deterministic system wins?` (BM25/hybrid path)
   - `enterprise usecases before generative AI`
   - `what are different design patterns mentioned?`
4. Paste UI + note `retrieval_strategy` / debug `whoosh` lines into TEST_RESULTS.md `## Round 2 - UI`
5. Tell architect: `review Round 2`

### → BUILD agent (slice S3 — after Round 2 OK)

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

### → TEST agent (slice S3 / P4 gate — NOW)

```
You are the TEST agent for TraceDoc.

Branch: feat/deterministic-stack-v2
git pull

$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
$env:TRACEDOC_EXTRACTION="both"

Run:
1. python -m pytest -q
2. python -m pytest tests/test_entity_ruler.py -q
3. python eval/run_eval.py
4. python scripts/preflight_tester.py eval/benchmark_docs/symbolic_architecture_doc.txt

Append to coordination/TEST_RESULTS.md under "## Round 3 - TEST agent"

Reply: TEST_DONE slice=S3 pytest=PASS eval=PASS
```

### → YOU (human) — after TEST pass

```powershell
git pull
$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
$env:TRACEDOC_EXTRACTION="both"
.\.venv\Scripts\streamlit run app/main.py
```

Re-process doc if needed. Ask any question; expand **C. Debug trace** and confirm lines like:
`entity_ruler_count=...` `entity_ruler_REQUIREMENT=...`

Paste debug trace + answer into TEST_RESULTS.md `## Round 3 - UI`
Tell architect: review Round 3

### → BUILD agent (slice S4 — after Round 3 OK)

```
P4 in CODER_TASKS.md: mark T4.1-T4.4, update TESTER_GUIDE with full v2 env block, README note on requirements-v2.txt.
Commit: feat(v2): complete deterministic stack behind env flags
BUILD_DONE slice=S4
```

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
| S0 | ✅ | ⬜ | — | — |
| S1 BUILD | ✅ | ⬜ | UI R1 fail | Review done |
| S1.5 hotfix | ✅ | — | R1b pass | ✅ |
| S2 Whoosh | ✅ | ✅ | R2 pass | ✅ |
| S3 Ruler | ✅ | ⬜ | Round 3 UI | — |
| S4 Final | ⬜ | ⬜ | merge | — |
| S3 | ⬜ | ⬜ | ⬜ | ⬜ |
| S4 | ⬜ | ⬜ | ⬜ | ⬜ |

---

## Anti-patterns (reject in code review)

- Adding your PDF filename or title strings to `pdf_layout.py` `_KNOWN_INLINE_HEADINGS`
- Skipping tests because "it works on my PDF once"
- Merging without benchmark `eval/run_eval.py` PASS on v2 flags
