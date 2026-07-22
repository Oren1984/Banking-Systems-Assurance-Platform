# ui/

## Phase 2 (implemented — minimal only)

- `streamlit_app.py` — a single-file, minimal scan workflow (select source → validate → scan →
  summary → findings with filters → export). Deliberately not the final production UI — see
  `docs/phase2_scanning_guide.md` for how to run it (`streamlit run ui/streamlit_app.py`).

## Phase 6 (planned — final production UI)

The page/component/service-separated structure originally planned for this directory
(`ai-project-control-tower/ui/`'s pattern) — `pages/`, `components/`, `services/` remain
scaffolded empty. `streamlit_app.py` above is intentionally not built against that structure;
Phase 6 replaces it rather than extends it.
