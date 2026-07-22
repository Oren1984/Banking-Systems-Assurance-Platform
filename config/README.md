# config/

## Structural note (deviation from the illustrative tree in Part C §2)

The unified typed settings model required by "Configuration Requirements" lives in
`core/config.py` (`core.config.Settings`), not in this directory. This follows
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §5.2's original approved architecture, which placed
`config.py` under `core/` alongside `contracts.py`/`exceptions.py`/`logging.py` as one of the
platform's shared primitives. Introducing a second, competing settings module here would
recreate exactly the "three separate configuration systems" duplication problem the audit
flagged in §4 — so this directory is intentionally not used for a second Settings class.

This directory is reserved for non-Python, environment-specific configuration assets (e.g.
per-deployment overrides, Prometheus/Grafana config once `observability/` is implemented) that
are not appropriate to hardcode into `core/config.py`. It is empty in Phase 1.

The root-level `.env.example` documents every environment variable `core.config.Settings`
reads.
