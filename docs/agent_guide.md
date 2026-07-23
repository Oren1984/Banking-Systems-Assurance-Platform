# Optional Agent Guide — Provider Architecture, Security, and Setup

This document covers the Phase 6 optional external-agent boundary: what it is, what it is not,
how to configure it, and exactly how it is kept outside the platform's trusted, deterministic
core. See `PHASE_6_COMPLETION_REPORT.md` for what was built and tested this phase, and
`agents/README.md`/`providers/README.md` for the module-level breakdown.

## What this is, in one paragraph

An optional, clearly-labeled advisory layer that can explain a finding, summarize a domain,
answer a question using existing assessment evidence, or draft an executive narrative — all in
plain language — on top of data the deterministic pipeline already produced. It is off by
default, it never changes a finding/score/governance decision, and the entire assessment
workflow (Quick Scan, Full Assessment, scoring, control evaluation, governance review,
overrides, finalization, reporting, traceability) works identically whether this layer is
enabled or not.

## Local-first operating model

| Layer | Default | What it does |
|---|---|---|
| Deterministic core (`scanners/`, `scoring/`, `assessment/`, `governance/approval_workflow.py`) | Always on | Everything the platform is actually assessed by. No agent involvement, ever. |
| Local RAG (`rag/vectorstores/{chroma_store,pgvector_store}.py`) | On (mock/local embeddings) | The platform's default intelligence layer for anything vector-search-related — unaffected by the agent boundary, which does not use retrieval today (see "Limitations" below). |
| Optional agent — local mode (`agents/local_agent.py`) | **The default whenever the agent feature is used** | Deterministic, template-based presentation of already-sanitized data. No network call, no API key, no cost. |
| Optional agent — external mode | **Off unless explicitly configured** | Sends sanitized, size-limited context to a configured external provider. See "Configuration" and "Security and Privacy Boundaries" below. |

## Supported providers

| Provider | Adapter | Real outbound call implemented? |
|---|---|---|
| OpenAI / ChatGPT-compatible | `providers/openai_adapter.py` | No — configuration-ready stub, see "Why send() only raises" below |
| Anthropic Claude | `providers/claude_adapter.py` | No — same |
| Google Gemini | `providers/gemini_adapter.py` | No — same |

### Why `send()` only raises `NotImplementedError`

This is a deliberate, documented scope boundary for this project (see `providers/README.md`),
not a bug. Every adapter is fully configuration-ready — API key, model name, timeout, and
retry-limit are all read from settings, validated, and stored — but no adapter imports a
network-client library or a vendor SDK, and no real HTTP call is ever made anywhere in this
codebase. `agents/agent_service.py` already treats this exception as an ordinary provider
failure and falls back to local mode automatically (see "Failure handling" below) — so the
behavior an operator actually sees, end to end, is a graceful, honest fallback, never a crash.

## Setup instructions (local mode — the default)

Nothing to do. `AGENT_ENABLED=false` by default; the "AI Assistant (Optional)" tab in
`ui/streamlit_app.py`'s Full Assessment mode is present and fully usable in local mode with no
configuration.

## Setup instructions (attempting external mode)

Real external execution is out of this project's approved scope (see above) — attempting
external mode today will always gracefully fall back to local, with a clear on-screen message
explaining why. To exercise the configuration surface itself (e.g. for testing):

```env
AGENT_ENABLED=true
AGENT_PROVIDER=openai            # local | openai | gemini | claude
AGENT_MODEL_NAME=                # optional — falls back to each adapter's own documented default
AGENT_TIMEOUT_SECONDS=30
AGENT_MAX_RETRIES=1
AGENT_MAX_CONTEXT_CHARS=4000
AGENT_MAX_EVIDENCE_ITEMS=5

EXTERNAL_PROVIDERS_ENABLED=true  # the platform-wide kill switch — see docs/security_boundaries.md
OPENAI_ENABLED=true
OPENAI_API_KEY=                  # leave empty unless you have deliberately decided to test this path
```

All four conditions (`AGENT_ENABLED`, `AGENT_PROVIDER != local`, `EXTERNAL_PROVIDERS_ENABLED`,
the specific provider's own `{NAME}_ENABLED`/`{NAME}_API_KEY`) must hold before
`agents/registry.py::get_agent_provider()` returns anything other than local mode — see that
module's own docstring for the exact precedence, and `tests/unit/test_agent_registry.py` for
every failure mode tested.

## Environment variables

See `.env.example` for the complete, placeholder-only reference. Every value above has a safe
default (`AGENT_ENABLED=false`, `AGENT_PROVIDER=local`, all API keys empty).

## Security and Privacy Boundaries

| Requirement | How it is enforced |
|---|---|
| No entire repository sent by default | `agents/sanitizer.py` only ever builds context from one finding, one domain's findings (capped at `AGENT_MAX_EVIDENCE_ITEMS`), a question plus a capped evidence list, or a capped domain-score overview — never a file, never a directory tree. |
| No raw secrets | Every context passes through `governance/report_sanitizer.py::sanitize_report()` (secret masking + auto-fix stripping) before anything else — verified by `tests/unit/test_agent_sanitizer.py` and end-to-end by `tests/security/test_agent_no_secret_leakage.py`. |
| No unnecessary PII | A second pass, `governance/pii_redaction.py::redact_pii()`, runs after sanitization. |
| Payload size limits | `AGENT_MAX_CONTEXT_CHARS` (default 4000) and `AGENT_MAX_EVIDENCE_ITEMS` (default 5) are both enforced in `agents/sanitizer.py`, independent of whatever limit a provider's own API might separately impose. |
| Explicit external transmission | External mode requires four separate, explicit configuration conditions (see "Setup instructions" above) plus an explicit UI button click for the specific action — nothing is sent when an assessment or the agent tab is merely opened. |
| Prompt-injection awareness | Free-text questions are passed through `governance/prompt_safety.py::check_prompt_safety(enforce=True)` — a suspicious pattern is rejected outright (`GovernanceError`), not merely warned about. |
| No automatic external call | `agents/registry.py::get_agent_provider()` never selects an external provider unless all four conditions above hold; the UI never calls an agent action without an explicit button click. |

## Consent requirements

The "AI Assistant (Optional)" tab always states, before any action can be triggered: the
current mode (local or the specific external provider); that sanitized evidence **may leave
the local environment** in external mode; that output is advisory, non-authoritative, and
non-deterministic; and that deterministic findings, scores, control evaluations, and
finalization status are never altered by anything on that tab. See `ui/streamlit_app.py::_agent_tab()`.

## Failure handling

Every external-adapter call in `agents/agent_service.py::_run()` is wrapped. Any exception —
including the `NotImplementedError` every adapter's `send()` currently raises — results in a
graceful fallback to the local, deterministic response, with `AgentResponse.success=False` and
a sanitized error message. The assessment the agent was asked about is never affected; no
exception from this boundary propagates into `assessment/engine.py` or any deterministic code
path — verified by `tests/unit/test_agent_service.py` and
`tests/unit/test_agent_ui_service.py::test_agent_actions_do_not_change_deterministic_findings_or_scores`.

## Audit behavior

Every agent action records exactly one `AuditEvent` (`AuditEventType.AGENT_ACTION`) via the
same append-only `AuditRepository` every other governance action uses. The payload contains
only: action type, provider/mode, model name, success/failure, a sanitized error (if any),
context categories used, and whether the action was user-triggered — never a raw prompt, a raw
response, or evidence content. Verified field-by-field by
`tests/unit/test_agent_ui_service.py::test_agent_audit_payload_contains_no_raw_prompt_or_response_content`.

## Limitations

- No real outbound API call is implemented for any of the three providers (see "Why send()
  only raises" above) — external mode is configuration-ready, not functionally complete.
- The agent boundary does not use `rag/vectorstores/` retrieval today — "answer a question"
  context comes from already-persisted Finding rows for the current scan, not a vector search.
  Wiring the agent to local RAG retrieval remains a candidate for a future phase.
- `agents/local_agent.py` never generates new natural-language prose — it presents the
  sanitized, already-deterministic context directly. A true natural-language local response
  would require a local LLM, which is out of this phase's scope.
- Sanitization (secret masking, PII redaction) remains regex-based and non-exhaustive — the
  same documented limitation `docs/security_boundaries.md` already states for the rest of the
  platform.

## Cost considerations

None today — no real API call is made, so there is no metered usage or cost to account for.
If real `send()` implementations are added in a future phase, `agent_timeout_seconds` and
`agent_max_retries` already exist as the configuration surface to bound worst-case latency and
retry cost, and `AGENT_MAX_CONTEXT_CHARS` bounds token usage per call.

## Optional live smoke-test instructions

**None exist.** Because no adapter makes a real outbound call, there is nothing to smoke-test
live — every test in `tests/unit/test_agent_*.py` and `tests/security/test_agent_no_secret_leakage.py`
uses mocks/fakes or the real (always-local-fallback) code path, and none requires network
access or a real API key. If a future phase implements a real `send()`, add a live smoke test
following the same pattern as `tests/integration/test_postgres_phase5_demo.py`: skipped by
default, gated on an explicit environment flag, and never given the mock banking repository or
any sensitive fixture content.
