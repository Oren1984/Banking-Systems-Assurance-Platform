# Banking Systems Assurance Platform

A local-first, read-only assurance and governance platform for banking, credit, investments,
payments, and other regulated financial systems: it scans systems read-only, compares
implementations against requirements/policies/controls/architecture standards, identifies
gaps and risks, scores findings by domain and severity, links findings to evidence, and
recommends remediation. **It never auto-modifies an inspected target.**

This platform never claims legal or regulatory compliance from automated checks alone.

## Status: Phase 2 of 6 — Banking Source Ingestion and Read-Only Scanning Engine

See `BANKING_PLATFORM_INTEGRATION_PLAN.md` for the full audit, target architecture, and
phased migration plan, and `PHASE_1_COMPLETION_REPORT.md` / `PHASE_2_COMPLETION_REPORT.md` for
exactly what each phase delivered, what was tested, and what remains open. Do not treat any
capability described in the plan as implemented unless it is also listed as implemented in a
completion report. Phase 2 added a working local scan: point it at a directory or ZIP archive
and it discovers files, classifies them, maps them to the 16 banking domains, runs 8
deterministic scanners, persists results to PostgreSQL, and exports a report — see
`docs/phase2_scanning_guide.md`.

## Repository layout

This unified platform is built directly at the root of this repository. Three legacy
repositories are retained, untouched, as read-only reference material during the migration:

- `RAG-Engineering-Lab/` — source of the local RAG contracts/isolation pattern
- `ai-project-control-tower/` — source of the scanning/orchestration/persistence pattern
- `AI-Project-Scope-Guard/` — source of the scoring/explainability mechanism (not its
  idea-decision workflow)

See `docs/architecture.md` for what exists today and why the layout is structured this way.

## Local-first by default

```env
LOCAL_ONLY_MODE=true
EXTERNAL_PROVIDERS_ENABLED=false
VECTOR_BACKEND=pgvector
```

No external AI provider (OpenAI, Gemini, Claude) is ever called unless explicitly enabled —
see `docs/security_boundaries.md`. `VECTOR_BACKEND` may also be set to `chroma` for a fully
local, server-free vector store — see `docs/vector_backend_decision.md`.

## Getting started (development)

```bash
pip install -r requirements.txt
cp .env.example .env   # then edit .env with real local values — never commit it
pytest
```

`pytest` runs entirely offline against local, ephemeral state (temp directories, an
in-process FastAPI test client, a local Chroma instance) — no live PostgreSQL server or
external API key is required for the vast majority of the suite. A small number of tests
(`tests/integration/test_postgres_persistence.py`) require a live PostgreSQL/pgvector
instance and are automatically skipped, not failed, when `DATABASE_URL` is unset.

Run a local scan through the minimal UI:

```bash
streamlit run ui/streamlit_app.py
```

See `docs/phase2_scanning_guide.md` for the full walkthrough, supported file types, safety
limits, and scanner coverage.

## Documentation

- `docs/architecture.md` — what is implemented, and structural deviations from the plan
- `docs/phase2_scanning_guide.md` — supported file types, safety limits, scanner coverage, how to scan, how to test
- `docs/security_boundaries.md` — what is enforced, what is a known gap
- `docs/vector_backend_decision.md` — pgvector (primary) vs. Chroma (secondary) decision
- `docs/mock_banking_system.md` — status of the synthetic demonstration environment
