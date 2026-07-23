# scoring/

## Phase 3 (implemented — see `PHASE_3_COMPLETION_REPORT.md`)

- `engine.py` — `score_domain()`/`score_all_domains()`. Severity+confidence-weighted
  deduction from 100, merging the weighting/threshold/explainability mechanism from
  `AI-Project-Scope-Guard/src/scope_guard/evaluator.py` (pattern only, not its
  build/don't-build decision semantics — those were explicitly excluded, see
  `BANKING_PLATFORM_INTEGRATION_PLAN.md` §3) with per-dimension aggregation adapted from
  `ai-project-control-tower/app/audit/scoring.py`. Delivers the platform's core correctness
  fix: a domain with zero findings because it was never evaluated resolves to
  `DecisionCategory.INSUFFICIENT_EVIDENCE`, never a false "clean" score — verified by
  `tests/unit/test_scoring_engine.py`, including the exact boundary case (zero findings +
  evaluated vs. zero findings + never evaluated).
- `recommendations.py` — `generate_recommendations()`. Deterministic-template recommendation
  text per finding; reproducible byte-for-byte for the same input.

Pure functions, no database — `storage/db/repositories.py::ScoringRepository` is the only
caller that reads persisted rows and applies these functions' output.

## Phase 4 (implemented — see `PHASE_4_COMPLETION_REPORT.md`)

`assessment/evaluators/control_evaluator.py` (not in this package — see `assessment/README.md`)
applies the same insufficient-evidence-is-not-a-false-pass fix one level more granular, at the
individual-control level rather than the domain-score level.
