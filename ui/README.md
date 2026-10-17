# ui/

The Streamlit application.

- `app.py` — entrypoint (`python -m streamlit run ui/app.py`; Docker runs it automatically). `streamlit_app.py` is an alias that runs the same app.
- `shell.py` — session check on every run, sign-in gate, and role-filtered navigation.
- `app_context.py` — wiring of the secured services, the per-page guard, and error handling.
- `views/` — one module per page. `components/` — theme, badges, charts, header and sidebar.
- `services/` — Streamlit-free logic (assessments, AI Assistant, scan comparison). Pages never call it directly; they go through `auth/secured_services.py`.

Pages live in `views/`, not `pages/`, so Streamlit's automatic page discovery cannot expose a page outside the sign-in gate. UI tests: `tests/unit/test_streamlit_app_smoke.py`.
