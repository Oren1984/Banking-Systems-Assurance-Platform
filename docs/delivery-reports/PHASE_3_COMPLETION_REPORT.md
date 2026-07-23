# Phase 3 Completion Report — Assessment, Evidence, and Scoring

**Status:** Phase 3 complete. Phase 4 has **not** started. Waiting for explicit approval
before any Phase 4 work begins.

This report is the authoritative record of what Phase 3 actually delivered. Where this
document and `BANKING_PLATFORM_INTEGRATION_PLAN.md` disagree on what is implemented, trust
this document. Where this document and `PHASE_2_COMPLETION_REPORT.md` disagree on which phase
built something, trust whichever report's own session actually verified it — see §2 for a
note on provenance.

---

## 1. Executive summary

Phase 3 delivers the scoring engine, control catalog, evidence capture, and recommendation
generation the integration plan calls for, plus the first real Alembic migration for the
control-evaluation side of the schema (`controls`, `scores`, `evidence`, `recommendations`,
and three new columns on `findings`). It closes the single largest gap named in the
integration plan's Executive Summary: a domain with zero findings because it was never
evaluated now resolves to `DecisionCategory.INSUFFICIENT_EVIDENCE`, never a false "clean"
100/100 score — verified by dedicated boundary-case tests, not merely asserted.

## 2. Provenance note (why this report exists now, not earlier)

The core Phase 3 modules (`scoring/engine.py`, `scoring/recommendations.py`,
`controls/catalog.py`, `evidence/capture.py`, the four new `storage/db/models/*.py` files,
`storage/db/repositories.py::ScoringRepository`, and
`alembic/versions/0002_phase3_controls_evidence_scoring.py`) were already present and passing
their existing tests (`tests/unit/test_scoring_engine.py`, 12 tests) at the start of this
session — implemented in an earlier session as part of the same commit that carried Phase 1
and Phase 2 forward (`ad2bdcd`, "Banking-Systems-Assurance-Platform stage 1-3"). What this
session added: the test coverage that was still missing for `controls/catalog.py`,
`evidence/capture.py`, `scoring/recommendations.py`, and `ScoringRepository` (none of which
had a dedicated test file, unlike every Phase 2 module), live-PostgreSQL verification of the
Phase 3 migration and `ScoringRepository`, and this completion report — mirroring the
"implement → test every module → verify live where a live server changes behavior → write the
report → stop for approval" pattern `PHASE_1_COMPLETION_REPORT.md` and
`PHASE_2_COMPLETION_REPORT.md` both followed.

## 3. Phase 3 objective

As stated in `BANKING_PLATFORM_INTEGRATION_PLAN.md` §13: stand up persistence, evidence
capture, and the new scoring engine with confidence/evidence-completeness support. Included:
`models/{control,evidence,finding,recommendation,score}.py` (delivered as SQLAlchemy models
directly under `storage/db/models/`, since `Finding` itself was already Phase 2 work — see the
plan's own Phase 2 status correction note — and no separate Pydantic layer was judged
necessary beyond the existing dataclass shapes in `scoring/engine.py` and `evidence/capture.py`),
`storage/db/*` domain tables plus the first real Alembic migration, `controls/*`, `evidence/*`,
`scoring/engine.py`. Not in scope: `assessment/engine.py` and the human-approval/audit-trail
governance layer (both explicitly Phase 4, per §13), and any control-library content authored
by banking/compliance domain experts (§16 open question #4, still open).

## 4. Final implementation status

**Fully implemented and tested (this session added the missing test coverage):**
`scoring/engine.py` (`score_domain`, `score_all_domains` — tested prior to this session),
`scoring/recommendations.py` (`generate_recommendations` — newly tested this session),
`controls/catalog.py` (`CONTROL_CATALOG`, `upsert_catalog`, `control_for_rule_id` — newly
tested this session), `evidence/capture.py` (`build_evidence` — newly tested this session),
`storage/db/repositories.py::ScoringRepository` (`score_scan`, `score_and_generate`,
`get_scores`, `get_recommendations`, `get_evidence_for_finding`, `review_recommendation` —
newly tested this session, both against in-memory SQLite and a live PostgreSQL/pgvector
instance).

**Implemented and live-integration tested (this session):**
`alembic/versions/0002_phase3_controls_evidence_scoring.py` was already applied to the local
Docker Postgres instance (`banking_assurance_db`, started in an earlier session) before this
session began; this session verified the four new tables and the three new `findings` columns
exist on that live database, and ran a full `ingest → scan → persist → score_and_generate`
round-trip against it.

**Scaffolded only / deferred, unchanged — remains Phase 4+ scope:** `assessment/engine.py` and
`assessment/evaluators/*` (still only `assessment/__init__.py` + `README.md`),
`governance/approval_workflow.py`, `governance/audit_trail.py`, `models/audit_event.py`,
`knowledge_base/controls/` content across all 16 domains, `rag/{ingestion,chunking,retrieval,
pipeline}` (unchanged since Phase 1/2), full `mock_banking_system/` content, `ui/{pages,
components,services}/`.

## 5. Files and modules added this session

| Area | Files | Contents |
|---|---|---|
| `tests/unit/` | 4 | `test_control_catalog.py` (6 tests), `test_evidence_capture.py` (7 tests), `test_recommendations.py` (9 tests), `test_scoring_repository.py` (8 tests) |
| `tests/integration/` | 1 | `test_postgres_phase3_scoring.py` (3 tests, live PostgreSQL — skipped when `DATABASE_URL` is unset) |
| `PHASE_3_COMPLETION_REPORT.md` | 1 | This document |

No existing file was modified this session — every change is a new test file plus this
report. The Phase 3 production code itself (§2) predates this session and was not altered.

## 6. Files and modules already present at the start of this session (Phase 3 production code)

| Area | Files | Key modules |
|---|---|---|
| `scoring/` | 2 | `engine.py` (`score_domain`, `score_all_domains`), `recommendations.py` (`generate_recommendations`) |
| `controls/` | 1 | `catalog.py` (`CONTROL_CATALOG`, `upsert_catalog`, `control_for_rule_id`) |
| `evidence/` | 1 | `capture.py` (`build_evidence`) |
| `storage/db/models/` | 4 | `control.py`, `evidence.py`, `score.py`, `recommendation.py` |
| `storage/db/repositories.py` | +1 class | `ScoringRepository`, added alongside the existing `ScanRepository` |
| `alembic/versions/` | 1 | `0002_phase3_controls_evidence_scoring.py` |
| `models/enums.py` | +3 enums | `EvidenceType`, `RecommendationStatus`, `RecommendationSource` (appended to the single shared enum module, not a second file — same rule Phase 1/2 followed) |
| `tests/unit/test_scoring_engine.py` | 1 | 12 tests, including the core insufficient-evidence boundary case |

## 7. Scoring engine

`scoring/engine.py::score_domain()` takes a domain, its findings, whether it was evaluated at
all, and how many files were evaluated, and returns a `ScoreResult` carrying `raw_score`,
`weighted_score`, `confidence_level`, `evidence_completeness`, and `decision_category`. The
distinguishing signal for the core fix is `evaluated` — whether at least one scanned file was
actually mapped to this domain (`scanners/domain_mapper.py` output) — not "zero findings for
this domain": an unevaluated domain always returns `raw_score=None`,
`weighted_score=None`, `evidence_completeness=INSUFFICIENT`,
`decision_category=INSUFFICIENT_EVIDENCE`, regardless of how many findings other domains have.
Severity deductions (`CRITICAL`=40, `HIGH`=25, `MEDIUM`=12, `LOW`=5, `INFO`=1) apply to
`raw_score`; `weighted_score` additionally discounts by a confidence multiplier
(`HIGH`=1.0, `MEDIUM`=0.7, `LOW`=0.4). A domain confidence reflects its weakest contributing
finding. `score_all_domains()` always scores all 16 `BankingDomain` members, never a subset —
verified by `test_score_all_domains_scores_all_sixteen_including_untouched_ones`. Decision
routing: any `CRITICAL` finding forces `CRITICAL_RISK` regardless of score; all-low-confidence
findings on a medium-or-worse-severity domain route to `MANUAL_REVIEW_REQUIRED` rather than
asserting a possibly-wrong automated verdict; otherwise threshold bands
(`HIGH_RISK` < 35 ≤ `REMEDIATION_REQUIRED` < 55 ≤ `ACCEPTABLE_WITH_OBSERVATIONS` < 75 ≤
`ACCEPTABLE`) apply to `weighted_score`.

## 8. Control catalog

`controls/catalog.py::CONTROL_CATALOG` is 8 illustrative, engineering-derived technical
controls, each mapped 1:1 to a Phase 2 scanner category by `rule_prefix` (e.g. `SECRET-` →
`CTRL-SECRET-001`). **This is explicitly not a banking regulatory control library** — every
entry's `control_type` is `ControlType.TECHNICAL`, and the module's own docstring points back
to `BANKING_PLATFORM_INTEGRATION_PLAN.md` §16 open question #4 (authoring a real regulatory
library requires domain expertise outside this engineering phase's scope, and remains open).
`control_for_rule_id()` is a pure prefix-match lookup, verified this session to correctly match
known prefixes and return `None` for unmapped ones, and verified that every catalog entry has a
unique `control_id` and `rule_prefix` (no ambiguous double-matches possible).
`upsert_catalog(session)` is verified this session to be genuinely idempotent — calling it
twice produces exactly 8 rows, not 16 — and to actually update (not just skip) an existing
row's fields on a second call, which a naive "insert if control_id not present" implementation
would fail to do.

## 9. Evidence capture

`evidence/capture.py::build_evidence()` is a pure function (no database access) that turns a
persisted `Finding` row's already-masked evidence into an `EvidenceResult` per finding, with a
human-readable `source_reference` (`path:line` for a single line, `path:start-end` for a
range) and `evidence_type` always `SCAN_RESULT` in Phase 3 (no RAG-retrieved or manually
uploaded evidence source exists yet). Tests added this session verify both `source_reference`
formats, confirm `retrieved_via` is always `None` today, confirm `content` passes through
unmodified (this module must never re-derive or further transform evidence — trusting the
caller's masking), and confirm `control_id` passes through as `None` when no control matched
rather than defaulting to some sentinel value.

## 10. Recommendation generation

`scoring/recommendations.py::generate_recommendations()` is a pure, deterministic-template
function — the same finding input always produces byte-identical text, verified this session
by calling it twice on the same input and asserting equality. Generated text embeds the
`rule_id`, `title`, `source_relative_path:line_start`, an optional banking-domain note (present
only when `domains` is non-empty — both branches tested), and the finding's own
`recommended_action`. `priority` mirrors `Severity`; `status` always starts `OPEN`; `source` is
always `RecommendationSource.DETERMINISTIC_TEMPLATE` — the field exists specifically so a
future Phase 6 LLM-backed source is never taken on faith (see the enum's own docstring).

## 11. `ScoringRepository` (persistence wiring)

`storage/db/repositories.py::ScoringRepository`, added alongside the existing `ScanRepository`
(deliberately not merged into it — the Phase 3 brief explicitly separates "deterministic
scanning," "evidence retrieval," "recommendation generation," and "human review" so they don't
collapse into one opaque autonomous flow):

- `score_scan(scan_id)` — reads persisted `Finding`/`DomainMappingRecord` rows for a scan,
  computes domain evaluation coverage from the mappings (not from findings alone), calls
  `score_all_domains()`, persists and returns 16 `Score` rows.
- `score_and_generate(scan_id)` — the full post-scan pipeline: idempotently upserts the control
  catalog, scores every domain, matches each finding's `rule_id` to a persisted `Control` row's
  real database id, captures evidence, generates recommendations, and commits all of it.
- `get_scores`, `get_recommendations`, `get_evidence_for_finding` — read accessors.
- `review_recommendation(id, status, reviewed_by)` — the minimal human-review action Phase 3
  requires; returns `None` for an unknown id rather than raising. The full
  `governance/approval_workflow.py` audit-trail module remains Phase 4+ scope.

Tests added this session (`tests/unit/test_scoring_repository.py`, in-memory SQLite, mirroring
`test_scan_repository.py`'s established pattern) verify: all 16 domains are always scored;
a domain no scanned file was mapped to resolves to `INSUFFICIENT_EVIDENCE` with `raw_score is
None` even when other domains have real findings; `score_and_generate` upserts the catalog
exactly once (no duplicate `Control` rows) and correctly links a `SECRET-001` finding's
evidence/recommendation to `CTRL-SECRET-001`'s real database id; no evidence row's `content`
ever contains the raw secret value scanned from the fixture; every persisted `Finding` defaults
`human_review_status` to `pending`; `review_recommendation` both succeeds and returns `None`
for an unknown id; `get_evidence_for_finding` filters correctly by finding id.

## 12. Live PostgreSQL/pgvector verification

The local Docker Postgres instance (`banking_assurance_db`, `pgvector/pgvector:pg16`, port
5434) provisioned in an earlier session was still running at the start of this session, and
`alembic upgrade head` had already been applied to it (verified: `alembic_version` plus all
Phase 2 and Phase 3 tables present before any test in this session ran). This session added
`tests/integration/test_postgres_phase3_scoring.py` (3 tests, skipped when `DATABASE_URL` is
unset, matching `test_postgres_persistence.py`'s Phase 2 pattern exactly) and ran it against
that live instance: the 4 Phase 3 tables (`controls`, `scores`, `evidence`, `recommendations`)
and the 3 new `findings` columns (`human_review_status`, `reviewed_by`, `reviewed_at`) exist on
the real schema, and a full `ingest → scan → persist → score_and_generate` round-trip against
the live database produces all 16 `Score` rows, at least one `Evidence` row with the raw secret
absent from its content, at least one `Recommendation` row, and correctly flags an untouched
domain (`investments_trading`) as `INSUFFICIENT_EVIDENCE`. No schema drift or FK-ordering bug
was found this session (contrast with Phase 2's §17.1, where live verification did surface two
real bugs) — `ScoringRepository` reads already-flushed `Finding`/`DomainMappingRecord` rows and
never inserts a child row before its parent's id exists, so the bug class named in Phase 2's
§26 risk note did not recur here.

## 13. Test summary

| Suite | Test count added this session |
|---|---|
| `tests/unit/test_control_catalog.py` | 6 |
| `tests/unit/test_evidence_capture.py` | 7 |
| `tests/unit/test_recommendations.py` | 9 |
| `tests/unit/test_scoring_repository.py` | 8 |
| `tests/integration/test_postgres_phase3_scoring.py` | 3 |
| **Total added this session** | **33** |
| `tests/unit/test_scoring_engine.py` (pre-existing, re-verified this session) | 12 |
| **Total Phase 3 test coverage** | **45** |

Full-suite command: `pytest` from the repo root.

- With `DATABASE_URL` unset: **288 passed, 9 skipped** (up from Phase 2's 258 passed/6 skipped
  — the 3 new live-Postgres tests join the pre-existing 5 live-Postgres + 1 symlink skip; the
  30 new always-runnable unit tests all pass).
- With `DATABASE_URL` set to the local test instance: the 3 new live-Postgres tests pass, and
  the pre-existing 5 Phase 2 live-Postgres tests continue to pass, alongside every other test —
  **295 passed, 1 skipped (symlink), 1 failed**. The 1 failure
  (`test_config_defaults.py::test_no_default_database_credential`) is not a Phase 3 defect: it
  is `Settings` correctly reading the `DATABASE_URL` environment variable this session
  deliberately exported to reach the live database, which is exactly what that test is designed
  to catch when a credential leaks into the environment — re-running the full suite with
  `DATABASE_URL` unset (the normal, no-live-db state) confirms **0 failures**.

## 14. Linting

No new lint issues were introduced by the 5 new test files — a manual `flake8 --select=F`
pass (matching Phase 1/2's practice: real-bug-class checks only, ignoring cosmetic
line-length) returned zero findings for all newly added files.

## 15. Known limitations

- The Phase 3 production code (§2) was written in an earlier session; this session's
  verification is necessarily a review-and-test pass, not a from-scratch implementation
  review of every design decision. Design rationale embedded in each module's own docstrings
  was read and cross-checked against `BANKING_PLATFORM_INTEGRATION_PLAN.md` §9/§11/§13 for
  consistency, but no line-by-line security review beyond the tests above was performed in
  this session.
- `ScoringRepository.review_recommendation()` is a minimal, single-row human-review action —
  it is not the `governance/approval_workflow.py` audit-trail module the plan describes for
  Phase 4; no history of review actions is kept beyond the row's own
  `status`/`reviewed_by`/`reviewed_at` fields being overwritten on each call.
- `controls/catalog.py`'s 8 entries remain illustrative technical controls, not a banking
  regulatory/compliance library — unchanged, open question (§16 #4 in the plan).
- No performance/scale testing was done against a large real repository or a large finding
  set — only the small synthetic fixtures already used by Phase 2's tests.
- The live-Postgres verification in §12 is a single-process, single-scan correctness check,
  not a concurrency or long-running-stability test — same caveat Phase 2's §15 already noted
  for its own live verification.

## 16. Remaining risks

- No risk class comparable to Phase 2's foreign-key-ordering bug was found in this session's
  live verification of `ScoringRepository`, but that absence reflects one test scenario (a
  single small scan), not exhaustive coverage of every insert ordering `score_and_generate()`
  could hit under different data shapes.
- `control_for_rule_id()`'s prefix-matching is order-dependent if a future control's
  `rule_prefix` were a prefix of another's (e.g. adding `"SECRET"` would also match
  `"SECRET-001"`'s existing `"SECRET-"` control unpredictably depending on catalog order) —
  today's 8 entries have no such collision (verified this session), but nothing enforces that
  invariant going forward except the new uniqueness test.

## 17. Deferred Phase 4 items

Per `BANKING_PLATFORM_INTEGRATION_PLAN.md` §13's Phase 4 ("Complete Banking Domain and
Governance Layer"): `assessment/engine.py`, `assessment/evaluators/*` (generalized from
`ai-project-control-tower/app/agents/*`), `knowledge_base/controls/` content across all 16
`BankingDomain` values, `governance/approval_workflow.py`, `governance/audit_trail.py`,
`models/audit_event.py`, retention foundations, report disclaimers. **Awaiting explicit
approval to begin Phase 4** — no file under `assessment/engine.py`, `assessment/evaluators/`,
`governance/approval_workflow.py`, `governance/audit_trail.py`, or `models/audit_event.py`
exists beyond the Phase 1 placeholder `README.md`/`__init__.py` files already present.

## 18. Git status

At the end of this session (`git status --porcelain`), the only changes are 5 new untracked
test files and this new completion report — no existing file was modified, and no Phase 3
production code (§2/§6) was touched. Nothing was staged or committed; git state is left for
the user to review and commit explicitly.

## 19. Final Phase 3 verdict

**Phase 3 is complete.** The scoring engine correctly delivers the core fix named in the
integration plan's Executive Summary (insufficient evidence is never mistaken for a clean
score), every Phase 3 module now has dedicated test coverage (45 tests total: 12 pre-existing
+ 33 added this session), and the Phase 3 Alembic migration is verified against a live
PostgreSQL/pgvector instance, not merely construction-tested. **Phase 4 was not started:** no
file under `assessment/engine.py`, `assessment/evaluators/`, `governance/approval_workflow.py`,
`governance/audit_trail.py`, or `models/audit_event.py` exists beyond Phase 1's placeholders.
