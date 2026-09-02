# Reference Bank — Planted Findings Inventory

This is the authoritative, **actually-executed** record of what scanning
`reference_banking_system/` produces — the second, well-governed demo fixture (contrast this
against `docs/mock_banking_planted_findings.md`). Every number below was captured by running
`scanners.scan_orchestrator.run_scan` and `assessment.engine.run_assessment` against this exact
fixture tree in this session, not predicted by hand, exactly matching the practice
`docs/mock_banking_planted_findings.md` established — see
`tests/unit/test_reference_banking_system_fixture.py` for the tests that pin these numbers.

**No real credentials, personal information, production data, or external dependencies appear
anywhere in this directory.** Every value is synthetic.

## Why this fixture exists

`mock_banking_system/` demonstrates the platform finding real problems. This fixture
demonstrates the other half of the same story: what the platform reports when the code it
scans actually follows its own control catalog — `satisfied`/`acceptable` earned through real,
evaluated evidence (see `assessment/evaluators/control_evaluator.py` and
`scoring/engine.py`: both require a domain to be positively **evaluated** — a real file mapped
to it by `scanners/domain_mapper.py` — before any non-`insufficient_evidence` result is
possible; absence of scanning is never mistaken for absence of problems). This mechanism, and
this fixture's design, were verified against the evaluator's actual source before
implementation — see the session record for that verification.

## Top-level result (as of this session)

- Files scanned: **11** (all 11 discovered files — nothing skipped)
- Total findings: **1**
- By severity: `low=1`
- Domains evaluated: **5 of 16** — deliberately, not a gap: this is a small, focused codebase,
  and the other 11 domains correctly resolve to `insufficient_evidence` rather than a false
  "clean" score. See `reference_banking_system/README.md`, "Deliberate scope."
- The same fixture scanned twice in the same session produces byte-identical findings —
  verified by
  `tests/unit/test_reference_banking_system_fixture.py::test_scanning_the_reference_system_twice_is_deterministic`.
- Scanning this fixture never modifies it — verified by the same test file's
  `test_scanning_the_reference_system_never_modifies_it`.

## The one planted finding

| File | Rule | Severity | Intent |
|---|---|---|---|
| `api/routes/openapi_routes.yml` | `CFG-008` | low | `display_errors: true` left enabled — a deliberately minor, credible gap so this fixture is a genuine assessment result, not a suspiciously perfect one, and so the Governance tab has something real to review. |

Every other file in this fixture is a deliberate **positive** example — parameterized queries,
no hardcoded secrets, masked/safe logging, least-privilege IAM (no wildcard `Action`/`Resource`,
no `role = admin`), and review-trail calls (`user=`, `action=` keyword arguments) present on
every sensitive operation, using the exact same call pattern
`mock_banking_system/app/accounts/account_lookup_clean.py` already proves the scanner
recognizes as satisfying `AUDIT-002`/`AUDIT-003`.

## Domain scores (full `run_assessment()` result, this session)

| Domain | Decision category | Weighted score | Confidence | Findings | Files evaluated |
|---|---|---|---|---|---|
| `application_security` | `acceptable` | 100.0 | high | 0 | 4 |
| `core_banking` | `acceptable` | 100.0 | medium | 0 | 2 |
| `infrastructure_api_security` | `acceptable` | 96.5 | medium | 1 | 2 |
| `model_ai_governance` | `acceptable` | 100.0 | medium | 0 | 1 |
| `payments` | `acceptable` | 100.0 | medium | 0 | 2 |
| (all other 11 domains) | `insufficient_evidence` | — | low | 0 | 0 |

**Direct, same-domain contrast with `mock_banking_system/`:** all four of
`application_security`, `infrastructure_api_security`, `payments`, and `core_banking` score
`critical_risk` or `high_risk` there; all four score `acceptable` here, on the same platform,
the same scanners, the same scoring engine — the only variable is the source code itself.

**`model_ai_governance` is the fixture's other headline result:** `mock_banking_system/`
deliberately never evaluates this domain (see that fixture's "Intentional gap"); this fixture
does, with one real file and zero findings, resolving to `acceptable` at a clean 100.0 rather
than `insufficient_evidence` — the same `business_continuity_dr`-style "genuinely checked and
found clean" case, demonstrated on the one domain the primary demo leaves untouched.

## Control evaluations (this session)

A full `run_assessment()` call produces the same **68** `ControlEvaluation` rows every scan of
any source produces (16 domains × `controls/catalog.py`'s applicable controls — a fixed
function of the domain/control catalog, not of what was scanned): **21 `satisfied`**, **1
`gap`** (the one `CFG-008` finding, against `CTRL-CFG-001` in `infrastructure_api_security`),
and **46 `insufficient_evidence`** (the 11 unevaluated domains' applicable controls).

`model_ai_governance`'s four applicable (cross-cutting) controls are all **`satisfied`** here —
the direct opposite of `mock_banking_system/`'s four `insufficient_evidence` results for the
same domain's same controls.

## Governance and finalization

Because no finding in this fixture is `high`/`critical` severity, **no domain scores
`high_risk`/`critical_risk`** — `governance/approval_workflow.py::check_finalization_policy()`
therefore reports this assessment **can be finalized immediately**, with zero review actions
required (verified by direct test of `check_finalization_policy()` during implementation,
using this fixture's real domain/decision-category set). This is the fixture's clearest
contrast with `mock_banking_system/`, whose finalization banner starts red and requires active
review to clear.

The one finding is still `pending` human review by default, so the Governance tab has one real
review action available for the walkthrough — it is simply not required to reach finalization,
unlike the primary demo.
