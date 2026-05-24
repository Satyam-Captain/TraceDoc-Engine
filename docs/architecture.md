# TraceDoc Engine — Architecture

## Goal

Answer questions about uploaded documents using deterministic, local processing only.

## Constraints

- No LLM, AI/ML models, embeddings, or external APIs
- Runs on a single laptop

## Pipeline (planned)

1. **Ingestion** — load and normalize source documents
2. **Structure** — extract logical structure (sections, tables, etc.)
3. **Indexing** — build searchable indexes from structured content
4. **Query** — parse and normalize user questions
5. **Retrieval** — fetch candidate spans from the index
6. **Evidence** — rank and assemble answer evidence
7. **Audit** — log decisions and provenance
8. **Storage** — persist uploads, indexes, and metadata

See `architecture.drawio` for a diagram placeholder.

## Status

Skeleton only — components will be implemented step by step.
