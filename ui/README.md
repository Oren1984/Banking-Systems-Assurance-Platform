# ui/

## Phase 2 (implemented — minimal only, still available)

- `streamlit_app.py`'s "Quick Scan only (no database)" mode — the original single-file, minimal
  scan workflow (select source → validate → scan → summary → findings with filters → export),
  kept unchanged in spirit because it never requires `DATABASE_URL`.

## Phase 5 (implemented — full demonstration workflow)

- `streamlit_app.py`'s "Full Assessment (recommended)" mode — select a source (the mock banking
  system by default) → run `assessment.engine.run_assessment()` → view domain scores, findings
  with full traceability, control evaluations, and the append-only audit trail → perform
  human-in-the-loop governance review and score overrides through
  `governance/approval_workflow.py` → check finalization eligibility → export a sanitized
  report (JSON/Markdown/CSV). See `docs/demo_guide.md` for the full walkthrough with expected
  results.
- `services/assessment_service.py` — every piece of business logic the UI calls, deliberately
  with **no Streamlit import** so it is fully unit-testable
  (`tests/unit/test_assessment_service.py`) without a running Streamlit process. This is the
  illustrative target tree's `services/api_client.py`, renamed and reshaped: this platform has
  no FastAPI-backed assessment API for the UI to call through (unlike
  `ai-project-control-tower`'s pattern), so this module talks to the same SQLAlchemy
  repositories every other Phase 2–4 caller uses, directly. See `docs/architecture.md`'s
  "Structural deviations" section.
- `pages/`, `components/` remain intentionally empty. A single-file, tabbed app
  (`st.tabs(...)`) was judged sufficient for this phase's "avoid unnecessary design complexity"
  instruction — Streamlit's native multipage convention (a real `pages/` directory) was
  considered and not used, to avoid the added complexity of coordinating a database session
  and `st.session_state` across independently-rerun page scripts for no functional gain at
  this phase's scope.

## Phase 6 (implemented — optional agent tab)

- `streamlit_app.py`'s **"AI Assistant (Optional)"** tab, sixth in the Full Assessment tab set
  — explain a finding, summarize a domain, ask a question, generate an executive summary.
  Clearly states the current mode (local/external), that sanitized evidence may leave the
  local environment in external mode, and that output never changes findings/scores/governance
  status. Defaults to local mode — no API key, no network call, no cost.
- `services/agent_ui_service.py` — the database glue for the agent tab, deliberately a separate
  module from `services/assessment_service.py` (not functions added to it) so the "agent sits
  outside the trusted deterministic core" boundary is reflected at the module level, not just
  in prose — see `docs/architecture.md`'s module-boundary diagram and `agents/README.md`.

## Note on a previous, incorrect claim in this file

An earlier version of this document stated "Phase 6 replaces it rather than extends it,"
implying the UI work belonged to Phase 6. That was wrong in its original context —
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §13 always scoped the *core* assessment UI to
**Phase 5** ("UI, Mock System, and Demonstration Workflow"). Phase 6's original "Optional
External Providers" framing was later revised at execution time to include a genuinely optional
agent UI addition (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §13's Phase 6 scope-revision
note) — which is exactly what the section above describes: an addition, not a replacement.
