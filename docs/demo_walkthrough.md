# TraceDoc Engine — Architect Demo Walkthrough

Audience: enterprise architects, technical leads, and security reviewers evaluating **deterministic, evidence-backed document intelligence** without generative AI.

---

## Problem statement

Teams need answers they can **verify**: citations, source lines, and explicit reasoning paths—not ungrounded prose from a language model. TraceDoc targets regulated and engineering domains where “the model said so” is not acceptable.

## Constraint (non-negotiable)

| Allowed | Not allowed |
|---------|-------------|
| Local SQLite + file storage | LLM / chat completion APIs |
| BM25 lexical retrieval | Embeddings / vector databases |
| Regex and symbolic rules | ML classifiers or NER models |
| Deterministic graph matching | External cloud inference |

Everything in the demo runs on the laptop in front of the audience.

## Architecture story (5 minutes)

1. **Ingest** — PDF, DOCX, or TXT → normalized text, sections, line-anchored chunks.
2. **Structure** — Semantic tree (document → section → paragraph → sentence).
3. **Schema** — Categories and symbolic grammars discovered from headings and repeated patterns.
4. **Graph** — Subject–relation–object edges from tree + schema (uses, contains, implements, etc.).
5. **Question** — Rule-based intent + question graph (no model).
6. **Answer** — One of: structured extractive list, graph-based relationship list, or evidence cards only.
7. **Audit** — Append-only event log for process and query activity.

Point to the **Capabilities** panel in the Streamlit UI while narrating this stack.

## Setup

```bash
cd tracedoc-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

### Automated checks (run before the meeting)

```bash
python -m pytest
python scripts/smoke_test.py
python eval/run_eval.py
```

All three should pass. The eval benchmark proves architecture, grammar, graph, and evidence-only paths without clicking the UI.

## Demo script (15–20 minutes)

### 1. Open the app

```bash
streamlit run app/main.py
```

**Show first:**

- Title: **TraceDoc Engine** — *Deterministic Symbolic Document Intelligence*
- Subtitle constraints: **No LLM | No AI | No Embeddings | Local Only**
- Blue info banner: TraceDoc does **not** generate free-form AI answers
- **Capabilities** panel (six bullets)

### 2. Process a document

**Option A — policy sample (evidence-only path)**

- Upload `samples/hpc6_policy.txt` → **Process document**
- Processing summary: document ID, sections, chunks, schema categories, graph counts

**Option B — architecture sample (structured + graph paths)**

- Upload `samples/system_architectures.txt` or `eval/benchmark_docs/symbolic_architecture_doc.txt`
- Note schema categories and non-zero graph nodes/edges when available

### 3. Ask questions (use suggested buttons)

Select the document, then click a **Suggested demo question** or type your own.

| Goal | Example question | What to highlight |
|------|------------------|-------------------|
| List / grammar | *what are different architectures mentioned?* | **A. Answer** → STRUCTURED_EXTRACTIVE + section retrieval |
| Design patterns | *what are different design patterns mentioned?* | Same mode; different section |
| Graph relation | *What does Enterprise search stack use?* | GRAPH_STRUCTURED + graph caption |
| Graph relation | *What does Classic QA pipeline contain?* | Numbered list from graph edges |
| Evidence only | *Where is CPU binding mentioned?* (HPC sample) | EVIDENCE_ONLY + cards |

### 4. Walk through the answer layout

For each question, scroll in order:

1. **Detected intent** and **Retrieval strategy**
2. **A. Answer** — mode label with human-readable explanation
3. **B. Supporting evidence** — citation, confidence, snippet (first card expanded)
4. **C. Debug trace** — collapsed by default; expand only if the audience asks “how did it decide?”

### 5. Audit trail

Scroll to **Audit / Traceability**. Show `document_processed` and `question_asked` events with JSON details.

### 6. Optional: CLI proof

```bash
python eval/run_eval.py
```

Show the PASS/FAIL table—same logic as the UI, suitable for CI and regression gates.

---

## What to show

- Constraints banner and sidebar (local-only, no AI)
- Processing summary with schema categories and graph stats
- Three answer styles (structured, graph, evidence-only) with **honest mode labels**
- Evidence cards with citations—not invented summaries
- Collapsed debug trace as “inspectability without noise”
- Audit log for traceability narrative

## What not to claim

| Do not say | Say instead |
|------------|-------------|
| “AI-powered answers” | “Deterministic answers from evidence and symbolic rules” |
| “Understands meaning like ChatGPT” | “Lexical retrieval + section/tree/graph rules” |
| “Semantic search” | “BM25 + section title matching” |
| “Always correct” | “Answers only when extractable evidence or graph matches exist” |
| “Multi-document reasoning” | “Single-document QA in v1; simple multi-doc helpers only” |

## Sample question cheat sheet

**Architecture / symbolic documents**

- what are different architectures mentioned?
- what are different design patterns mentioned?
- What does Enterprise search stack use?
- What does Classic QA pipeline contain?

**Policy / requirements documents**

- What is HPC6 memory policy?
- Where is CPU binding mentioned?
- What is REQ-001?
- List all storage rules

## Current limitations (be upfront)

- Heading quality drives section and list answers; messy PDFs may need re-processing after layout reconstruction.
- No synonym expansion—wording must overlap indexed terms or section titles.
- Graph answers require relationship phrases present in the built graph.
- No generative summarization or multi-hop inference.
- Re-process documents after pipeline upgrades (or use **Clear all local data** in the sidebar).

## Related docs

- [`README.md`](../README.md) — capabilities table, quick start, demo flow
- [`docs/architecture.md`](architecture.md) — enterprise path (SSO, connectors) without changing the deterministic core
