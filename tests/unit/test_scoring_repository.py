from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from core.config import Settings
from core.domains import BankingDomain
from models.enums import DecisionCategory, HumanReviewStatus, RecommendationStatus
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory
from storage.db.base import Base
from storage.db.models.control import Control
from storage.db.repositories import ScanRepository, ScoringRepository

# Phase 3 — storage/db/repositories.py::ScoringRepository. In-memory SQLite
# construction/shape test, mirroring tests/unit/test_scan_repository.py's
# approach for ScanRepository — proves the ORM wiring between already-
# persisted Finding/DomainMappingRecord rows and the pure scoring/evidence/
# recommendation functions is correct, without needing a live PostgreSQL
# server. See tests/integration/test_postgres_persistence.py-style live-DB
# coverage for the pgvector-specific guarantees this module doesn't need
# (it uses no vector columns).


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _run_and_persist_scan(tmp_path, session: Session):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text(
        'API_KEY = "hunter2value123"\n'
    )
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    repo = ScanRepository(session)
    repo.save(result)
    return result


def test_score_scan_scores_all_sixteen_domains(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        scoring_repo = ScoringRepository(session)
        scores = scoring_repo.score_scan(result.summary.scan_id)
        assert len(scores) == 16


def test_score_scan_flags_untouched_domains_as_insufficient_evidence(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        scoring_repo = ScoringRepository(session)
        scores = scoring_repo.score_scan(result.summary.scan_id)

        by_domain = {s.domain: s for s in scores}
        payments_score = by_domain[BankingDomain.PAYMENTS.value]
        assert payments_score.decision_category != DecisionCategory.INSUFFICIENT_EVIDENCE.value

        # A domain no scanned file was ever mapped to must not silently
        # score as clean.
        untouched = by_domain[BankingDomain.INVESTMENTS_TRADING.value]
        assert untouched.decision_category == DecisionCategory.INSUFFICIENT_EVIDENCE.value
        assert untouched.raw_score is None


def test_score_and_generate_upserts_catalog_once_and_links_matched_control(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        scoring_repo = ScoringRepository(session)
        output = scoring_repo.score_and_generate(result.summary.scan_id)

        assert len(session.query(Control).all()) == len(output["controls"])

        evidence_rows = output["evidence"]
        assert len(evidence_rows) >= 1
        secret_evidence = [e for e in evidence_rows if "hunter2value123" not in e.content]
        assert len(secret_evidence) == len(evidence_rows)  # never leaks the raw secret

        matched = [e for e in evidence_rows if e.control_id is not None]
        assert len(matched) >= 1  # SECRET-001 must match CTRL-SECRET-001


def test_score_and_generate_produces_recommendations_defaulting_to_open(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        scoring_repo = ScoringRepository(session)
        output = scoring_repo.score_and_generate(result.summary.scan_id)

        recommendations = output["recommendations"]
        assert len(recommendations) >= 1
        for rec in recommendations:
            assert rec.status == RecommendationStatus.OPEN.value

        fetched = scoring_repo.get_recommendations(result.summary.scan_id)
        assert len(fetched) == len(recommendations)


def test_findings_default_to_pending_human_review_status(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        repo = ScanRepository(session)
        findings = repo.get_findings(result.summary.scan_id)
        assert len(findings) >= 1
        for f in findings:
            assert f.human_review_status == HumanReviewStatus.PENDING.value


def test_review_recommendation_updates_status_and_reviewer(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        scoring_repo = ScoringRepository(session)
        output = scoring_repo.score_and_generate(result.summary.scan_id)
        recommendation = output["recommendations"][0]

        updated = scoring_repo.review_recommendation(
            recommendation.id, status="accepted", reviewed_by="reviewer@example.com"
        )
        assert updated is not None
        assert updated.status == "accepted"
        assert updated.reviewed_by == "reviewer@example.com"
        assert updated.reviewed_at is not None


def test_review_recommendation_returns_none_for_unknown_id(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        scoring_repo = ScoringRepository(session)
        assert scoring_repo.review_recommendation("does-not-exist", "accepted", "reviewer") is None


def test_get_evidence_for_finding_filters_by_finding_id(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = _run_and_persist_scan(tmp_path, session)
        scan_repo = ScanRepository(session)
        scoring_repo = ScoringRepository(session)
        scoring_repo.score_and_generate(result.summary.scan_id)

        [finding] = scan_repo.get_findings(result.summary.scan_id)[:1]
        evidence = scoring_repo.get_evidence_for_finding(finding.id)
        assert len(evidence) >= 1
        assert all(e.finding_id == finding.id for e in evidence)
