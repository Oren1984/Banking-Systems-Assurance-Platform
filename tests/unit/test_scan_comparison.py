from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from auth.exceptions import SessionExpiredError
from models.enums import DecisionCategory, Role
from storage.db.models.finding import Finding
from storage.db.models.scan import Scan
from storage.db.models.score import Score
from tests.auth_support import MOCK_SYSTEM_PATH, REPO_ROOT, build_auth_env
from ui.services.comparison_service import (
    IncompatibleScansError,
    check_compatible,
    compare_findings,
    compare_scores,
    effective_scores,
)


def _f(rule, path, evidence, line=1, fid=None):
    return SimpleNamespace(
        id=fid or f"{rule}-{path}-{line}",
        rule_id=rule,
        severity="high",
        title=rule,
        source_relative_path=path,
        line_start=line,
        masked_evidence=evidence,
        human_review_status="pending",
    )


def _s(sid, domain, category, weighted, override_of=None, minutes=0):
    return SimpleNamespace(
        id=sid,
        domain=domain,
        decision_category=category,
        weighted_score=weighted,
        override_of=override_of,
        calculated_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes),
    )


# --------------------------------------------------------------------- #
# Pure matching rules
# --------------------------------------------------------------------- #


def test_new_resolved_and_unchanged_are_classified():
    before = [_f("SQL-001", "a.py", "query + x"), _f("LOG-001", "b.py", "log(password)")]
    after = [_f("SQL-001", "a.py", "query + x"), _f("CFG-001", "c.ini", "DEBUG = true")]
    new, resolved, unchanged = compare_findings(before, after)
    assert [f.rule_id for f in new] == ["CFG-001"]
    assert [f.rule_id for f in resolved] == ["LOG-001"]
    assert [f.rule_id for f in unchanged] == ["SQL-001"]


def test_moved_line_is_still_the_same_finding():
    new, resolved, unchanged = compare_findings([_f("SQL-001", "a.py", "q + x", line=10)], [_f("SQL-001", "a.py", "q + x", line=42)])
    assert (len(new), len(resolved), len(unchanged)) == (0, 0, 1)
    assert unchanged[0].line_start == 42  # refs point at the current scan


def test_whitespace_in_evidence_is_normalized():
    _, _, unchanged = compare_findings([_f("SQL-001", "a.py", "q  +\tx")], [_f("SQL-001", "a.py", "q + x")])
    assert len(unchanged) == 1


def test_different_evidence_same_rule_and_file_are_distinct():
    new, resolved, _ = compare_findings([_f("SQL-001", "a.py", "q + x")], [_f("SQL-001", "a.py", "q + y")])
    assert len(new) == 1 and len(resolved) == 1


def test_duplicates_are_matched_by_multiplicity():
    before = [_f("PII-EMAIL", "a.py", "[EMAIL]", line=i) for i in (1, 2, 3)]
    after = [_f("PII-EMAIL", "a.py", "[EMAIL]", line=i) for i in (1, 2)]
    new, resolved, unchanged = compare_findings(before, after)
    assert (len(new), len(resolved), len(unchanged)) == (0, 1, 2)
    assert resolved[0].line_start == 3


def test_effective_score_follows_the_override_chain():
    original = _s("s1", "payments", "high_risk", 20.0)
    override = _s("s2", "payments", "acceptable", 80.0, override_of="s1", minutes=5)
    other = _s("s3", "lending", "acceptable", 90.0)
    eff = effective_scores([original, override, other])
    assert eff["payments"].id == "s2"
    assert eff["lending"].id == "s3"


def test_score_changes_report_categories_and_delta():
    changes = compare_scores(
        [_s("a1", "payments", "high_risk", 20.0), _s("a2", "lending", "acceptable", 90.0)],
        [_s("b1", "payments", "acceptable", 85.5), _s("b2", "identity", "insufficient_evidence", None)],
    )
    by_domain = {c.domain: c for c in changes}
    assert by_domain["payments"].delta == 65.5 and by_domain["payments"].category_changed
    assert by_domain["lending"].current_category is None  # domain no longer scored
    assert by_domain["identity"].baseline_category is None and by_domain["identity"].delta is None


def test_incompatible_scans_are_rejected_explicitly():
    a = SimpleNamespace(id="a", status="completed", source_path="/x", source_type="directory")
    b = SimpleNamespace(id="b", status="completed", source_path="/y", source_type="directory")
    failed = SimpleNamespace(id="c", status="failed", source_path="/x", source_type="directory")
    with pytest.raises(IncompatibleScansError, match="different sources"):
        check_compatible(a, b)
    with pytest.raises(IncompatibleScansError, match="did not complete"):
        check_compatible(a, failed)
    with pytest.raises(IncompatibleScansError, match="two different"):
        check_compatible(a, a)
    with pytest.raises(IncompatibleScansError, match="no longer exists"):
        check_compatible(a, None)


# --------------------------------------------------------------------- #
# Against real stored assessments, through the secured service
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    env = build_auth_env(tmp_path_factory.mktemp("compare"))
    env.settings.allowed_scan_paths.append(str(REPO_ROOT / "reference_banking_system"))
    emp = env.principals[Role.EMPLOYEE]
    env.first = env.assessments.run_new_assessment(emp, str(MOCK_SYSTEM_PATH)).scan_id
    env.second = env.assessments.run_new_assessment(emp, str(MOCK_SYSTEM_PATH)).scan_id
    env.reference = env.assessments.run_new_assessment(emp, str(REPO_ROOT / "reference_banking_system")).scan_id
    return env


def _snapshot(env):
    with env.auth.session() as s:
        return (
            s.query(Scan).count(),
            sorted((f.id, f.human_review_status, f.reviewed_by) for f in s.query(Finding).all()),
            sorted((x.id, x.decision_category, x.weighted_score) for x in s.query(Score).all()),
        )


def test_identical_reruns_compare_as_all_unchanged(env):
    p = env.login("test.employee")
    before = _snapshot(env)
    result = env.assessments.compare_scans(p, env.first, env.second)
    assert (len(result.new_findings), len(result.resolved_findings), len(result.unchanged_findings)) == (0, 0, 42)
    assert all(c.delta in (0, None) and not c.category_changed for c in result.domain_changes)
    assert _snapshot(env) == before  # read-only


def test_order_is_normalized_oldest_first(env):
    p = env.login("test.employee")
    result = env.assessments.compare_scans(p, env.second, env.first)
    assert result.reordered
    assert (result.baseline_scan_id, result.current_scan_id) == (env.first, env.second)


def test_override_in_current_scan_shows_as_score_change(env):
    m = env.login("test.manager")
    with env.auth.session() as s:
        score = s.query(Score).filter(Score.scan_id == env.second, Score.override_of.is_(None)).first()
    env.assessments.override_score(m, score.id, env.second, score.domain, DecisionCategory.MANUAL_REVIEW_REQUIRED, "Escalated")
    result = env.assessments.compare_scans(m, env.first, env.second)
    change = {c.domain: c for c in result.domain_changes}[score.domain]
    assert change.current_category == DecisionCategory.MANUAL_REVIEW_REQUIRED.value
    assert change.category_changed


def test_comparing_different_sources_is_refused(env):
    p = env.login("test.employee")
    with pytest.raises(IncompatibleScansError):
        env.assessments.compare_scans(p, env.first, env.reference)


def test_unknown_scan_is_reported_not_crashed(env):
    p = env.login("test.employee")
    with pytest.raises(IncompatibleScansError):
        env.assessments.compare_scans(p, env.first, "00000000-0000-0000-0000-000000000000")


def test_comparison_requires_an_authenticated_session(env):
    p = env.login("test.employee")
    env.clock.advance(minutes=31)
    with pytest.raises(SessionExpiredError):
        env.assessments.compare_scans(p, env.first, env.second)
