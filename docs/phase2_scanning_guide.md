# Phase 2 Scanning Guide

Covers what Phase 2 actually built: supported file types, safety limits, ignored paths,
scanner coverage, how to run a local scan, how to run the test suite, and how PostgreSQL
persistence behaves when no server is available. See `PHASE_2_COMPLETION_REPORT.md` for the
full verification record and `BANKING_PLATFORM_INTEGRATION_PLAN.md` for the target
architecture this phase implements a slice of.

## Supported file types

`scanners/file_discovery.py::SUPPORTED_TEXT_EXTENSIONS` and `SUPPORTED_TEXT_FILENAMES`:

Python (`.py`), JavaScript/JSX (`.js`, `.jsx`), TypeScript/TSX (`.ts`, `.tsx`), Java (`.java`),
C# (`.cs`), Go (`.go`), Shell (`.sh`, `.bash`), PowerShell (`.ps1`), SQL (`.sql`), JSON
(`.json`), YAML (`.yaml`, `.yml`), XML (`.xml`), TOML (`.toml`), INI/config (`.ini`, `.cfg`,
`.conf`), Markdown (`.md`), plain text (`.txt`), CSV (`.csv`), Terraform (`.tf`, `.tfvars`),
env files (`.env`), Java-style properties (`.properties`), plus filename-based matches for
`Dockerfile`, `docker-compose.yml`/`.yaml`, and `Makefile`.

Anything else is skipped with `SkipReason.UNSUPPORTED_TYPE` — not scanned, not an error. No
binary parsing of any kind is implemented; `scanners/content_reader.py` sniffs for a null byte
in the first 8KB and raises `BinaryContentError` rather than attempt to decode binary content
as text, as a second line of defense even for a file that passed the extension check.

## Safety limits (`core/config.py::Settings`)

| Limit | Setting | Default |
|---|---|---|
| Per-file size | `max_scan_file_size_bytes` | 1 MB |
| Total scan volume | `max_scan_total_size_bytes` | 200 MB |
| File count | `max_scan_file_count` | 20,000 |
| Directory depth | `max_scan_depth` | 40 |
| Symlinks | `scan_follow_symlinks` | `False` (skipped, never followed) |
| Archive entry count | `max_archive_entry_count` | 20,000 |
| Archive uncompressed size | `max_archive_uncompressed_bytes` | 200 MB |
| Archive compression ratio | `max_archive_compression_ratio` | 100x (zip-bomb heuristic) |

Exceeding a limit produces a recorded `SkippedFile` (file-level limits) or marks the scan
`completed_with_warnings` / raises `SourceIngestionError` before extraction begins
(archive-level limits) — see `scanners/source_ingestion.py` and `scanners/file_discovery.py`.

## Ignored paths

`scanners/file_discovery.py::DEFAULT_IGNORED_DIR_NAMES`: `.git`, `.github`, `node_modules`,
`venv`, `.venv`, `env`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `coverage`, `dist`,
`build`, `target`, `bin`, `obj`, `.idea`, `.vscode`, `.tox`, `.eggs`, `htmlcov`. Deliberately
does **not** ignore infrastructure/governance-relevant directories like `config/`, `deploy/`,
`ci/`, `.github/workflows/` (only `.github` itself is skipped as a dot-directory convention,
its `workflows/` YAML content is still discoverable once you're inside a repo that doesn't
nest it under a fully-ignored parent) — those are exactly the files several Phase 2 scanners
target.

## Scanner coverage (`scanners/rules/*.py`)

| Scanner | Category | Example detections |
|---|---|---|
| `secret_scanner.py` | `secret_exposure` | AWS/GitHub/OpenAI/Anthropic/Google keys, JWTs, quoted password/token/secret assignments, DB connection-string credentials (reuses `governance/secret_masker.py` — one detection implementation, not two) |
| `pii_scanner.py` | `pii_exposure` | Email, phone-shaped, card/account-number-shaped digit runs, national-ID-shaped patterns, date-of-birth fields, account/IBAN-labeled fields |
| `unsafe_logging_scanner.py` | `unsafe_logging` | A logging/print call whose arguments mention password/token/secret/cvv/card_number/ssn/account_number/auth_header/request_body/response_body |
| `audit_scanner.py` | `audit_gap` | Audit logging disabled in config; a sensitive-operation function (transfer/withdraw/approve/grant_access/...) with no audit call in the next 25 lines; an audit-labeled block missing standard fields (user/action/timestamp/correlation_id) |
| `permission_scanner.py` | `broad_permissions` | Wildcard IAM Action/Resource (JSON or HCL), admin-level role assignment, public/anonymous access flags, `chmod 777` |
| `sql_scanner.py` | `unsafe_sql` | String-concatenated SQL, f-string SQL, %-format SQL, `DROP TABLE`/`DROP DATABASE`/`TRUNCATE TABLE`, plaintext DB credential |
| `insecure_config_scanner.py` | `insecure_configuration` | Debug mode, TLS verification disabled, auth/encryption disabled, permissive CORS, public bind (`0.0.0.0`), default weak credentials, verbose error exposure, cookies without `Secure` |
| `unsupported_file_scanner.py` | `unsupported_sensitive_file` | A *skipped* file (unsupported type, size limit, symlink, unreadable) whose name looks sensitive — not every skipped file, only sensitive-looking ones |

Every finding carries `finding_type` (`observed_evidence` vs. `inference`), `severity`,
`confidence`, `masked_evidence` (never the raw match), `rule_id`, and
`remediation_mode="advisory_only"` — see `scanners/rules/base.py::RawFinding` and
`storage/db/models/finding.py`.

## Running a local scan

Programmatically (what `ui/streamlit_app.py` does):

```python
from core.config import get_settings
from scanners.source_ingestion import ingest_local_directory
from scanners.scan_orchestrator import run_scan
from reporting.scan_report_exporter import to_json, to_markdown

settings = get_settings()  # requires ALLOWED_SCAN_PATHS to include your target
handle = ingest_local_directory(r"C:\path\to\project", settings)
try:
    result = run_scan(handle, settings)
finally:
    handle.cleanup()

print(to_markdown(result))
```

Through the UI:

```bash
streamlit run ui/streamlit_app.py
```

Then select a local directory or ZIP archive under an `ALLOWED_SCAN_PATHS` entry, start the
scan, review findings, filter by severity/domain/category/path/scanner, and export.

## Running the tests

```bash
pytest                                    # everything except the live-Postgres suite (auto-skipped without DATABASE_URL)
DATABASE_URL=postgresql://user:pass@localhost:5434/db pytest tests/integration/test_postgres_persistence.py
```

No test requires network access or an external AI provider SDK. The synthetic fixture at
`tests/fixtures/phase2_bank_fixture/` (see its own `README.md`) is used by the full-scan
integration tests — it is fake data, safe to scan repeatedly.

## PostgreSQL persistence when no server is available

`storage/db/repositories.py::ScanRepository` requires a live `Session` — nothing in
`scanners/scan_orchestrator.py` requires a database at all (`run_scan()` returns an in-memory
`ScanResult` regardless of whether persistence ever happens). If `DATABASE_URL` is unset or a
server is unreachable:

- `run_scan()` still works fully — scanning, classification, domain mapping, and report export
  are all independent of persistence.
- `storage.db.session.get_engine()` raises a clear `ConfigurationError` (not a crash) if
  `DATABASE_URL` is unset.
- `ScanRepository.save()` will raise whatever SQLAlchemy/psycopg2 connection error occurs if
  given a session bound to an unreachable database — this is a genuine failure the caller must
  handle, not silently swallowed (per the Phase 2 brief's "No silent fallback may hide
  database failures").
- `tests/integration/test_postgres_persistence.py` is skipped (not failed, not silently
  passed) when `DATABASE_URL` is unset — its skip reason states exactly why.
