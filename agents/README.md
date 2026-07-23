# agents/

## Phase 6 (implemented — see `PHASE_6_COMPLETION_REPORT.md`)

The optional external-agent boundary. Sits **outside** the deterministic assessment core —
nothing under `scanners/`, `scoring/`, `assessment/evaluators/`, `governance/approval_workflow.py`,
or `storage/db/repositories.py`'s write paths imports from this package, and nothing in this
package writes to a `Finding`, `Score`, `ControlEvaluation`, or `Recommendation` row. See
`docs/architecture.md`'s module-boundary diagram and `docs/agent_guide.md` for the full
picture.

| Module | Responsibility |
|---|---|
| `contracts.py` | `AgentContext` (sanitized, size-limited input), `AgentResponse` (always-advisory output), `ADVISORY_DISCLAIMER` |
| `sanitizer.py` | The dedicated context-minimization boundary — the only place raw assessment data is turned into what may be sent anywhere (local or external). Reuses `governance/report_sanitizer.py`, `governance/pii_redaction.py`, and (for free-text questions) `governance/prompt_safety.py` in hard-gate mode. Enforces both a character limit and an item-count limit. |
| `local_agent.py` | The always-available, deterministic default. Never fabricates AI-sounding prose — presents the exact sanitized context directly, clearly labeled as non-AI. |
| `registry.py` | `get_agent_provider()` — safe provider selection; always resolves to local mode or a genuinely available external adapter, never a crash, never "nothing." `validate_agent_configuration()` — a pure diagnostic for the UI. |
| `agent_service.py` | The four supported advisory actions (`explain_finding`, `summarize_domain`, `answer_question`, `generate_executive_summary`). Pure — no database. Every external-adapter call is wrapped; any failure (including the `NotImplementedError` every provider adapter's `send()` currently raises) gracefully falls back to local mode rather than propagating. |

`ui/services/agent_ui_service.py` (not in this package, by design — see that module's own
docstring) is the only place this boundary touches a database: it fetches already-persisted
Finding/Score rows, converts them to this package's plain input dataclasses
(`agents/sanitizer.py::FindingForAgent`/`DomainScoreForAgent`), calls into `agent_service.py`,
and records exactly one `AuditEvent` per action (metadata only — never a raw prompt or
response, see `storage/db/models/audit_event.py`).

## What this boundary can never do

Modify source systems or scanned files; change a finding, score, or control-evaluation result;
approve a governance review; finalize an assessment; create a silent score override; bypass
human-in-the-loop review; access an unrestricted file path; transmit an entire repository or
raw source file; or expose a secret, credential, token, or unnecessary PII. See
`docs/agent_guide.md`'s "Security and Privacy Boundaries" section for how each of these is
actually enforced, with file/test references.

## Default operating mode

`AGENT_ENABLED=false` by default (`.env.example`). Even when enabled, `AGENT_PROVIDER=local` is
the default — an operator must explicitly select an external provider *and* that provider must
already satisfy `providers/registry.py`'s own three-condition activation rule (platform-wide
kill switch, the specific provider's own enable flag, a non-empty API key) before
`agents/registry.py::get_agent_provider()` ever returns anything other than local mode.

## Relationship to `providers/`

`providers/` (Phase 1 scaffolding, finalized in Phase 6) is the low-level adapter layer —
`ProviderAdapter`, `ProviderRequest`/`ProviderResponse`, and the three provider-specific
adapters. `agents/` is the layer above it that this platform's UI actually calls. No adapter's
`send()` performs a real outbound HTTP call in this codebase (see `providers/README.md`) — a
deliberate Phase 6 scope boundary, not an oversight.
