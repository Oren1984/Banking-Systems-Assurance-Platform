from __future__ import annotations

import ui.services.agent_ui_service as agent_svc
import ui.services.assessment_service as svc
from core.config import Settings

# Phase 6 — ui/services/agent_ui_service.py. No Streamlit import here or
# in the module under test — this is the "UI-facing service logic" layer,
# fully testable without a running Streamlit process.


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
        database_url=f"sqlite:///{tmp_path / 'agent_ui_test.db'}",
    )


def _project_with_a_secret(tmp_path):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('API_KEY = "hunter2value123"\n')
    return project


def test_get_agent_status_defaults_to_local(tmp_path):
    settings = _settings(tmp_path)
    status = agent_svc.get_agent_status(settings)
    assert status["is_local"] is True
    assert status["agent_enabled"] is False


def test_explain_finding_records_an_audit_event(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    response = agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    assert response is not None
    assert response.is_local is True

    events = svc.get_audit_trail(settings, result.scan_id)
    agent_events = [e for e in events if e.event_type == "agent_action"]
    assert len(agent_events) == 1
    assert agent_events[0].actor == "reviewer@example.com"
    assert agent_events[0].payload["action"] == "explain_finding"


def test_explain_finding_returns_none_for_unknown_finding(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    assert agent_svc.explain_finding(settings, result.scan_id, "does-not-exist", "reviewer@example.com") is None


def test_summarize_domain_records_an_audit_event(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    domain = result.findings[0].banking_domains[0]

    response = agent_svc.summarize_domain(settings, result.scan_id, domain, "reviewer@example.com")
    assert response is not None
    events = svc.get_audit_trail(settings, result.scan_id)
    assert any(e.event_type == "agent_action" and e.payload["action"] == "summarize_domain" for e in events)


def test_answer_question_records_an_audit_event(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))

    response = agent_svc.answer_question(settings, result.scan_id, "What are the risks?", "reviewer@example.com")
    assert response.is_local is True
    events = svc.get_audit_trail(settings, result.scan_id)
    assert any(e.event_type == "agent_action" and e.payload["action"] == "answer_question" for e in events)


def test_generate_executive_summary_records_an_audit_event(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))

    response = agent_svc.generate_executive_summary(settings, result.scan_id, "reviewer@example.com")
    assert response.is_local is True
    events = svc.get_audit_trail(settings, result.scan_id)
    assert any(e.event_type == "agent_action" and e.payload["action"] == "executive_summary" for e in events)


def test_agent_actions_never_leak_the_raw_secret_into_audit_payload(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    events = svc.get_audit_trail(settings, result.scan_id)
    for e in events:
        assert "hunter2value123" not in str(e.payload)
        assert "hunter2value123" not in e.summary


def test_agent_audit_payload_contains_no_raw_prompt_or_response_content(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    events = [e for e in svc.get_audit_trail(settings, result.scan_id) if e.event_type == "agent_action"]
    payload = events[0].payload
    # Only metadata keys — never a "content"/"prompt"/"response" field.
    assert set(payload.keys()) == {
        "action", "provider", "is_local", "model", "success", "error", "context_categories", "user_triggered",
    }


def test_agent_actions_do_not_change_deterministic_findings_or_scores(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    before_findings = {f.id: f.severity for f in svc.get_findings(settings, result.scan_id)}
    before_scores = {s.domain: s.decision_category for s in svc.get_scores(settings, result.scan_id)}

    agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    agent_svc.summarize_domain(settings, result.scan_id, finding.banking_domains[0], "reviewer@example.com")
    agent_svc.generate_executive_summary(settings, result.scan_id, "reviewer@example.com")

    after_findings = {f.id: f.severity for f in svc.get_findings(settings, result.scan_id)}
    after_scores = {s.domain: s.decision_category for s in svc.get_scores(settings, result.scan_id)}
    assert before_findings == after_findings
    assert before_scores == after_scores


def test_agent_actions_do_not_change_finalization_status(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    before = svc.check_finalization(settings, result.scan_id)
    agent_svc.explain_finding(settings, result.scan_id, finding.id, "reviewer@example.com")
    after = svc.check_finalization(settings, result.scan_id)
    assert before.can_finalize == after.can_finalize
