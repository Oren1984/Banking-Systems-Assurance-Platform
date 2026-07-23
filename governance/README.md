# governance/

## Phase 1 (implemented — sanitization foundations)

- `secret_masker.py` — regex-based secret detection/masking (AWS/GitHub/OpenAI/Anthropic/
  Google keys, JWTs, quoted assignments, connection-string credentials). The single detection
  implementation `scanners/rules/secret_scanner.py` and `agents/sanitizer.py` both reuse —
  never duplicated.
- `report_sanitizer.py` — re-masks secrets and strips auto-fix/patch-plan content from any
  report. The code-level enforcement of "recommend, never auto-fix."
- `pii_redaction.py` — regex-based PII redaction (email, phone-shaped, long digit runs).
  Explicitly non-exhaustive — see the module's own docstring and `docs/security_boundaries.md`.
- `prompt_safety.py` — suspicious-query pattern scan. Advisory-only (`enforce=False`) by
  default; `enforce=True` is a documented extension point for a hard gate. First actually used
  in `enforce=True` mode in Phase 6, by `agents/sanitizer.py::build_question_context()`.
- `file_validation.py` — upload/query input validation (path traversal, filename sanitization).

## Phase 4 (implemented — human-in-the-loop governance)

- `approval_workflow.py` — pure validation functions for finding review (`review_finding()`)
  and score override (`override_score()`), plus the finalization policy
  (`check_finalization_policy()`: a domain scored `high_risk`/`critical_risk` with any pending
  finding blocks finalization). No database access — `storage/db/repositories.py::GovernanceRepository`
  applies these validated decisions.
- `audit_trail.py` — `build_audit_event()`, a pure, sanitizing event builder.
  `storage/db/repositories.py::AuditRepository` is the only writer of the resulting
  `audit_events` table, which is append-only by construction (no update/delete method exists
  anywhere in this codebase for it).
- `retention.py` — identify-only retention foundations (`find_scans_eligible_for_retention()`).
  Never deletes anything; see the module's own docstring for exactly what remains a deliberate,
  open decision for a later phase.

## What this directory is, architecturally

The platform's one sanitization/governance boundary — every module elsewhere that needs to
mask a secret, redact PII, validate a review action, or record an audit event calls into this
directory rather than reimplementing the logic. `agents/` (Phase 6) is the newest consumer of
this pattern, not a second one: `agents/sanitizer.py` reuses `report_sanitizer.py`,
`pii_redaction.py`, and `prompt_safety.py` directly rather than duplicating detection logic.
