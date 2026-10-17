from __future__ import annotations

import pytest

from auth.exceptions import AuthorizationError
from models.enums import AuthEventType, AuditEventType, DecisionCategory, HumanReviewStatus, Role
from storage.db.models.audit_event import AuditEvent
from storage.db.models.finding import Finding
from storage.db.models.score import Score
from tests.auth_support import MOCK_SYSTEM_PATH, build_auth_env

# Direct calls to the secured service layer — no UI involved — prove that
# role restrictions cannot be bypassed by skipping the interface.


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    env = build_auth_env(tmp_path_factory.mktemp("secured"))
    # EMPLOYEE is allowed to run a Full Assessment; reuse that scan below.
    env.scan_id = env.assessments.run_new_assessment(env.principals[Role.EMPLOYEE], str(MOCK_SYSTEM_PATH)).scan_id
    return env


def _fresh(env, role):
    # Sessions idle-expire on the fake clock; sign in again per test.
    return env.login(f"test.{role.value}")


def _events(env, event_type):
    with env.auth.session() as s:
        return list(
            s.query(AuditEvent).filter(AuditEvent.event_type == event_type.value).order_by(AuditEvent.created_at).all()
        )


def _a_pending_finding(env):
    with env.auth.session() as s:
        return (
            s.query(Finding)
            .filter(Finding.scan_id == env.scan_id, Finding.human_review_status == HumanReviewStatus.PENDING.value)
            .first()
        )


def _a_score(env):
    with env.auth.session() as s:
        return s.query(Score).filter(Score.scan_id == env.scan_id, Score.override_of.is_(None)).first()


def test_employee_full_assessment_is_attributed_to_the_employee(env):
    requested = _events(env, AuthEventType.ASSESSMENT_REQUESTED)
    assert [(e.actor, e.scan_id) for e in requested] == [("test.employee", env.scan_id)]
    assert len(env.assessments.get_assessment(_fresh(env, Role.EMPLOYEE), env.scan_id).findings) == 42


@pytest.mark.parametrize("role", list(Role))
def test_every_role_can_view_and_run(env, role):
    p = _fresh(env, role)
    assert env.assessments.list_recent_scans(p)
    assert env.assessments.get_assessment(p, env.scan_id) is not None
    assert env.assessments.check_finalization(p, env.scan_id) is not None
    result = env.assessments.run_quick_scan(p, str(MOCK_SYSTEM_PATH))
    assert result.summary.total_findings == 42
    assert _events(env, AuthEventType.QUICK_SCAN_REQUESTED)[-1].actor == p.username


@pytest.mark.parametrize("role", [Role.EMPLOYEE, Role.ADMIN])
def test_non_managers_cannot_review_findings(env, role):
    p = _fresh(env, role)
    finding = _a_pending_finding(env)
    with pytest.raises(AuthorizationError):
        env.assessments.review_finding(p, finding.id, HumanReviewStatus.APPROVED, "looks fine")
    with env.auth.session() as s:
        assert s.get(Finding, finding.id).human_review_status == HumanReviewStatus.PENDING.value
    denied = _events(env, AuthEventType.ACCESS_DENIED)[-1]
    assert denied.actor == p.username
    assert denied.payload["permission"] == "review_findings"


@pytest.mark.parametrize("role", [Role.EMPLOYEE, Role.ADMIN])
def test_non_managers_cannot_override_scores(env, role):
    p = _fresh(env, role)
    score = _a_score(env)
    with env.auth.session() as s:
        before = s.query(Score).filter(Score.scan_id == env.scan_id).count()
    with pytest.raises(AuthorizationError):
        env.assessments.override_score(p, score.id, env.scan_id, score.domain, DecisionCategory.ACCEPTABLE, "because")
    with env.auth.session() as s:
        assert s.query(Score).filter(Score.scan_id == env.scan_id).count() == before
    assert _events(env, AuthEventType.ACCESS_DENIED)[-1].payload["permission"] == "override_scores"


def test_manager_review_uses_authenticated_identity(env):
    p = _fresh(env, Role.MANAGER)
    finding = _a_pending_finding(env)
    env.assessments.review_finding(p, finding.id, HumanReviewStatus.APPROVED, "Confirmed")
    with env.auth.session() as s:
        row = s.get(Finding, finding.id)
        assert row.human_review_status == HumanReviewStatus.APPROVED.value
        assert row.reviewed_by == "test.manager"
    reviewed = _events(env, AuditEventType.FINDING_REVIEWED)[-1]
    assert reviewed.actor == "test.manager"


def test_manager_override_uses_authenticated_identity(env):
    p = _fresh(env, Role.MANAGER)
    score = _a_score(env)
    new = env.assessments.override_score(
        p, score.id, env.scan_id, score.domain, DecisionCategory.MANUAL_REVIEW_REQUIRED, "Needs a human look"
    )
    assert new.override_of == score.id
    assert _events(env, AuditEventType.SCORE_OVERRIDDEN)[-1].actor == "test.manager"


def test_review_signature_has_no_reviewer_parameter(env):
    import inspect

    for name in ("review_finding", "override_score"):
        params = inspect.signature(getattr(env.assessments, name)).parameters
        assert "reviewed_by" not in params and "reviewer" not in params


def test_employee_cannot_export_or_view_audit_log(env):
    p = _fresh(env, Role.EMPLOYEE)
    for call in (
        lambda: env.assessments.export_assessment(p, env.scan_id),
        lambda: env.assessments.record_export(p, "json", scan_id=env.scan_id),
        lambda: env.assessments.get_audit_trail(p, env.scan_id),
        lambda: env.assessments.get_platform_audit_log(p),
    ):
        with pytest.raises(AuthorizationError):
            call()


@pytest.mark.parametrize("role", [Role.MANAGER, Role.ADMIN])
def test_manager_and_admin_can_export_and_view_audit_log(env, role):
    p = _fresh(env, role)
    exports = env.assessments.export_assessment(p, env.scan_id)
    assert set(exports) == {"json", "markdown", "findings_csv", "scores_csv"}
    env.assessments.record_export(p, "json", scan_id=env.scan_id)
    assert _events(env, AuthEventType.REPORT_EXPORTED)[-1].actor == p.username
    assert env.assessments.get_audit_trail(p, env.scan_id)
    assert env.assessments.get_platform_audit_log(p)


def test_recent_activity_is_scoped_for_employees(env):
    p = _fresh(env, Role.EMPLOYEE)
    assert {e.actor for e in env.assessments.get_recent_activity(p, limit=50)} == {"test.employee"}
    m = _fresh(env, Role.MANAGER)
    assert len({e.actor for e in env.assessments.get_recent_activity(m, limit=200)}) > 1


@pytest.mark.parametrize("role", list(Role))
def test_ai_assistant_is_advisory_and_attributed(env, role):
    p = _fresh(env, role)
    finding = _a_pending_finding(env)
    with env.auth.session() as s:
        before = (s.get(Finding, finding.id).human_review_status, s.query(Score).count())
    response = env.agent.explain_finding(p, env.scan_id, finding.id)
    assert response is not None and response.is_local
    env.agent.generate_executive_summary(p, env.scan_id)
    with env.auth.session() as s:
        assert (s.get(Finding, finding.id).human_review_status, s.query(Score).count()) == before
    assert _events(env, AuditEventType.AGENT_ACTION)[-1].actor == p.username


def test_agent_service_exposes_no_decision_methods(env):
    public = {n for n in dir(env.agent) if not n.startswith("_")}
    assert public == {"get_agent_status", "explain_finding", "summarize_domain", "answer_question", "generate_executive_summary"}
