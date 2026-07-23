from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import AssessmentResult, run_assessment
from core.config import Settings, get_settings
from core.exceptions import ConfigurationError
from core.logging import get_logger
from reporting.assessment_report_exporter import to_assessment_json, to_assessment_markdown
from storage.db.base import Base

logger = get_logger(__name__)

# Phase 5 — Mock banking demo seed script
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 5:
# "scripts/seed_mock_banking_demo.py fully implemented (idempotent,
# deterministic, no real secrets, tested)"). Runs one full, real
# assessment.engine.run_assessment() call against mock_banking_system/ and
# writes two sample export files.
#
# WHAT "IDEMPOTENT" MEANS HERE, EXACTLY: safe to run any number of times
# without corrupting state or crashing — never that it produces the same
# scan_id twice. Every call inserts a new, real historical Scan (and its
# Findings/Scores/ControlEvaluations/Recommendations/AuditEvents) — exactly
# like any other assessment run — because scores and audit events must
# never be mutated (BANKING_PLATFORM_INTEGRATION_PLAN.md's own constraint,
# reused here rather than special-cased). The two files under
# `Settings.report_output_dir`/mock_banking_demo/ (see below) are the only
# thing this script overwrites on every run, by design — they are a demo
# convenience, not historical/audit data.
#
# DETERMINISTIC RESULTS: the mock_banking_system/ fixture itself never
# changes between runs, and every scanner/scoring/control-evaluation
# function it feeds is deterministic (see scoring/engine.py,
# assessment/evaluators/control_evaluator.py) — so the *content* of the
# findings/scores/control-evaluations is identical run to run (only
# generated ids and timestamps differ). See
# docs/mock_banking_planted_findings.md for the exact expected numbers,
# and tests/unit/test_mock_banking_fixture.py for the regression test that
# pins them.
#
# WHY SAMPLE EXPORTS ARE WRITTEN OUTSIDE mock_banking_system/, NOT INTO A
# `sample_exports/` DIRECTORY UNDER IT (contrary to that directory's
# original Phase 1 scaffold): a report emitted by this very script — full
# of finding rule ids, recommendation text mentioning "password"/"secret"/
# "audit", and masked evidence snippets — would itself be scanned on the
# *next* run if it lived inside the scanned tree, corrupting the
# "deterministic" guarantee above (verified the hard way in this session —
# see PHASE_5_COMPLETION_REPORT.md). Reports are written under
# `Settings.report_output_dir` (default `data/reports/`) instead, which is
# never a scan target.

def seed(settings: Optional[Settings] = None, session: Optional[Session] = None) -> dict:
    """
    Run one full assessment against mock_banking_system/ and write sample
    exports. If `session` is not provided, a fresh SQLAlchemy engine/session
    is constructed directly from `settings.database_url` (never via
    storage.db.session's process-wide cached engine — this function may be
    called more than once, including with different settings, in the same
    test session, and must not silently reuse a stale cached connection).
    Table creation is idempotent (`Base.metadata.create_all` only creates
    missing tables) so this is safe to call against either a fresh SQLite
    database or an already Alembic-migrated PostgreSQL instance.
    """
    s = settings or get_settings()

    owns_session = session is None
    if session is None:
        if not s.database_url:
            raise ConfigurationError(
                "DATABASE_URL is not configured. The demo seed script persists a real "
                "assessment run and requires a database — set DATABASE_URL, or pass an "
                "explicit `session` (e.g. an in-memory SQLite session for testing)."
            )
        engine = create_engine(s.database_url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        session = Session(engine)

    try:
        result = run_assessment(s.mock_banking_system_path, s, session)
        export_dir = Path(s.report_output_dir) / "mock_banking_demo"
        _write_sample_exports(result, export_dir)

        logger.info(
            "seed_mock_banking_demo_completed",
            scan_id=result.scan_id,
            findings=len(result.findings),
            domains_scored=len(result.scores),
        )

        return {
            "implemented": True,
            "scan_id": result.scan_id,
            "findings_count": len(result.findings),
            "scores_count": len(result.scores),
            "control_evaluations_count": len(result.control_evaluations),
            "recommendations_count": len(result.recommendations),
            "audit_events_count": len(result.audit_events),
            "sample_exports": [
                str(export_dir / "latest_assessment.json"),
                str(export_dir / "latest_assessment.md"),
            ],
        }
    finally:
        if owns_session:
            session.close()


def _write_sample_exports(result: AssessmentResult, export_dir: Path) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "latest_assessment.json").write_text(to_assessment_json(result), encoding="utf-8")
    (export_dir / "latest_assessment.md").write_text(to_assessment_markdown(result), encoding="utf-8")


def main() -> int:
    try:
        result = seed()
    except ConfigurationError as exc:
        print(f"Cannot seed the demo: {exc}")
        return 1

    print(f"Mock banking demo assessment complete — scan_id={result['scan_id']}")
    print(f"  Findings: {result['findings_count']}")
    print(f"  Domain scores: {result['scores_count']}")
    print(f"  Control evaluations: {result['control_evaluations_count']}")
    print(f"  Recommendations: {result['recommendations_count']}")
    print(f"  Audit events: {result['audit_events_count']}")
    print("Sample exports written to:")
    for path in result["sample_exports"]:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
