# Coder tasks — active sprint

**Branch:** `feat/deterministic-stack-v2`  
**Read first:** `coordination/ARCHITECT_CONTEXT.md`  
**Update this file:** Mark `[x]` when done; add PR notes in **Done notes** section.

---

## P0 — Setup (15 min)

- [ ] **T0.1** Pull branch `feat/deterministic-stack-v2`
- [ ] **T0.2** Create `requirements-v2.txt`:

```text
docling>=2.0
whoosh>=2.7
spacy>=3.7
```

- [ ] **T0.3** Install: `pip install -r requirements.txt -r requirements-v2.txt`
- [ ] **T0.4** Verify spaCy blank (no model download):

```python
from spacy.lang.en import English
nlp = English()
assert not nlp.pipe_names  # or only entity_ruler after add
```

- [ ] **T0.5** Run baseline: `pytest -q` (must pass before changes)

---

## P1 — Docling PDF extraction (90 min) — CRITICAL PATH

- [ ] **T1.1** Add `app/ingestion/docling_extractor.py`

  - Function: `extract_pdf_docling(file_path: str) -> tuple[str, int | None, dict, list[str]]`
  - Use Docling to convert PDF → markdown or plain text with line breaks
  - Normalize: `\r\n` → `\n`, collapse 3+ newlines to 2
  - Warnings list: e.g. `"docling_v2"`, page count if available
  - On Docling failure: raise with clear message (no silent fallback to pypdf in v2 mode)

- [ ] **T1.2** Update `app/ingestion/extractor.py`

  - Read `os.environ.get("TRACEDOC_EXTRACTOR", "v1").lower()`
  - If `v2` and extension `.pdf`: call `extract_pdf_docling`
  - Else: existing behavior
  - Add metadata key `extractor_version: v1|v2`

- [ ] **T1.3** Tests `tests/test_docling_extractor.py`

  - Skip if docling not installed (`pytest.importorskip`)
  - Use smallest PDF in `samples/` or create tiny fixture
  - Assert non-empty text and `\n` in output

- [ ] **T1.4** Do **not** delete `pdf_layout.py` yet; v1 path unchanged

**Done when:** `TRACEDOC_EXTRACTOR=v2 pytest tests/test_docling_extractor.py -q` passes

---

## P2 — Whoosh BM25 retrieval (90 min)

- [ ] **T2.1** Add `app/retrieval/whoosh_index.py`

  - Schema fields: `chunk_id` (ID, stored), `text` (TEXT), `section_id` (TEXT)
  - `build_whoosh_index(document_id, chunks, index_dir: Path) -> Path`
  - Store under `data/index/whoosh/{document_id}/`
  - Use BM25 similarity (Whoosh default)

- [ ] **T2.2** Add `app/retrieval/whoosh_searcher.py`

  - `search_whoosh(index_path, query: str, limit: int = 10) -> list[SearchResult]`
  - Map Whoosh hits → existing `SearchResult` model (same as BM25 searcher)

- [ ] **T2.3** Hook `app/pipeline.py` after `prepare_document_chunks`

  - If `TRACEDOC_RETRIEVAL` in (`whoosh`, `hybrid`): build Whoosh index
  - Log warning in `ProcessedDocumentResult.warnings` if index build fails

- [ ] **T2.4** Hook `app/qa.py` / `app/retrieval/searcher.py`

  - If `whoosh`: use Whoosh only for chunk search
  - If `hybrid`: run both, merge by max score, deterministic tie-break `chunk_id`
  - Section retrieval path **unchanged** (still primary for list questions)

- [ ] **T2.5** Tests `tests/test_whoosh_retrieval.py` with temp dir

**Done when:** `TRACEDOC_RETRIEVAL=whoosh pytest tests/test_whoosh_retrieval.py -q` passes

---

## P3 — spaCy EntityRuler (60 min) — NO ML MODEL

- [ ] **T3.1** Add `app/evidence/entity_ruler.py`

  - `build_ruler_nlp()` → `Language.blank("en")` + `entity_ruler`
  - Patterns (minimum):
    - `REQUIREMENT`: `[{"LOWER": "must"}, {"IS_ALPHA": True, "OP": "+"}]`
    - `REQUIREMENT`: `[{"LOWER": "shall"}, ...]`
    - `DEFINITION`: `[{"LOWER": "is"}, {"LOWER": "defined"}, {"LOWER": "as"}]` (token window)
  - `extract_ruler_entities(text: str) -> list[dict]` with `label`, `text`, `start`, `end`

- [ ] **T3.2** Integrate in `app/evidence/structured_composer.py` or `pattern_extractor.py`

  - Only when `TRACEDOC_EXTRACTION` in (`ruler`, `both`)
  - Append ruler entities to debug trace; do not replace grammar extraction

- [ ] **T3.3** Test `tests/test_entity_ruler.py` — deterministic spans on sample sentence

**Done when:** No `spacy download` in CI; blank English only

---

## P4 — Integration & preflight (45 min)

- [ ] **T4.1** Ensure `scripts/preflight_tester.py` runs (architect added; extend if needed)

  - Report `extractor_version`, section titles, gate status

- [ ] **T4.2** Document flags in `coordination/TESTER_GUIDE.md` (architect owns; coder add env examples if new flags)

- [ ] **T4.3** Run full gate:

```powershell
$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
$env:TRACEDOC_EXTRACTION="both"
pytest -q
python eval/run_eval.py
python scripts/preflight_tester.py samples/your_test.pdf
```

- [ ] **T4.4** Commit coder changes with message: `feat(v2): docling + whoosh + entity ruler behind env flags`

---

## Explicitly OUT OF SCOPE (do not implement)

- LLM / Ollama / OpenAI
- `en_core_web_sm` or any `spacy download`
- Neo4j, Tika/JVM (post-sprint)
- Rewriting `detector.py`, graph matcher, or Streamlit UI (unless 1-line env display)

---

## Done notes (coder fills in)

| Task | Status | Notes |
|------|--------|-------|
| P0 | | |
| P1 | | |
| P2 | | |
| P3 | | |
| P4 | | |

---

## Blockers → ping architect

List here if stuck >15 min:

1. 
