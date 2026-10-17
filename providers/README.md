# providers/

Adapters for external AI providers (OpenAI, Gemini, Claude) behind the interface in `base.py`, selected by `registry.py`.

**Not implemented:** each adapter's `send()` raises `NotImplementedError`, and no provider SDK is listed in `requirements.txt`. If external mode is ever selected, `agents/agent_service.py` falls back to the local, deterministic mode. No data leaves the machine through this package.
