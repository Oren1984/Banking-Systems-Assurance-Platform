from __future__ import annotations

import pytest

import ui.services.assessment_service as svc
from core.config import Settings
from core.exceptions import GovernanceError
from models.enums import DecisionCategory, HumanReviewStatus

# Phase 5 — ui/services/assessment_service.py. Deliberately no Streamlit
# import anywhere in this module or the service module — this is what
# "UI-facing service logic" testing means: the plain-Python layer the
# Streamlit rendering code calls, fully testable without a running
# Streamlit process. See tests/unit/test_streamlit_app_smoke.py for the
# separate rendering-layer smoke test.


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
        database_url=f"sqlite:///{tmp_path / 'svc_test.db'}",
    )


def _project_with_a_secret(tmp_path):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('API_KEY = "hunter2value123"\n')
    return project


def _project_with_a_critical_finding(tmp_path):
    # PERM-001 (wildcard IAM Action) is CRITICAL severity at MEDIUM
    # confidence (scanners/rules/permission_scanner.py) — not LOW like
    # LOG-001/AUDIT-*, so it is not swept into scoring/engine.py's
    # all-low-confidence MANUAL_REVIEW_REQUIRED branch and deterministically
    # forces its domain to CRITICAL_RISK regardless of numeric score.
    project = tmp_path / "critical_project"
    (project / "app" / "security").mkdir(parents=True)
    (project / "app" / "security" / "policy.py").write_text('IAM = {"Action": "*", "Resource": "*"}\n')
    return project


def test_run_new_assessment_and_list_recent_scans(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)

    result = svc.run_new_assessment(settings, str(project))
    assert len(result.scores) == 16
    assert len(result.findings) >= 1

    scans = svc.list_recent_scans(settings)
    assert len(scans) == 1
    assert scans[0].scan_id == result.scan_id


def test_get_assessment_reloads_a_persisted_scan(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    fresh = svc.run_new_assessment(settings, str(project))

    loaded = svc.get_assessment(settings, fresh.scan_id)
    assert loaded is not None
    assert loaded.scan_result is None
    assert len(loaded.scores) == len(fresh.scores)
    assert len(loaded.findings) == len(fresh.findings)


def test_get_assessment_returns_none_for_unknown_scan(tmp_path):
    settings = _settings(tmp_path)
    assert svc.get_assessment(settings, "does-not-exist") is None


def test_trace_finding_returns_the_full_chain(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    trace = svc.trace_finding(settings, finding.id)
    assert trace is not None
    assert "CTRL-SECRET-001" in trace.control_ids


def test_review_finding_updates_status_and_records_audit_event(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    updated = svc.review_finding(settings, finding.id, HumanReviewStatus.APPROVED, "reviewer@example.com")
    assert updated is not None
    assert updated.human_review_status == HumanReviewStatus.APPROVED.value

    events = svc.get_audit_trail(settings, result.scan_id)
    assert any(e.event_type == "finding_reviewed" for e in events)


def test_review_finding_invalid_transition_raises_governance_error(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    finding = result.findings[0]

    with pytest.raises(GovernanceError):
        svc.review_finding(settings, finding.id, HumanReviewStatus.PENDING, "reviewer@example.com")


def test_override_score_creates_new_row_and_history_grows(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))
    scores = svc.get_scores(settings, result.scan_id)
    score = scores[0]

    before_history = svc.get_score_history(settings, result.scan_id, score.domain)
    assert len(before_history) == 1

    new_score = svc.override_score(
        settings,
        score.id,
        result.scan_id,
        score.domain,
        DecisionCategory.ACCEPTABLE,
        "reviewer@example.com",
        "Compensating control verified out-of-band.",
    )
    assert new_score.override_of == score.id

    after_history = svc.get_score_history(settings, result.scan_id, score.domain)
    assert len(after_history) == 2


def test_check_finalization_reflects_pending_review_state(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_critical_finding(tmp_path)
    result = svc.run_new_assessment(settings, str(project))

    scores = svc.get_scores(settings, result.scan_id)
    blocking = [s for s in scores if s.decision_category in ("high_risk", "critical_risk")]
    assert blocking, "expected the planted CRITICAL finding to force at least one blocking domain"

    check = svc.check_finalization(settings, result.scan_id)
    assert check.can_finalize is False

    domain = blocking[0].domain
    domain_findings = [f for f in result.findings if domain in (f.banking_domains or [])]
    for f in domain_findings:
        svc.review_finding(settings, f.id, HumanReviewStatus.APPROVED, "reviewer@example.com")

    check_after = svc.check_finalization(settings, result.scan_id)
    blocked_domains_after = {b.domain for b in check_after.blockers}
    assert domain not in blocked_domains_after


def test_export_assessment_returns_all_formats_with_no_raw_secret(tmp_path):
    settings = _settings(tmp_path)
    project = _project_with_a_secret(tmp_path)
    result = svc.run_new_assessment(settings, str(project))

    exports = svc.export_assessment(settings, result.scan_id)
    assert exports is not None
    assert set(exports.keys()) == {"json", "markdown", "findings_csv", "scores_csv"}
    for content in exports.values():
        assert "hunter2value123" not in content


def test_export_assessment_returns_none_for_unknown_scan(tmp_path):
    settings = _settings(tmp_path)
    assert svc.export_assessment(settings, "does-not-exist") is None
