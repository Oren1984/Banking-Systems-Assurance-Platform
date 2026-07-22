from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_safe_defaults(monkeypatch):
    for key in (
        "DATABASE_URL",
        "EXTERNAL_PROVIDERS_ENABLED",
        "LOCAL_ONLY_MODE",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "CLAUDE_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["local_only_mode"] is True
    assert body["external_providers_enabled"] is False
    assert body["vector_backend"] == "pgvector"
    assert body["banking_domain_count"] == 16
