# Demo Guide — End-to-End Walkthrough

This guide walks through the complete demonstration workflow:

**Mock Banking System → Read-Only Ingestion → Scanning → Evidence → Scoring → Control
Evaluation → Governance Review → Final Assessment Report**, plus the optional Phase 6 agent
boundary.

Every number quoted below is real, reproducible output — see
`docs/mock_banking_planted_findings.md` for the full inventory and
`tests/unit/test_mock_banking_fixture.py` for the regression tests that pin it. If a number
here ever stops matching what you actually see, that is a real regression — check the test
suite before assuming this guide is stale.

## Prerequisites

- Python dependencies installed: `pip install -r requirements.txt`
- A local PostgreSQL/pgvector instance, reachable via `DATABASE_URL` (a Docker Compose service
  is provided — see `deployment/docker-compose.yml`). `DATABASE_URL` must **not** contain the
  known-insecure placeholder credential `control_tower_pass` (rejected by `core/config.py` on
  construction).
- `ALLOWED_SCAN_PATHS` including the repository root (or specifically `mock_banking_system`) —
  required by `scanners/path_validator.py`, which fails closed if unset.

## 1. Start dependencies

```bash
docker compose -f deployment/docker-compose.yml up -d
```

## 2. Configure the environment

```bash
cp .env.example .env   # then edit .env with real local values — never commit it
export DATABASE_URL="postgresql://<user>:<password>@localhost:5434/<db>"
export ALLOWED_SCAN_PATHS="mock_banking_system"
```

## 3. Run database migrations

```bash
alembic upgrade head
```

Applies every migration through `alembic/versions/..._phase4_audit_trail_control_evaluations.py`
(the most recent — Phase 5 and Phase 6 added no new tables). Safe to re-run; Alembic tracks the
current revision and applies nothing twice.

## 4. Launch the application

```bash
streamlit run ui/streamlit_app.py
```

The sidebar offers two modes: **"Quick Scan only (no database)"** and **"Full Assessment
(recommended)"**.

## 5. Run Quick Scan

Select **"Quick Scan only (no database)"** in the sidebar. This is the original, unmodified
Phase 2 workflow — no `DATABASE_URL` is required. Choose a local directory or ZIP archive under
an `ALLOWED_SCAN_PATHS` entry, click **Validate and Start Read-Only Scan**, and review the
summary and JSON/Markdown export buttons. Nothing here persists to a database or unlocks
scoring/governance — that requires Full Assessment mode (next step).

## 6. Run Full Assessment

Switch to **"Full Assessment (recommended)"**. Under "1. Select Source and Run Assessment,"
leave the default source ("Mock Banking System (demo)") selected and click **Run Full
Assessment**. Wait for the "Assessment complete" success message.

Equivalent from the command line (no UI, fastest):

```bash
python -m scripts.seed_mock_banking_demo
```

Expected output (exact counts — see `docs/mock_banking_planted_findings.md`):

```
Mock banking demo assessment complete — scan_id=<uuid>
  Findings: 42
  Domain scores: 16
  Control evaluations: 68
  Recommendations: 42
  Audit events: 4
Sample exports written to:
  - data/reports/mock_banking_demo/latest_assessment.json
  - data/reports/mock_banking_demo/latest_assessment.md
```

`mock_banking_system/` is a static, synthetic fixture already committed to the repository (see
`mock_banking_system/README.md`) — nothing in this step "loads" it, and it is never modified;
that guarantee is re-proven by
`tests/security/test_assessment_no_source_modification.py::test_running_the_mock_banking_demo_assessment_never_modifies_the_fixture`.

## 7. Review domain scores

The **Domain Scores** tab shows all 16 domains. Look specifically at:

- **`application_security`** — `critical_risk`, weighted score 0.0. A `PERM-001` wildcard-IAM
  finding is `critical` severity, which forces `CRITICAL_RISK` regardless of the numeric score
  (`scoring/engine.py`'s documented precedence).
- **`business_continuity_dr`** — `acceptable`, weighted score exactly 100.0, **0 findings, 1
  file evaluated**. This domain was genuinely checked and found clean.

Open the **Control Evaluations** tab to see the 68 (domain, control) results: 56 `satisfied`,
8 `gap`, 4 `insufficient_evidence` (the four cross-cutting controls, all under
`model_ai_governance` — see step 13).

## 8. Review findings and traceability

In the **Findings & Evidence** tab, filter by severity, domain, rule, or file path. Expand any
finding to see its sanitized (`masked_evidence`) evidence, description, and advisory-only
recommended action — never a raw secret. Click **"Show full traceability"** on any finding to
see the complete chain: matched control id(s), the `ControlEvaluation` status it caused,
evidence row ids, its domain's current score, and its recommendation id(s).

Try the `app/payments/payment_processor.py` finding (`SECRET-001`, high severity) — its
evidence shows a masked credential, never the real fake value from the source file.

## 9. Perform governance review

Go to the **Governance** tab.

- The top banner reads **"This assessment CANNOT be finalized yet"** and lists every
  high/critical-risk domain with a pending finding (`application_security`, `core_banking`,
  `infrastructure_api_security`, `payments`, at minimum).
- Under **"Review a finding,"** pick any pending finding, choose a decision (`approved`,
  `rejected`, or `overridden` — `overridden` requires a reason), enter a reviewer identity, and
  click **Submit review**. The finding's `human_review_status` updates immediately and a
  `finding_reviewed` event appears in the audit trail below.

## 10. Create a score override

Still on the **Governance** tab, under **"Override a domain score,"** pick a domain's current
score, choose a new decision category, enter a mandatory justification, and click **Submit
override**. A **new** `Score` row is created, linked to the original via `override_of` — the
original row is never mutated. Expand that domain in the **Domain Scores** tab afterward to see
both rows under "Score history."

## 11. Test finalization blocking and unblocking

With even one finding still `pending` in a high/critical-risk domain, the banner stays red —
this is `governance/approval_workflow.py::check_finalization_policy()` working as designed, not
a bug; there is no way to bypass it from the UI. Review every finding in one blocking domain
(e.g. `payments`, which has only 2 findings) until none remain `pending` for that domain.
Re-open the Governance tab — that domain no longer appears in the blockers list. Finalization
becomes possible once **every** high/critical-risk domain has no pending findings (an override
that changes a domain's category away from high/critical-risk also removes it from the blockers
list, as shown in step 10).

There is no separate "finalize" button or persisted "final" flag — finalization is a **policy
check**, not a state transition (a `Report`/finalization-state entity was never scoped; see
`models/README.md`). Once the banner turns green ("This assessment CAN be finalized"), the
assessment is, by the platform's own definition, eligible to be finalized — export the report
next.

## 12. Export reports

Go to the **Export** tab and download any of: JSON, Markdown, Findings CSV, or Scores CSV. Every
format includes the same governance disclaimers, domain scores, control evaluations,
recommendations, human-review status, and audit trail — and never a raw secret (verified by
`tests/unit/test_assessment_report_exporter.py` and
`tests/unit/test_assessment_service.py::test_export_assessment_returns_all_formats_with_no_raw_secret`).

The same exports are written automatically to `data/reports/mock_banking_demo/` by
`scripts/seed_mock_banking_demo.py` (step 6) — deliberately **outside** `mock_banking_system/`
itself (see `mock_banking_system/README.md`'s "Hard rules": a report scanned alongside the
fixture that produced it would corrupt the fixture's own deterministic finding count — found and
fixed during Phase 5's implementation).

## 13. Review the insufficient-evidence domain

In the **Domain Scores** tab, find **`model_ai_governance`** — `insufficient_evidence`, weighted
score **`N/A`** (`None`), 0 files evaluated. No mock content touches this domain at all —
deliberately, per `docs/mock_banking_planted_findings.md`'s "Intentional gap" section. This is
the platform's core correctness guarantee, shown live: a domain nobody has evaluated yet is
never reported as a false "clean" 100/100. Phase 6 added no evidence for this domain — it
remains the platform's live demonstration of this guarantee unchanged.

## 14. Optionally activate the external agent

Open the **AI Assistant (Optional)** tab. By default it shows **"Mode: Local (no external AI
provider)"** — every action (explain a finding, summarize a domain, ask a question, generate an
executive summary) works immediately with no configuration, no API key, and no data leaving the
local environment. See `docs/agent_guide.md` for how to point `AGENT_PROVIDER` at an external
provider; because no adapter's `send()` makes a real outbound call in this codebase (a
deliberate, documented scope boundary — see `providers/README.md`), attempting external mode
today always gracefully falls back to local, with a clear on-screen explanation of why. Using
this tab never changes the Findings/Domain Scores/Control Evaluations/Governance tabs' numbers —
only the audit trail grows, by one `agent_action` event per action.

## 15. Run the second scenario: the well-governed Reference Banking System

Back at step 6 ("1. Select Source and Run Assessment"), choose **"Reference Banking System
(well-governed demo)"** instead of the mock system and click **Run Full Assessment** again —
this starts a second, independent assessment; it does not replace the one above. See
`docs/reference_banking_system_findings.md` for the full, actually-executed inventory. This
scenario exists to show the direct opposite outcome, on the same platform:

- **Same four domains, opposite result.** `application_security`, `infrastructure_api_security`,
  `payments`, and `core_banking` all score `critical_risk`/`high_risk` in the mock system above
  — all four score `acceptable` here, because the source code in this fixture actually follows
  the platform's own control catalog (parameterized queries, no wildcard IAM, review-trail calls
  present on sensitive operations), not because anything was hidden from the scanner.
- **`model_ai_governance` is evaluated for the first time.** Step 13 showed this domain as
  `insufficient_evidence` because the mock system deliberately never touches it. Here, one real
  file maps to it and produces zero findings — `acceptable`, weighted 100.0. Open the **Domain
  Scores** tab and compare the two scan results side by side.
- **Finalization is immediately available.** Open the **Governance** tab — the banner reads
  **"This assessment CAN be finalized"** right away, with no review required, because no domain
  scored `high_risk`/`critical_risk`. Contrast this against step 9's blocked banner. One finding
  (`CFG-008`, low severity) is still available to review if you want to demonstrate the review
  flow anyway — it just isn't required to unblock finalization here.
- **The other 11 domains still correctly show `insufficient_evidence`.** This is a small,
  focused fixture, not a system that was silently declared clean everywhere — the platform's
  core correctness guarantee (step 13) applies here too.

`reference_banking_system/` is a separate, additive fixture — it never modifies, replaces, or
reduces `mock_banking_system/`, and both remain independently selectable from the same UI.

## Expected results reference

### Mock Banking System (the primary, flawed-legacy-system scenario)

| Metric | Expected value |
|---|---|
| Total findings | 42 |
| Severity breakdown | critical=4, high=18, medium=10, low=10 |
| Domains evaluated | 15 of 16 (`model_ai_governance` excluded, deliberately) |
| Domain scores | 16 (one per `BankingDomain`, always — see `scoring/engine.py`) |
| Control evaluations | 68 (56 satisfied, 8 gap, 4 insufficient_evidence) |
| Recommendations | 42 |
| Audit events per assessment run | 4 (`scan_persisted`, `scoring_completed`, `control_evaluation_completed`, `assessment_completed`) — grows by 1 per subsequent governance or agent action |
| `DecisionCategory` values represented | all 7 |

If any of these numbers differ from what you observe, run
`pytest tests/unit/test_mock_banking_fixture.py -v` first — it will tell you precisely which
number changed and on which file, rather than requiring you to eyeball a full scan output.

### Reference Banking System (the second, well-governed scenario)

| Metric | Expected value |
|---|---|
| Total findings | 1 |
| Severity breakdown | low=1 |
| Domains evaluated | 5 of 16 (`application_security`, `core_banking`, `infrastructure_api_security`, `model_ai_governance`, `payments`) |
| Domain scores | 16 (5 `acceptable`, 11 `insufficient_evidence`) |
| Control evaluations | 68 (21 satisfied, 1 gap, 46 insufficient_evidence) |
| Recommendations | 1 |
| Audit events per assessment run | 4, same baseline as above |
| Finalization | immediately eligible — no `high_risk`/`critical_risk` domain |

If any of these numbers differ from what you observe, run
`pytest tests/unit/test_reference_banking_system_fixture.py -v` first, for the same reason.
