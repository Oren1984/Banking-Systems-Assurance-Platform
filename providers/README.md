# providers/

## Phase 1 (scaffolded) → Phase 6 (finalized — see `PHASE_6_COMPLETION_REPORT.md`)

The low-level, per-provider adapter layer for OpenAI, Google Gemini, and Anthropic Claude.
Disabled by default and never required for local-only startup or the core assessment workflow
— see `tests/isolation/test_no_sdk_required_for_local_startup.py` and
`tests/isolation/test_no_network_imports_outside_providers.py` (this is the **only** directory
in the platform allowed to import a network-client library; none of the three adapters
actually do, since none makes a real call — see below).

| Module | Contents |
|---|---|
| `base.py` | `ProviderAdapter` (ABC: `is_available()`, `send()`, `provider_name`), `ProviderRequest`/`ProviderResponse` |
| `registry.py` | `get_provider(name, settings)` — the three-condition activation rule: the platform-wide `EXTERNAL_PROVIDERS_ENABLED` kill switch, the specific provider's own `{name}_enabled` flag, and a non-empty `{name}_api_key` must **all** hold, or `None` is returned. Never raises. |
| `openai_adapter.py`, `gemini_adapter.py`, `claude_adapter.py` | Fail-fast-at-construction (a missing API key raises `ProviderDisabledError` immediately, never a later silent failure), never-log-key (`__repr__` redacts it), configuration-ready (`model`, `timeout_seconds`, `max_retries` are accepted, stored, and used to build the audit metadata `agents/agent_service.py` records — never silently ignored). |

## Why `send()` still only raises `NotImplementedError`

This is a deliberate Phase 6 scope boundary, not an oversight or a missed deadline. No adapter
imports `httpx`, `requests`, or a vendor SDK (`openai`, `anthropic`, `google-generativeai`) —
lazily or otherwise. Implementing a real outbound call would require this codebase to depend on
live, paid, non-deterministic external infrastructure for a project whose entire premise is a
deterministic, local-first assessment core; `agents/agent_service.py` already treats this
exception as an ordinary, expected provider-failure case and falls back to the local,
deterministic agent mode — see `agents/README.md` and `docs/agent_guide.md`.

## Never installed, never required

`openai`, `anthropic`, and `google-generativeai` are not in `requirements.txt` and are not
installed in this environment — verified by
`tests/isolation/test_no_sdk_required_for_local_startup.py::test_provider_sdks_are_not_installed_in_this_environment`,
unchanged since Phase 1. The entire assessment workflow (scanning, evidence, scoring, control
evaluation, governance review, overrides, finalization, reporting, traceability, and even the
optional agent boundary's *local* mode) runs with zero API keys and zero provider SDKs
installed.
