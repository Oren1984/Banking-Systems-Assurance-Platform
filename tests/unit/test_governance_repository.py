from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from core.exceptions import GovernanceError
from governance.approval_workflow import FindingReviewDecision, ScoreOverrideDecision
from models.enums import DecisionCategory, HumanReviewStatus
from storage.db.base import Base
from storage.db.models.finding import Finding
from storage.db.models.scan import Scan
from storage.db.models.score import Score
from storage.db.repositories import GovernanceRepository

# Phase 4 — storage/db/repositories.py::GovernanceRepository. In-memory
# SQLite test, directly seeding Scan/Score/Finding rows rather than
# running a full scan — this isolates governance-repository behavior
# (review, override, finalization policy) from scanner-detection
# specifics, which are already covered by tests/unit/rules/ and
# tests/unit/test_assessment_engine.py.


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _seed_scan_score_and_finding(session: Session, decision_category: str, review_status: str):
    scan = Scan(source_path="/tmp/project", source_type="directory", status="completed")
    session.add(scan)
    session.flush()

    score = Score(
        scan_id=scan.id,
        domain="payments",
        raw_score=10.0,
        weighted_score=10.0,
        confidence_level="high",
        evidence_completeness="complete",
        decision_category=decision_category,
        files_evaluated=3,
        findings_count=1,
    )
    session.add(score)

    finding = Finding(
        scan_id=scan.id,
        scanner_id="secret_scanner",
        scanner_version="1.0",
        rule_id="SECRET-001",
        title="Hardcoded secret",
        finding_type="observed_evidence",
        category="secret_exposure",
        severity="critical",
        confidence="high",
        banking_domains=["payments"],
        source_relative_path="app/config.py",
        line_start=1,
        line_end=1,
        masked_evidence="***MASKED***",
        description="d",
        impact="i",
        recommended_action="r",
        human_review_status=review_status,
    )
    session.add(finding)
    session.flush()
    session.commit()
    return scan, score, finding


def test_review_finding_updates_status_reviewer_and_timestamp():
    with Session(_engine()) as session:
        _, _, finding = _seed_scan_score_and_finding(
            session, DecisionCategory.ACCEPTABLE.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        updated = repo.review_finding(
            FindingReviewDecision(
                finding_id=finding.id,
                new_status=HumanReviewStatus.APPROVED,
                reviewed_by="reviewer@example.com",
            )
        )
        assert updated.human_review_status == HumanReviewStatus.APPROVED.value
        assert updated.reviewed_by == "reviewer@example.com"
        assert updated.reviewed_at is not None


def test_review_finding_returns_none_for_unknown_id():
    with Session(_engine()) as session:
        repo = GovernanceRepository(session)
        result = repo.review_finding(
            FindingReviewDecision(
                finding_id="does-not-exist",
                new_status=HumanReviewStatus.APPROVED,
                reviewed_by="reviewer@example.com",
            )
        )
        assert result is None


def test_review_finding_invalid_transition_raises_and_persists_nothing():
    with Session(_engine()) as session:
        _, _, finding = _seed_scan_score_and_finding(
            session, DecisionCategory.ACCEPTABLE.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        with pytest.raises(GovernanceError):
            repo.review_finding(
                FindingReviewDecision(
                    finding_id=finding.id, new_status=HumanReviewStatus.PENDING, reviewed_by="reviewer@example.com"
                )
            )
        session.expire_all()
        assert session.get(Finding, finding.id).human_review_status == HumanReviewStatus.PENDING.value


def test_review_finding_writes_an_audit_event():
    with Session(_engine()) as session:
        _, _, finding = _seed_scan_score_and_finding(
            session, DecisionCategory.ACCEPTABLE.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        repo.review_finding(
            FindingReviewDecision(
                finding_id=finding.id, new_status=HumanReviewStatus.APPROVED, reviewed_by="reviewer@example.com"
            )
        )
        events = repo._audit.get_for_scan(finding.scan_id)
        assert len(events) == 1
        assert events[0].event_type == "finding_reviewed"
        assert events[0].actor == "reviewer@example.com"


def test_override_score_creates_a_new_row_linked_via_override_of():
    with Session(_engine()) as session:
        _, score, _ = _seed_scan_score_and_finding(
            session, DecisionCategory.HIGH_RISK.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        new_score = repo.override_score(
            ScoreOverrideDecision(
                original_score_id=score.id,
                scan_id=score.scan_id,
                domain="payments",
                new_decision_category=DecisionCategory.ACCEPTABLE,
                reviewed_by="reviewer@example.com",
                reason="Compensating control confirmed out-of-band.",
            )
        )
        assert new_score.override_of == score.id
        assert new_score.decision_category == DecisionCategory.ACCEPTABLE.value
        # The original row is untouched — overriding never mutates history.
        session.expire_all()
        original = session.get(Score, score.id)
        assert original.decision_category == DecisionCategory.HIGH_RISK.value


def test_override_score_returns_none_for_unknown_original_id():
    with Session(_engine()) as session:
        repo = GovernanceRepository(session)
        result = repo.override_score(
            ScoreOverrideDecision(
                original_score_id="does-not-exist",
                scan_id="scan-x",
                domain="payments",
                new_decision_category=DecisionCategory.ACCEPTABLE,
                reviewed_by="reviewer@example.com",
                reason="reason",
            )
        )
        assert result is None


def test_check_finalization_blocked_by_critical_risk_domain_with_pending_finding():
    with Session(_engine()) as session:
        scan, _, _ = _seed_scan_score_and_finding(
            session, DecisionCategory.CRITICAL_RISK.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        result = repo.check_finalization(scan.id)
        assert result.can_finalize is False
        assert result.blockers[0].domain == "payments"


def test_check_finalization_unblocked_after_reviewing_the_finding():
    with Session(_engine()) as session:
        scan, _, finding = _seed_scan_score_and_finding(
            session, DecisionCategory.CRITICAL_RISK.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        assert repo.check_finalization(scan.id).can_finalize is False

        repo.review_finding(
            FindingReviewDecision(
                finding_id=finding.id, new_status=HumanReviewStatus.APPROVED, reviewed_by="reviewer@example.com"
            )
        )
        assert repo.check_finalization(scan.id).can_finalize is True


def test_check_finalization_uses_the_override_not_the_original_decision_category():
    with Session(_engine()) as session:
        scan, score, finding = _seed_scan_score_and_finding(
            session, DecisionCategory.CRITICAL_RISK.value, HumanReviewStatus.PENDING.value
        )
        repo = GovernanceRepository(session)
        assert repo.check_finalization(scan.id).can_finalize is False

        repo.override_score(
            ScoreOverrideDecision(
                original_score_id=score.id,
                scan_id=scan.id,
                domain="payments",
                new_decision_category=DecisionCategory.ACCEPTABLE,
                reviewed_by="reviewer@example.com",
                reason="Compensating control confirmed out-of-band.",
            )
        )
        # The domain's *latest* score is now acceptable, so a still-pending
        # finding in that domain no longer blocks finalization.
        assert repo.check_finalization(scan.id).can_finalize is True
