# Manual test — Franz-Kafka.pdf (pre-merge)

**File:** `docs/Franz-Kafka.pdf` (88 pages; Docling **partial** — only ~4.7k chars / first ~5 pages indexed in preflight)

**Important:** Many pages failed with `std::bad_alloc`. UI answers only reflect **extracted** text, not the full book. This is a stress test for v2 on a **literary PDF**, not the enterprise Deterministic doc.

**Preflight (architect run):** GREEN+ — 10 sections, 24 chunks, `docling_partial_success`

**Sections detected:**

- THE METAMORPHOSIS
- Franz kafka
- SYNOPSIS OF THE METAMORPHOSIS
- Spanish / Portuguese / French InfoLibros blocks
- C H A P T E R I

---

## How to start (every session)

```powershell
cd c:\Users\satti\Desktop\tracedoc-engine
git checkout feat/deterministic-stack-v2
git pull

.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-v2.txt

$env:TRACEDOC_EXTRACTOR="v2"
$env:TRACEDOC_RETRIEVAL="hybrid"
$env:TRACEDOC_EXTRACTION="both"

# Optional: clean DB so this PDF re-processes with Whoosh index
Remove-Item -Force data\tracedoc.db -ErrorAction SilentlyContinue

.\.venv\Scripts\streamlit run app/main.py
```

1. Open http://localhost:8501  
2. Upload **`docs/Franz-Kafka.pdf`** → **Process** (wait 1–3 min first time)  
3. Confirm processing: **~24 chunks** (not 105), warnings may include `docling_partial_success`  
4. Ask questions below; expand **C. Debug trace** each time  

Paste all results under `## Franz-Kafka manual test` in `TEST_RESULTS.md` → tell architect **`review Franz-Kafka`**.

---

## Question set (ask in order)

Record for each: **Answer mode** | **Strategy** | **Top snippet useful?** | **Debug:** `retrieval_mode` `extraction_mode` `entity_ruler_count`

### A — Section / synopsis (Docling + structure + tree)

| # | Question | Expect |
|---|----------|--------|
| A1 | `what is the synopsis of the metamorphosis?` | SECTION_LEVEL → **SYNOPSIS OF THE METAMORPHOSIS**; EVIDENCE or structured; body text about plot |
| A2 | `what happens in chapter I?` | SECTION_LEVEL → **C H A P T E R I**; evidence from lines 31–47 |
| A3 | `who wrote this document?` | BM25_CHUNK; mentions **Franz Kafka** (not only title) |

### B — BM25 / hybrid retrieval

| # | Question | Expect |
|---|----------|--------|
| B1 | `where is metamorphosis mentioned?` | BM25 or SECTION; snippets with Metamorphosis |
| B2 | `what languages is this book available in?` | Evidence citing Spanish / Portuguese / French sections |
| B3 | `what is InfoBooks.org?` | BM25; hit **InfoBooks.org** section |

### C — List / enumeration (grammar path)

| # | Question | Expect |
|---|----------|--------|
| C1 | `what are the main sections in this pdf?` | May be EVIDENCE_ONLY (not a tech doc); check if any list composed |
| C2 | `what translations are mentioned in the document?` | Evidence from Spanish/Portuguese/French heading blocks |

### D — Known weak cases (regression)

| # | Question | Expect |
|---|----------|--------|
| D1 | `what is this document about?` | Often weak (title-only top hit) — note if improved vs Round 3 |
| D2 | `what is THE METAMORPHOSIS?` | DEFINITION_LOOKUP; should prefer synopsis or chapter, not title only |

### E — v2 stack trace checks (debug only)

After any section-level question with body text, confirm debug contains:

- `retrieval_mode=hybrid`
- `extraction_mode=both`
- `entity_ruler_count=...` (0 is OK for fiction; no must/shall expected)

### F — Compare with Deterministic PDF (optional second doc)

Re-run 2 questions on **Deterministic Document…pdf** with same env:

- `what are different design patterns mentioned?` → STRUCTURED_EXTRACTIVE  
- `enterprise usecases before generative AI` → BM25 + enterprise use cases snippet  

Proves stack works on **both** doc types before merge.

---

## Pass criteria for you (informal)

| Area | Pass if |
|------|---------|
| Ingest | Process succeeds; chunks ≈ 24 |
| Section QA | A1 or A2 returns **body** evidence, not title only |
| Hybrid | Debug shows `retrieval_mode=hybrid` |
| Ruler | `extraction_mode=both`; count may be 0 |
| Honest limit | You understand long PDF is **partially** extracted until Docling/memory fixed |

---

## If process fails or 0 chunks

```powershell
$env:TRACEDOC_EXTRACTOR="v1"
# re-process — smaller extract, compare
```

Report in TEST_RESULTS.md.
