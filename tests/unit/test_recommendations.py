from __future__ import annotations

from models.enums import RecommendationSource, RecommendationStatus, Severity
from scoring.recommendations import FindingForRecommendation, generate_recommendations

# Phase 3 — scoring/recommendations.py. Pure, deterministic-template
# function (see the module's own docstring: "the same finding always
# produces the same recommendation text, byte-for-byte").


def _finding(**overrides) -> FindingForRecommendation:
    defaults = dict(
        finding_id="f1",
        rule_id="SECRET-001",
        title="Hardcoded secret detected",
        severity=Severity.HIGH,
        recommended_action="Remove the credential and rotate it.",
        source_relative_path="app/config.py",
        line_start=12,
    )
    defaults.update(overrides)
    return FindingForRecommendation(**defaults)


def test_generate_recommendations_produces_one_row_per_finding():
    results = generate_recommendations([_finding(finding_id="f1"), _finding(finding_id="f2")])
    assert len(results) == 2
    assert {r.finding_id for r in results} == {"f1", "f2"}


def test_recommendation_text_includes_rule_id_title_location_and_action():
    [result] = generate_recommendations([_finding()])
    assert "SECRET-001" in result.text
    assert "Hardcoded secret detected" in result.text
    assert "app/config.py:12" in result.text
    assert "Remove the credential and rotate it." in result.text


def test_recommendation_text_includes_domain_note_when_domains_present():
    [result] = generate_recommendations([_finding(domains=["payments", "fraud_controls"])])
    assert "banking domains: payments, fraud_controls" in result.text


def test_recommendation_text_omits_domain_note_when_no_domains():
    [result] = generate_recommendations([_finding(domains=[])])
    assert "banking domains" not in result.text


def test_recommendation_priority_mirrors_finding_severity():
    [result] = generate_recommendations([_finding(severity=Severity.CRITICAL)])
    assert result.priority == Severity.CRITICAL.value


def test_recommendation_defaults_to_open_status_and_deterministic_template_source():
    [result] = generate_recommendations([_finding()])
    assert result.status == RecommendationStatus.OPEN.value
    assert result.source == RecommendationSource.DETERMINISTIC_TEMPLATE.value


def test_recommendation_control_id_passes_through_including_when_unmatched():
    [matched] = generate_recommendations([_finding(control_id="ctrl-db-id-123")])
    [unmatched] = generate_recommendations([_finding(control_id=None)])
    assert matched.control_id == "ctrl-db-id-123"
    assert unmatched.control_id is None


def test_recommendation_text_is_reproducible_for_the_same_input():
    finding = _finding()
    [first] = generate_recommendations([finding])
    [second] = generate_recommendations([finding])
    assert first.text == second.text


def test_generate_recommendations_of_empty_list_returns_empty_list():
    assert generate_recommendations([]) == []
