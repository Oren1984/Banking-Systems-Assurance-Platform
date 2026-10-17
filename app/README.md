# app/

`main.py` is a small FastAPI app exposing `GET /health` (configuration status). It is covered by `tests/unit/test_app_health.py` but is **not started** by Docker or any documented command — the platform runs as the Streamlit app in `ui/`.
