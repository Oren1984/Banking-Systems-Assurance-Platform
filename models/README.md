# models/

## Phase 1 (implemented)

- `enums.py` — `Severity`, `ConfidenceLevel`, `EvidenceCompleteness`, `HumanReviewStatus`,
  `DecisionCategory`, `ControlType` (Phase 1) plus `ScanStatus`, `SkipReason`,
  `FindingCategory`, `FindingType`, `RemediationMode`, `MappingSource` (Phase 2), plus
  `EvidenceType`, `RecommendationStatus`, `RecommendationSource` (Phase 3), plus
  `ControlEvaluationStatus`, `AuditEventType` (Phase 4) — one enum module throughout, never a
  second one.

## Phase 2 (implemented — status corrected from the original Phase 3 placement below)

`Finding` and its supporting persistence tables were required by Phase 2's own brief and were
built then, not deferred to Phase 3 as originally planned. They live in
`storage/db/models/{scan,file_inventory,domain_mapping,finding,scanner_execution}.py`
(SQLAlchemy ORM, not a separate `models/` module — see that directory's own README for why).
`models/enums.py` above supplies the vocabulary those tables use.

## Phase 3 (implemented — Assessment, Evidence, and Scoring)

The control-evaluation side of the schema. As with Phase 2's `Finding`, these were built as
SQLAlchemy ORM classes directly under `storage/db/models/` rather than a separate `models/`
data-model layer, for the same "one persistence pattern, not two" reason — see
`storage/db/README.md`.

| Planned module (`BANKING_PLATFORM_INTEGRATION_PLAN.md` §11) | What was actually built |
|---|---|
| `control.py` | `storage/db/models/control.py::Control` |
| `evidence.py` | `storage/db/models/evidence.py::Evidence` |
| `recommendation.py` | `storage/db/models/recommendation.py::Recommendation` |
| `score.py` | `storage/db/models/score.py::Score` |
| `policy.py`, `assessment_target.py`, `report.py` | Not built — no dedicated `Policy`/`AssessmentTarget`/`Report` table exists; `Score.scan_id` references the real, already-persisted `scans.id` directly (see `score.py`'s own module docstring for why) |

## Phase 4 (implemented — Complete Banking Domain and Governance Layer)

| Planned module (`BANKING_PLATFORM_INTEGRATION_PLAN.md` §13 Phase 4) | What was actually built |
|---|---|
| `audit_event.py` | `storage/db/models/audit_event.py::AuditEvent` |
| (control-evaluation detail — not separately named in the plan) | `storage/db/models/control_evaluation.py::ControlEvaluation` (net-new, closes the gap that Evidence/Recommendation only record controls a finding *violated*, never one it *passed*) |
| `human_review.py` | Not built as a separate table — human review state lives directly on `Finding` (`human_review_status`/`reviewed_by`/`reviewed_at`, Phase 3) and `Score` (`override_of`, Phase 3), applied via `governance/approval_workflow.py` + `storage/db/repositories.py::GovernanceRepository` (Phase 4) |
| `provider_request.py` | Not built — remains Phase 6 scope (no real external-provider `send()` implementation exists yet to log requests for) |
