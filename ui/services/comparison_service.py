from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from core.config import Settings
from core.exceptions import ValidationError
from models.enums import ScanStatus
from storage.db.models.finding import Finding
from storage.db.models.scan import Scan
from storage.db.models.score import Score
from storage.db.repositories import ScanRepository, ScoringRepository
from ui.services.assessment_service import _session

# Read-only comparison of two stored assessments ("what changed since the
# last run?"). SELECT queries only — no row is written or modified, so
# historical results are never altered. No Streamlit import (same rule as
# the rest of ui/services/).
#
# FINDING IDENTITY (deterministic matching method). Finding ids are random
# UUIDs per scan, so they cannot match across scans. Two findings are "the
# same finding" when they share:
#     (rule_id, source_relative_path, whitespace-normalized masked_evidence)
# - line numbers are deliberately excluded, so a finding that merely moved
#   because unrelated lines were added above it counts as unchanged;
# - masked evidence is included, so two different findings of the same
#   rule in the same file stay distinct;
# - only masked evidence is ever stored (storage/db/models/finding.py), so
#   matching never needs a raw secret value.
# Identical keys are matched by multiplicity in line order: 3 occurrences
# before and 2 after means 2 unchanged + 1 resolved.
#
# COMPATIBILITY. Two scans are comparable only when they assessed the same
# source (same resolved source_path and source_type) and both completed.
# Anything else raises IncompatibleScansError with the reason — comparing
# two unrelated systems would produce a meaningless "diff".
#
# DOMAIN SCORES. The effective score per domain is the latest row not
# superseded by an override (overrides are new rows whose override_of
# points at the row they replace — see GovernanceRepository.override_score),
# so a human override is what the comparison shows.

_COMPLETED = {ScanStatus.COMPLETED.value, ScanStatus.COMPLETED_WITH_WARNINGS.value}

FindingKey = Tuple[str, str, str]


class IncompatibleScansError(ValidationError):
    """The two selected scans cannot be meaningfully compared."""


@dataclass(frozen=True)
class FindingRef:
    finding_id: str
    rule_id: str
    severity: str
    title: str
    source_relative_path: str
    line_start: int
    human_review_status: str


@dataclass(frozen=True)
class DomainScoreChange:
    domain: str
    baseline_category: Optional[str]
    current_category: Optional[str]
    baseline_weighted: Optional[float]
    current_weighted: Optional[float]

    @property
    def delta(self) -> Optional[float]:
        if self.baseline_weighted is None or self.current_weighted is None:
            return None
        return round(self.current_weighted - self.baseline_weighted, 2)

    @property
    def category_changed(self) -> bool:
        return self.baseline_category != self.current_category


@dataclass
class ScanComparison:
    baseline_scan_id: str
    current_scan_id: str
    source_path: str
    reordered: bool
    new_findings: List[FindingRef] = field(default_factory=list)
    resolved_findings: List[FindingRef] = field(default_factory=list)
    unchanged_findings: List[FindingRef] = field(default_factory=list)
    domain_changes: List[DomainScoreChange] = field(default_factory=list)


def finding_key(finding: Finding) -> FindingKey:
    return (finding.rule_id, finding.source_relative_path, " ".join((finding.masked_evidence or "").split()))


def _ref(f: Finding) -> FindingRef:
    return FindingRef(
        finding_id=f.id,
        rule_id=f.rule_id,
        severity=f.severity,
        title=f.title,
        source_relative_path=f.source_relative_path,
        line_start=f.line_start,
        human_review_status=f.human_review_status,
    )


def effective_scores(scores: Iterable[Score]) -> Dict[str, Score]:
    scores = list(scores)
    superseded = {s.override_of for s in scores if s.override_of}
    effective: Dict[str, Score] = {}
    for s in scores:
        if s.id in superseded:
            continue
        current = effective.get(s.domain)
        if current is None or (s.calculated_at and current.calculated_at and s.calculated_at > current.calculated_at):
            effective[s.domain] = s
    return effective


def check_compatible(baseline: Optional[Scan], current: Optional[Scan]) -> None:
    if baseline is None or current is None:
        raise IncompatibleScansError("One of the selected assessments no longer exists.")
    if baseline.id == current.id:
        raise IncompatibleScansError("Select two different assessments to compare.")
    for scan in (baseline, current):
        if scan.status not in _COMPLETED:
            raise IncompatibleScansError(f"Assessment {scan.id} did not complete (status: {scan.status}).")
    if baseline.source_path != current.source_path or baseline.source_type != current.source_type:
        raise IncompatibleScansError(
            "These assessments scanned different sources and cannot be compared "
            f"('{baseline.source_path}' vs '{current.source_path}')."
        )


def compare_findings(
    baseline: Sequence[Finding], current: Sequence[Finding]
) -> Tuple[List[FindingRef], List[FindingRef], List[FindingRef]]:
    """Returns (new, resolved, unchanged). Unchanged refs point at the
    current scan's rows."""
    before: Dict[FindingKey, List[Finding]] = defaultdict(list)
    after: Dict[FindingKey, List[Finding]] = defaultdict(list)
    for f in sorted(baseline, key=lambda f: f.line_start or 0):
        before[finding_key(f)].append(f)
    for f in sorted(current, key=lambda f: f.line_start or 0):
        after[finding_key(f)].append(f)

    new: List[FindingRef] = []
    resolved: List[FindingRef] = []
    unchanged: List[FindingRef] = []
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key, []), after.get(key, [])
        matched = min(len(b), len(a))
        unchanged.extend(_ref(f) for f in a[:matched])
        new.extend(_ref(f) for f in a[matched:])
        resolved.extend(_ref(f) for f in b[matched:])
    return new, resolved, unchanged


def compare_scores(baseline: Iterable[Score], current: Iterable[Score]) -> List[DomainScoreChange]:
    b, a = effective_scores(baseline), effective_scores(current)
    return [
        DomainScoreChange(
            domain=domain,
            baseline_category=b[domain].decision_category if domain in b else None,
            current_category=a[domain].decision_category if domain in a else None,
            baseline_weighted=b[domain].weighted_score if domain in b else None,
            current_weighted=a[domain].weighted_score if domain in a else None,
        )
        for domain in sorted(set(b) | set(a))
    ]


def compare_loaded(session: Session, baseline_scan_id: str, current_scan_id: str) -> ScanComparison:
    scan_repo = ScanRepository(session)
    baseline, current = scan_repo.get_scan(baseline_scan_id), scan_repo.get_scan(current_scan_id)
    check_compatible(baseline, current)

    reordered = False
    if baseline.created_at and current.created_at and baseline.created_at > current.created_at:
        baseline, current = current, baseline
        reordered = True

    scoring = ScoringRepository(session)
    new, resolved, unchanged = compare_findings(scan_repo.get_findings(baseline.id), scan_repo.get_findings(current.id))
    return ScanComparison(
        baseline_scan_id=baseline.id,
        current_scan_id=current.id,
        source_path=current.source_path,
        reordered=reordered,
        new_findings=new,
        resolved_findings=resolved,
        unchanged_findings=unchanged,
        domain_changes=compare_scores(scoring.get_scores(baseline.id), scoring.get_scores(current.id)),
    )


def compare_scans(settings: Settings, baseline_scan_id: str, current_scan_id: str) -> ScanComparison:
    session = _session(settings)
    try:
        return compare_loaded(session, baseline_scan_id, current_scan_id)
    finally:
        session.close()


__all__ = [
    "DomainScoreChange",
    "FindingRef",
    "IncompatibleScansError",
    "ScanComparison",
    "check_compatible",
    "compare_findings",
    "compare_scans",
    "compare_scores",
    "effective_scores",
    "finding_key",
]
