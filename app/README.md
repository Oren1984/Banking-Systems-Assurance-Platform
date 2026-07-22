# app/

## Phase 1 (implemented)

- `main.py` — FastAPI application object with a single `/health` endpoint reporting
  safety-relevant configuration (local-only mode, vector backend, external-provider kill
  switch, banking domain count). No scan, assessment, or report routes exist yet.

## Phase 2+ (planned)

`app/api/routes/*` — adapted from `ai-project-control-tower/app/api/routes/*` once the
scanner, RAG core, assessment engine, and data models they depend on exist. Not implemented:
do not import route modules from this package yet.
