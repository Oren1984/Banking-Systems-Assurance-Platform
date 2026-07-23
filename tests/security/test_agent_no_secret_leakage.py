from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
import ui.services.agent_ui_service as agent_svc
from assessment.engine import run_assessment
from core.config import Settings
from storage.db.base import Base
from ui.services.assessment_service import get_audit_trail

# Phase 6 — end-to-end secret-leakage proof for the optional agent
# boundary, mirroring tests/security/test_no_secret_leakage_in_logs.py's
# pattern for the Phase 2 scanner. A full assessment is run against a
# fixture containing a real-looking (synthetic) secret, then every agent
# action is triggered; the raw secret must never appear in application
# logs or in the persisted audit trail — the only two surfaces this
# boundary is allowed to write to.

_RAW_FAKE_SECRET = "hunter2value123demo"


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
        database_url=f"sqlite:///{tmp_path / 'agent_secrets_test.db'}",
    )


def _project_with_a_secret(tmp_path):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text(f'API_KEY = "{_RAW_FAKE_SECRET}"\n')
    return project


def _run(settings: Settings, project):
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    # expire_on_commit=False: run_assessment() commits internally
    # (ScanRepository.save(), ScoringRepository.score_and_generate(), ...);
    # this keeps the returned Finding/Score objects' attributes usable
    # after this helper returns, the same reasoning
    # ui/services/assessment_service.py::_session() documents.
    session = Session(engine, expire_on_commit=False)
    return run_assessment(str(project), settings, session)


def test_agent_actions_never_log_the_raw_secret(tmp_path, caplog):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)

    with caplog.at_level(logging.DEBUG):
        result = _run(settings, project)
        finding = result.findings[0]
        agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
        agent_svc.generate_executive_summary(settings, result.scan_id, "reviewer@example.com")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _RAW_FAKE_SECRET not in log_text


def test_agent_audit_trail_never_contains_the_raw_secret(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = _run(settings, project)
    finding = result.findings[0]

    agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    agent_svc.summarize_domain(settings, result.scan_id, finding.banking_domains[0], "reviewer@example.com")
    agent_svc.answer_question(settings, result.scan_id, "What secrets exist?", "reviewer@example.com")
    agent_svc.generate_executive_summary(settings, result.scan_id, "reviewer@example.com")

    events = get_audit_trail(settings, result.scan_id)
    agent_events = [e for e in events if e.event_type == "agent_action"]
    assert len(agent_events) == 4
    for e in agent_events:
        assert _RAW_FAKE_SECRET not in e.summary
        assert _RAW_FAKE_SECRET not in str(e.payload)


def test_no_agent_action_transmits_more_than_the_sanitized_context_even_with_an_external_provider_configured(tmp_path):
    # A fully "configured" external provider (fake key — its send() still
    # only ever raises NotImplementedError, see providers/README.md) must
    # still never be handed anything containing the raw secret: the
    # sanitization boundary runs before provider selection is even
    # consulted.
    settings = _settings(tmp_path)
    settings = settings.model_copy(
        update={
            "agent_enabled": True,
            "agent_provider": "openai",
            "external_providers_enabled": True,
            "openai_enabled": True,
            "openai_api_key": "sk-fake-test-key",
        }
    )
    project = _project_with_a_secret(tmp_path)
    result = _run(settings, project)
    finding = result.findings[0]

    response = agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    # send() raises NotImplementedError -> graceful local fallback; either
    # way, the raw secret must never appear in what comes back to the UI.
    assert _RAW_FAKE_SECRET not in response.content
    assert response.error is None or _RAW_FAKE_SECRET not in response.error
