# models/

## Phase 1 (implemented)

- `enums.py` — `Severity`, `ConfidenceLevel`, `EvidenceCompleteness`, `HumanReviewStatus`,
  `DecisionCategory`, `ControlType` (Phase 1) plus `ScanStatus`, `SkipReason`,
  `FindingCategory`, `FindingType`, `RemediationMode`, `MappingSource` (Phase 2 additions to
  this same file — one enum module, not two).

## Phase 2 (implemented — status corrected from the original Phase 3 placement below)

`Finding` and its supporting persistence tables were required by Phase 2's own brief and were
built then, not deferred to Phase 3 as originally planned. They live in
`storage/db/models/{scan,file_inventory,domain_mapping,finding,scanner_execution}.py`
(SQLAlchemy ORM, not a separate `models/` module — see that directory's own README for why).
`models/enums.py` above supplies the vocabulary those tables use.

## Phase 3 (planned — Assessment, Evidence, and Scoring)

The remaining data model classes — the control-evaluation side of the schema, not yet built.
Field-level shapes are already specified in `BANKING_PLATFORM_INTEGRATION_PLAN.md` §11 and are
not repeated here to avoid a second source of truth. Planned Phase 3 modules:

| Module | Status |
|---|---|
| `assessment_target.py` | Net-new |
| `control.py` | Net-new |
| `policy.py` | Net-new |
| `evidence.py` | Adapted from `Finding.evidence` (control-tower) |
| `recommendation.py` | Adapted (promoted from `Finding.recommendation` to its own entity) |
| `score.py` | Adapted from `ai-project-control-tower/app/audit/models.py::AuditScores` |
| `report.py` | Adapted from `ai-project-control-tower/app/db/models/report.py` |
| `provider_request.py` | Net-new |
| `audit_event.py` | Net-new |
| `human_review.py` | Net-new |

(`finding.py` removed from this table — implemented in Phase 2, see above, not here.)

None of the modules in this table are implemented yet. Do not import modules from this table —
they do not exist until Phase 3.
