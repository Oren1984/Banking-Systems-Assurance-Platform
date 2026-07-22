from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from core.config import Settings
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory
from storage.db.base import Base
from storage.db.models.domain_mapping import DomainMappingRecord
from storage.db.models.finding import Finding
from storage.db.models.scan import Scan
from storage.db.repositories import ScanRepository

# Construction/shape test using an in-memory SQLite database — proves the
# repository's ORM mapping and INSERT statements are structurally correct
# without needing a live PostgreSQL server. This does NOT prove pgvector-
# specific behavior (there is none here — no vector columns are used by
# these five tables) and does NOT substitute for
# tests/integration/test_postgres_persistence.py, which runs the same kind
# of assertions against a real PostgreSQL/pgvector instance when one is
# available — see that file's own module docstring for whether it actually
# ran in a given test session.


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _run_scan_result(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text('PASSWORD = "hunter2value123"\n')
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(project), settings)
    try:
        return run_scan(handle, settings)
    finally:
        handle.cleanup()


def test_save_persists_scan_file_inventory_and_findings(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    result = _run_scan_result(tmp_path)

    with Session(engine) as session:
        repo = ScanRepository(session)
        repo.save(result)

        scan_row = session.get(Scan, result.summary.scan_id)
        assert scan_row is not None
        assert scan_row.status == result.summary.status.value
        assert scan_row.integrity_verified is True

        findings = repo.get_findings(result.summary.scan_id)
        assert len(findings) == len(result.findings)
        for row in findings:
            assert row.masked_evidence  # never empty
            assert not hasattr(row, "evidence")  # raw evidence column must not exist


def test_masked_evidence_never_contains_the_raw_secret(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    result = _run_scan_result(tmp_path)

    with Session(engine) as session:
        repo = ScanRepository(session)
        repo.save(result)
        findings = repo.get_findings(result.summary.scan_id)
        for row in findings:
            assert "hunter2value123" not in row.masked_evidence


def test_get_scan_returns_none_for_unknown_id(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = ScanRepository(session)
        assert repo.get_scan("does-not-exist") is None


def test_domain_mapping_rows_are_linked_to_a_real_file_inventory_id(tmp_path):
    # Regression test: an earlier version of ScanRepository.save() read
    # FileInventoryRecord.id immediately after session.add(), before any
    # flush — the Python-side UUID default is not populated until flush,
    # so file_inventory_id was silently written as NULL for every row.
    # SQLite doesn't enforce the FK, so this was invisible there; a live
    # PostgreSQL run raised a real ForeignKeyViolation on the *scan_id*
    # FK first (fixed by an explicit flush after the Scan row), which is
    # what led to finding this second, file_inventory_id instance of the
    # same root cause. See PHASE_2_COMPLETION_REPORT.md.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text("x = 1\n")
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    with Session(engine) as session:
        repo = ScanRepository(session)
        repo.save(result)

        mappings = (
            session.query(DomainMappingRecord)
            .filter(DomainMappingRecord.scan_id == result.summary.scan_id)
            .all()
        )
        assert len(mappings) >= 1
        for m in mappings:
            assert m.file_inventory_id is not None


def test_finding_row_has_no_raw_evidence_column():
    # Structural/schema-level guarantee, independent of any scan result:
    # storage/db/models/finding.py must never define an `evidence` column.
    assert not hasattr(Finding, "evidence")
    assert hasattr(Finding, "masked_evidence")
