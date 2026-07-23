from __future__ import annotations

from evidence.capture import FindingForEvidence, build_evidence
from models.enums import EvidenceType

# Phase 3 — evidence/capture.py. Pure function, no database (see the
# module's own docstring) — this module must never be handed raw evidence,
# only Finding.masked_evidence, so these tests only ever construct
# FindingForEvidence with already-masked-looking content.


def test_build_evidence_produces_one_row_per_finding():
    findings = [
        FindingForEvidence(
            finding_id="f1",
            masked_evidence="PASSWORD = ***MASKED***",
            source_relative_path="app/config.py",
            line_start=10,
            line_end=10,
        ),
        FindingForEvidence(
            finding_id="f2",
            masked_evidence="token = ***MASKED***",
            source_relative_path="app/auth.py",
            line_start=5,
            line_end=5,
        ),
    ]
    results = build_evidence(findings)
    assert len(results) == 2
    assert {r.finding_id for r in results} == {"f1", "f2"}


def test_single_line_finding_source_reference_has_no_range():
    finding = FindingForEvidence(
        finding_id="f1",
        masked_evidence="PASSWORD = ***MASKED***",
        source_relative_path="app/config.py",
        line_start=10,
        line_end=10,
    )
    [result] = build_evidence([finding])
    assert result.source_reference == "app/config.py:10"


def test_multi_line_finding_source_reference_has_a_range():
    finding = FindingForEvidence(
        finding_id="f1",
        masked_evidence="def foo():\n    ***MASKED***",
        source_relative_path="app/service.py",
        line_start=20,
        line_end=22,
    )
    [result] = build_evidence([finding])
    assert result.source_reference == "app/service.py:20-22"


def test_evidence_type_is_always_scan_result_in_phase_3():
    finding = FindingForEvidence(
        finding_id="f1",
        masked_evidence="x",
        source_relative_path="a.py",
        line_start=1,
        line_end=1,
    )
    [result] = build_evidence([finding])
    assert result.evidence_type == EvidenceType.SCAN_RESULT.value
    assert result.retrieved_via is None


def test_control_id_passes_through_unchanged_including_when_unmatched():
    matched = FindingForEvidence(
        finding_id="f1", masked_evidence="x", source_relative_path="a.py",
        line_start=1, line_end=1, control_id="ctrl-db-id-123",
    )
    unmatched = FindingForEvidence(
        finding_id="f2", masked_evidence="x", source_relative_path="b.py",
        line_start=1, line_end=1,
    )
    [r1] = build_evidence([matched])
    [r2] = build_evidence([unmatched])
    assert r1.control_id == "ctrl-db-id-123"
    assert r2.control_id is None


def test_content_is_passed_through_exactly_never_re_transformed():
    # The module must never re-derive or alter masked_evidence — it is
    # trusted to already be sanitized by the caller.
    finding = FindingForEvidence(
        finding_id="f1",
        masked_evidence="already ***MASKED*** content",
        source_relative_path="a.py",
        line_start=1,
        line_end=1,
    )
    [result] = build_evidence([finding])
    assert result.content == "already ***MASKED*** content"


def test_build_evidence_of_empty_list_returns_empty_list():
    assert build_evidence([]) == []
