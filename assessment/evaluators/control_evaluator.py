from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from controls.catalog import controls_for_domain
from core.domains import BankingDomain
from models.enums import ControlEvaluationStatus

# Phase 4 — Control evaluator (BANKING_PLATFORM_INTEGRATION_PLAN.md §13
# Phase 4: "assessment/evaluators/*", generalized from
# ai-project-control-tower/app/agents/*). Pure function, no database — same
# design as scoring/engine.py and evidence/capture.py: this module never
# imports storage.db.*, so it is fully unit-testable without a session.
#
# WHAT THIS ADDS BEYOND PHASE 3's Evidence/Recommendation ROWS: those only
# exist for controls a finding actually violated. There was previously no
# persisted record that a control which produced *no* findings in an
# evaluated domain was actually checked and found satisfied, as opposed to
# never having been considered. This module produces exactly one
# ControlEvaluationResult per (domain, applicable control) pair, for every
# one of the 16 approved domains — never a subset — mirroring
# scoring/engine.py::score_all_domains()'s own "always all 16" rule.
#
# THE SAME CORE FIX AS scoring/engine.py, AT CONTROL GRANULARITY: a domain
# that was never evaluated must resolve every one of its applicable
# controls to INSUFFICIENT_EVIDENCE, never to a false SATISFIED — the
# distinguishing signal is `evaluated_domains` (from
# scanners/domain_mapper.py output via storage/db/models/domain_mapping.py),
# not "zero findings matched this control".


@dataclass
class FindingForControlEvaluation:
    """The minimal shape this module needs from a persisted Finding row —
    deliberately not the ORM row itself, matching
    scoring/engine.py::FindingForScoring's own design."""

    finding_id: str
    rule_id: str
    domains: List[str] = field(default_factory=list)


@dataclass
class ControlEvaluationResult:
    domain: BankingDomain
    control_id: str | None  # catalog ControlDefinition.control_id; None only for a
    # domain-level INSUFFICIENT_EVIDENCE placeholder row when no control could even be
    # considered (kept distinct from a per-control result — see evaluate_domain())
    status: ControlEvaluationStatus
    finding_ids: List[str] = field(default_factory=list)


def evaluate_all_domains(
    findings: List[FindingForControlEvaluation],
    evaluated_domains: Set[str],
) -> List[ControlEvaluationResult]:
    """Evaluate every one of the 16 approved domains against every control
    that applies to it — never a subset, so a domain with no applicable
    controls evaluated would be just as misleading a silence as one with
    no score at all."""
    results: List[ControlEvaluationResult] = []
    for domain in BankingDomain:
        results.extend(
            evaluate_domain(
                domain,
                [f for f in findings if domain.value in f.domains],
                evaluated=domain.value in evaluated_domains,
            )
        )
    return results


def evaluate_domain(
    domain: BankingDomain,
    findings: List[FindingForControlEvaluation],
    evaluated: bool,
) -> List[ControlEvaluationResult]:
    applicable = controls_for_domain(domain.value)

    if not evaluated:
        # The domain itself was never evaluated — every applicable control
        # is INSUFFICIENT_EVIDENCE, not SATISFIED. If no control even
        # applies (cannot happen with today's catalog, since the four
        # cross-cutting controls apply universally — see
        # controls/catalog.py::applies_to_domain() — but kept explicit in
        # case a future catalog narrows a control's applies_to_domains and
        # leaves a domain with zero applicable controls), still record one
        # domain-level placeholder row (control_id=None) so the domain is
        # never silently absent from the results.
        if not applicable:
            return [
                ControlEvaluationResult(
                    domain=domain, control_id=None, status=ControlEvaluationStatus.INSUFFICIENT_EVIDENCE
                )
            ]
        return [
            ControlEvaluationResult(
                domain=domain, control_id=c.control_id, status=ControlEvaluationStatus.INSUFFICIENT_EVIDENCE
            )
            for c in applicable
        ]

    results: List[ControlEvaluationResult] = []
    for control in applicable:
        matched = [f.finding_id for f in findings if f.rule_id.startswith(control.rule_prefix)]
        status = ControlEvaluationStatus.GAP if matched else ControlEvaluationStatus.SATISFIED
        results.append(
            ControlEvaluationResult(domain=domain, control_id=control.control_id, status=status, finding_ids=matched)
        )
    return results


def domain_coverage_manifest() -> Dict[str, List[str]]:
    """Domain -> sorted list of applicable control_ids, for every one of
    the 16 approved domains. Pure function of `controls/catalog.py`'s
    current catalog — used both by control evaluation and by
    scripts/generate_knowledge_base_manifest.py so the two can never drift
    from each other."""
    return {
        domain.value: sorted(c.control_id for c in controls_for_domain(domain.value)) for domain in BankingDomain
    }


__all__ = [
    "FindingForControlEvaluation",
    "ControlEvaluationResult",
    "evaluate_all_domains",
    "evaluate_domain",
    "domain_coverage_manifest",
]
