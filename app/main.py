from __future__ import annotations

from fastapi import Depends, FastAPI

from core.config import Settings, get_settings
from core.domains import BankingDomain

# Phase 1 scope only: a health/status endpoint that reports the platform's
# safety-relevant configuration (local-only mode, vector backend, external
# provider kill switch, domain count). No scan/assessment/report routes
# exist yet — those are adapted from ai-project-control-tower/app/api/routes/*
# starting in Phase 2. See app/README.md.
#
# NOT SERVED IN THE ACTUAL DEPLOYMENT: the platform runs as a Streamlit app
# (deployment/docker-entrypoint.sh execs `streamlit run ui/streamlit_app.py`
# only). This FastAPI app and its /health route are never started by the
# Docker image or any documented run command — they exist only as a tested,
# importable module (tests/unit/test_app_health.py uses FastAPI's
# TestClient directly, not a running server). Documented here rather than
# removed: the endpoint's own tests exercise still-correct, safe behavior,
# and it remains a plausible Phase 2+ foundation if a real HTTP API is ever
# added — see app/README.md's "Phase 2+ (planned)" note.

app = FastAPI(
    title="Banking Systems Assurance Platform",
    version="0.1.0",
    description=(
        "Local-first, read-only assurance/governance platform. "
        "Phase 1 foundation build — see BANKING_PLATFORM_INTEGRATION_PLAN.md."
    ),
)


@app.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "local_only_mode": settings.local_only_mode,
        "external_providers_enabled": settings.external_providers_enabled,
        "vector_backend": settings.vector_backend,
        "banking_domain_count": len(BankingDomain),
    }
