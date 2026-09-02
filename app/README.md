# app/

## Phase 1 (implemented)

- `main.py` — FastAPI application object with a single `/health` endpoint reporting
  safety-relevant configuration (local-only mode, vector backend, external-provider kill
  switch, banking domain count). No scan, assessment, or report routes exist yet.

### Not served in the actual deployment

The platform's real run path is Streamlit only — `deployment/docker-entrypoint.sh` execs
`streamlit run ui/streamlit_app.py`, and no documented run command starts this FastAPI app.
`/health` is exercised solely via `tests/unit/test_app_health.py` (FastAPI's `TestClient`, no
running server). It is kept, documented as unused rather than removed, as a still-correct,
tested foundation for a future real HTTP API — not a currently-live endpoint. Do not assume
`GET /health` is reachable on any running deployment of this platform.

## Phase 2+ (planned)

`app/api/routes/*` — adapted from `ai-project-control-tower/app/api/routes/*` once the
scanner, RAG core, assessment engine, and data models they depend on exist. Not implemented:
do not import route modules from this package yet.
