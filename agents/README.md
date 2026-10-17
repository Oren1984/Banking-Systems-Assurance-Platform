# agents/

The optional, advisory AI Assistant. Four actions — explain a finding, summarize a domain, answer a question about the evidence, write an executive summary — each built from a size-limited, sanitized context (`sanitizer.py`).

- `agent_service.py` — the four actions; falls back to local mode on any provider failure.
- `local_agent.py` — deterministic local mode (no network). This is the mode that runs today.
- `registry.py` — chooses local or external mode from configuration; external mode needs every opt-in flag *and* a provider key.
- `contracts.py`, `sanitizer.py` — request/response types, context limits, prompt-safety check.

The UI reaches this package only through `auth/secured_services.py::SecuredAgentService`, which checks permissions and records each action in the audit trail. Nothing here can change a finding, score, or review. See [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
