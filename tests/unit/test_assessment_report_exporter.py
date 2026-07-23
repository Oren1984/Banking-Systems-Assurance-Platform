from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import run_assessment
from core.config import Settings
from reporting.assessment_report_exporter import to_assessment_json, to_assessment_markdown
from storage.db.base import Base

# Phase 4 — reporting/assessment_report_exporter.py ("report disclaimers").


def _run(tmp_path):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('API_KEY = "hunter2value123"\n')
    settings = Settings(
        _env_file=None, allowed_scan_paths=[str(tmp_path)], scan_temp_dir=str(tmp_path / "scan_tmp")
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return run_assessment(str(project), settings, session)


def test_markdown_report_contains_governance_disclaimers(tmp_path):
    result = _run(tmp_path)
    md = to_assessment_markdown(result)
    assert "not a banking regulatory or compliance certification" in md
    assert "advisory only" in md
    assert "No AI/LLM or RAG component" in md


def test_markdown_report_never_leaks_the_raw_secret(tmp_path):
    result = _run(tmp_path)
    md = to_assessment_markdown(result)
    assert "hunter2value123" not in md


def test_markdown_report_includes_domain_scores_and_review_status(tmp_path):
    result = _run(tmp_path)
    md = to_assessment_markdown(result)
    assert "payments" in md
    assert "pending" in md


def test_json_report_is_valid_json_and_never_leaks_the_raw_secret(tmp_path):
    result = _run(tmp_path)
    js = to_assessment_json(result)
    assert "hunter2value123" not in js
    payload = json.loads(js)
    assert payload["scan_id"] == result.scan_id
    assert len(payload["scores"]) == 16
    assert "governance_disclaimers" in payload
    assert payload["human_review_status_counts"].get("pending", 0) >= 1
