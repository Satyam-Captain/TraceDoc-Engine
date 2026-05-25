# Round 1b — Architect review (2026-05-25)

**Document:** Deterministic Document Question Answering Without AI or LLMs.pdf  
**S1.5:** Accepted (286 tests, title trap + BM25 fallback)

## Round 1b results

| # | Question | Strategy | Mode | Satisfied? |
|---|----------|----------|------|------------|
| 1b-1 | different design patterns mentioned | SECTION_LEVEL | **STRUCTURED_EXTRACTIVE** | **YES** — 6 patterns, correct section |
| 1b-2 | enterprise usecases before generative AI | **BM25_CHUNK** | EVIDENCE_ONLY | **YES** — real content incl. "Enterprise use cases before generative AI" |
| 1b-3 | explain use cases before generative AI | SECTION_LEVEL | EVIDENCE_ONLY | **PARTIAL** — body text OK, section off-topic ("How to make it feel intelligent…") |
| 1b-4 | building blocks of ingestions | SECTION_LEVEL | EVIDENCE_ONLY | **YES** — Open-source building blocks, Tika/ManifoldCF/PDFBox |

Compare to Round 1 Q1/Q3: title-only snippet → **fixed** for enterprise usecases (BM25 path).

## Verdict

**Round 1b SATISFIED** for sprint gate.  
**S1.5 complete.**  
**S2 (Whoosh) UNBLOCKED.**

Optional follow-up (not blocking S2): improve section ranking when multiple sections tie at 2.00 (enterprise/explain → prefer section whose body contains query terms).

## Recommended extra test (you)

`what are different architectures mentioned in the pdf?` → expect STRUCTURED_EXTRACTIVE + Enterprise search stack, etc.

## Next: BUILD agent S2

See `coordination/AGENT_ROUTER.md` — BUILD slice S2 (Whoosh).
