# TraceDoc Engine — Demo Walkthrough

Audience: architects, technical leads, and security reviewers evaluating a **deterministic evidence-based document QA** approach.

## Setup

```bash
cd tracedoc-engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # macOS/Linux

pip install -r requirements.txt
```

## Automated smoke test

Validates unit tests, sample ingestion, indexing, retrieval, and evidence cards:

```bash
python scripts/smoke_test.py
```

Expected output ends with `Smoke test PASSED`.

## Streamlit demo flow

```bash
streamlit run app/main.py
```

1. **Upload** `samples/hpc6_policy.txt` or `samples/requirements_sample.txt`
2. Click **Process document** and note document id, chunk count, and indexed terms
3. **Select** the document in the question section
4. **Ask** a question and click **Search evidence**
5. Review **Detected intent** and **Evidence cards** (citations, confidence, snippets)
6. Scroll to **Audit / Traceability** to show append-only local events

## Sample questions

| Document | Question | Expected intent (approx.) |
|----------|----------|---------------------------|
| `hpc6_policy.txt` | What is HPC6 memory policy? | DEFINITION_LOOKUP |
| `hpc6_policy.txt` | Where is CPU binding mentioned? | WHERE_MENTIONED |
| `requirements_sample.txt` | What is REQ-001? | REQUIREMENT_REFERENCE |
| `hpc6_policy.txt` | List all storage rules | LIST_REQUEST |

## How to explain to an architect

1. **Problem:** Teams need answers with citations, not unverifiable generated prose.
2. **Approach:** Classical IR (inverted index + BM25) over line-anchored chunks.
3. **Guarantee:** No LLM, embeddings, or external APIs—everything runs locally.
4. **Output:** Evidence cards with confidence, citation, and snippet—not an AI answer.
5. **Audit:** SQLite event log for process and query activity.
6. **Future:** Enterprise hooks (SSO, connectors, policy service) documented in `docs/architecture.md` without changing the deterministic core.

## What not to claim

- Not semantic / vector search
- Not a chatbot or ChatGPT replacement
- Not multi-document reasoning beyond simple orchestration helpers
