# Security Boundaries — Phase 1 + Phase 2 Snapshot

Full security/privacy/governance analysis and the consolidated findings table live in
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §10. This document tracks only what has actually been
implemented and its known limitations — it does not re-derive the audit.

## Read-only enforcement

`scanners/path_validator.py` fails closed (rejects everything) when `ALLOWED_SCAN_PATHS` is
unset — verified by `tests/unit/test_path_validator.py`. **Phase 2 closes the gap Phase 1
noted here:** `scanners/scan_orchestrator.py` now performs a full read-only scan and proves it
never wrote to the source, by hashing the entire source tree before and after every scan
(`scanners/file_discovery.py::compute_source_integrity_hash`) and refusing to report a scan as
successful if the hashes differ — verified by
`tests/security/test_scan_no_source_modification.py` and exercised on every scan via
`ScanSummary.integrity_verified`. No scanner ever opens a scanned file in write mode; only
`open(path, "rb")` (hashing) and text-mode reads are used (`scanners/content_reader.py`).

The three legacy repositories were verified byte-for-byte unmodified across both the Phase 1
and Phase 2 implementation sessions using a hash-comparison test
(`tests/e2e/test_original_repos_not_modified.py`), the same pattern as
`ai-project-control-tower/tests/e2e/test_no_repo_modification.py`.

## No code execution during scanning (Phase 2)

Every Phase 2 scanner (`scanners/rules/*.py`) is regex-based pattern matching against
already-decoded text — none of them import a code execution facility
(`eval`/`exec`/`pickle.load`/unsafe `yaml.load`) or a database driver, verified statically by
`tests/security/test_no_unsafe_deserialization.py` (AST-walks every `.py` file in the
platform's own code, not just a sample). `scanners/rules/sql_scanner.py` in particular detects
SQL injection/destructive-statement *patterns* — it never executes SQL; the same static test
verifies no `sqlite3`/`psycopg2`/`pymysql`/`pyodbc` import or `.execute()` call exists anywhere
under `scanners/rules/`. `tests/security/test_no_network_during_scan.py` monkeypatches
`socket.socket` to raise during a full scan run, proving no network call occurs.

## Archive ingestion safety (Phase 2)

`scanners/source_ingestion.py::ingest_zip_archive()` rejects, before extracting a single byte:
Zip Slip / path-traversal entries, absolute-path entries (both POSIX and Windows drive-letter
forms), symlink entries (via the Unix mode bits in a ZIP's `external_attr`), archives exceeding
`max_archive_entry_count` or `max_archive_uncompressed_bytes`, and any single entry whose
compression ratio exceeds `max_archive_compression_ratio` (a zip-bomb heuristic). Extraction
itself re-validates every resolved path stays inside the extraction root as defense in depth.
All extraction happens in an isolated temp directory (`Settings.scan_temp_dir`) that
`SourceHandle.cleanup()` removes after the scan — verified by
`tests/unit/test_source_ingestion.py` (11 tests) and
`tests/security/test_scan_no_source_modification.py::test_scanning_a_zip_archive_never_modifies_the_original_zip`.

## Secret handling

- `governance/secret_masker.py` — regex-based pattern coverage (AWS/GitHub/OpenAI/
  Anthropic/Google keys, JWTs, env-style `KEY=value` secrets, Bearer tokens). **Line-start
  anchored** for the env-style pattern — `PASSWORD=value` is caught,
  `SOME_PREFIX_PASSWORD=value` on the same line start is not (verified in
  `tests/security/test_secret_masker.py`). Banking-specific patterns (PANs, IBANs, routing
  numbers) are **not yet included** — this is a known gap, not a completeness claim.
- `governance/report_sanitizer.py` — re-masks secrets and strips auto-fix/patch-plan content
  from any report. This is the code-level enforcement of "recommend, never auto-fix."
- `core/config.py` rejects the specific insecure placeholder credential fragment found during
  the audit in `ai-project-control-tower/app/core/config.py:89`
  (`control_tower_pass`) — enforced by a `field_validator`, verified by
  `tests/unit/test_config_defaults.py::test_rejects_legacy_insecure_placeholder_credential`.
  No field in `core/config.py` carries any default credential, placeholder or otherwise.
- `.env.example` contains only empty placeholders; verified by
  `tests/security/test_env_example_no_real_secrets.py` to contain no real-looking secret
  patterns and to keep `EXTERNAL_PROVIDERS_ENABLED=false` / `LOCAL_ONLY_MODE=true`.
- **Phase 2 extensions to `governance/secret_masker.py`:** added an unanchored quoted-
  assignment pattern (catches `db_password = "..."` in code, not just `.env`-style lines) and a
  connection-string-credential pattern (`postgres://user:PASS@host` etc.), plus a new
  `find_secret_spans()` function that `scanners/rules/secret_scanner.py` reuses so detection
  and masking share one pattern set rather than two. `storage/db/models/finding.py` deliberately
  has **no raw-`evidence` column** — only `masked_evidence` is ever persisted; this is a
  structural (schema-level) guarantee, not just an application-level one, verified by
  `tests/unit/test_scan_repository.py::test_finding_row_has_no_raw_evidence_column`.
  `tests/security/test_no_secret_leakage_in_logs.py` verifies a full scan run never emits a
  raw secret value to the logging system.

## PII redaction — explicitly not complete

`governance/pii_redaction.py` is regex-based (email, phone-like sequences, long digit runs).
It does **not** detect names, addresses, or free-text account references. Do not present its
output as guaranteed PII-free in any context — see the module docstring and
`tests/security/test_pii_redaction.py::test_documented_as_non_exhaustive`.

## Prompt-injection defense — advisory only

`governance/prompt_safety.py::check_prompt_safety()` defaults to advisory (`enforce=False`):
it flags suspicious patterns but does not block a query. An `enforce=True` hard-gate mode
exists as an extension point but nothing in Phase 1 calls it that way yet (no LLM-facing
pipeline exists in Phase 1 to gate).

## External provider isolation

- `core.config.Settings.external_providers_enabled` defaults to `False`; per-provider flags
  (`openai_enabled`, `gemini_enabled`, `claude_enabled`) also default to `False`.
- `providers/registry.py::get_provider()` requires all three conditions (kill switch,
  per-provider flag, non-empty API key) before returning anything other than `None` — verified
  by `tests/unit/test_provider_registry.py`.
- `providers/{openai,gemini,claude}_adapter.py` fail fast at construction if given an empty
  key, never log the key (`__repr__` redacts it), and lazy-import the vendor SDK only inside
  `send()` (not implemented in Phase 1 — raises `NotImplementedError`). No provider SDK
  (`openai`, `anthropic`, `google-generativeai`) is installed or required for local startup —
  verified by `tests/isolation/test_no_sdk_required_for_local_startup.py`.
- `tests/isolation/test_no_network_imports_outside_providers.py` statically verifies that no
  module outside `providers/` imports a network-client library
  (`requests`, `httpx`, `openai`, `anthropic`, `google.generativeai`, etc.) anywhere in the
  new platform's own code.

## Access control — unresolved gap, unchanged from the audit

No authentication or authorization exists anywhere, consistent with all three audited
repositories and unchanged by Phase 2 (out of scope per the Phase 2 brief's explicit "Explicitly
Out of Scope" list). This remains an open question requiring a stakeholder decision on the
deployment model (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §16, open question #2).

## What this platform does not claim

This is not a claim of banking-grade security. It is a foundation with specific, tested
guarantees (listed above) and specific, documented gaps (PII completeness, prompt-injection
hard-gating, authentication, banking-specific secret patterns, non-exhaustive scanner pattern
coverage — see `docs/phase2_scanning_guide.md`). Do not represent any component here as
production-ready or regulation-compliant. Phase 2's PII/sensitive-data scanner in particular
is pattern-based detection only and is never a regulatory compliance determination — see each
finding's own `description` field, which states this explicitly.
