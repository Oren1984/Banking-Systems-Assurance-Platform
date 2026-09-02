# reference_banking_system/

## Purpose

A second, small, entirely synthetic banking codebase used to demonstrate that this platform's
scan → score → control-evaluation → governance → export pipeline produces a genuinely
different, credible result when it examines source that actually follows its own control
catalog — not because negative findings were suppressed, but because the code in this
directory was written to avoid the specific patterns `scanners/rules/*.py` checks for, and
includes explicit review-trail calls (`user=`, `action=` fields) that the scanner's own
heuristics already recognize as positive evidence (the exact mechanism already proven by
`mock_banking_system/app/accounts/account_lookup_clean.py`).

This directory does not modify, replace, or reduce `mock_banking_system/` in any way — it is a
separate, additive fixture. See `docs/demo_guide.md` for how to run this scenario and
`docs/reference_banking_system_findings.md` for its actual, executed finding inventory (every
number there was captured by running the real scanner/assessment pipeline, not predicted by
hand — the same practice `docs/mock_banking_planted_findings.md` follows).

## Hard rules (same as mock_banking_system/'s own — see that directory's README)

- No real customer, bank, employee, account, transaction, credit, investment, identity, or
  payment information may be used, ever.
- No real secrets, credentials, or API keys — synthetic placeholders only.
- Everything here must be clearly identifiable as a demonstration artifact, never mistaken for
  a real banking system or genuine compliance evidence.
- Meta-documentation about this fixture and every generated assessment export live outside this
  directory, for the same self-contamination reason documented in `mock_banking_system/README.md`.

## Directory layout

| Directory | Purpose | Banking domain touched |
|---|---|---|
| `app/security/` | Least-privilege access policy, encryption configuration | `application_security` |
| `app/payments/` | Card/settlement processing | `payments` |
| `app/accounts/` | Core banking account service | `core_banking` |
| `app/ml_model_risk/` | Model risk governance documentation | `model_ai_governance` |
| `api/routes/` | API route exposure configuration (carries the one planted finding) | `infrastructure_api_security` |
| `infra/terraform/` | Least-privilege IaC example | `infrastructure_api_security` |

## Deliberate scope: five domains, not sixteen

This fixture intentionally touches only the five domains above — the four that score
`critical_risk`/`high_risk` in `mock_banking_system/` (`application_security`,
`infrastructure_api_security`, `payments`, `core_banking`), for a direct, same-domain
contrast, plus `model_ai_governance`, which `mock_banking_system/` deliberately leaves
unevaluated (see that fixture's README, "Intentional gap"). The other eleven domains are not
represented here and correctly resolve to `insufficient_evidence` — this is the platform's core
correctness guarantee working exactly as designed, not a gap in this fixture's construction:
a small, focused codebase does not get a free "clean" score for the parts of the business it
never touches.

## What this fixture is not

Not a claim that any of these five domains are exhaustively covered or regulation-compliant —
see `docs/security_boundaries.md`. It demonstrates the scoring and control-evaluation mechanism
operating on real, evaluated evidence that happens to follow the platform's own control
catalog, nothing more.
