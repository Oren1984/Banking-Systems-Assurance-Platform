# scoring/

## Phase 1

The vocabulary this engine will use is already defined and tested: `models.enums.Severity`,
`ConfidenceLevel`, `EvidenceCompleteness`, `DecisionCategory`. No scoring logic exists yet.

## Phase 3 (planned)

`engine.py` — merges the weighting/threshold/explainability mechanism from
`AI-Project-Scope-Guard/src/scope_guard/evaluator.py` (pattern only, not its build/don't-build
decision semantics — those are explicitly excluded, see
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §3) with per-dimension aggregation adapted from
`ai-project-control-tower/app/audit/scoring.py`, plus new confidence/evidence-completeness
handling. The core fix this must deliver: a domain with zero findings because it was never
evaluated must resolve to `DecisionCategory.INSUFFICIENT_EVIDENCE`, never to a default
"clean" score — this is the single most important gap identified in the audit (see
`BANKING_PLATFORM_INTEGRATION_PLAN.md` Executive Summary and §9).
