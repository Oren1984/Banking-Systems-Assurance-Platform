# Verification

## How to verify

```powershell
python -m pytest -q -rs                       # full suite; PostgreSQL-only tests skip without DATABASE_URL
```

The settings loader also reads the root `.env`. On a machine where `.env` points at your real database, move it aside while running tests (`Move-Item .env .env.hold`, then back), so no test can reach that database. CI has no `.env`.

PostgreSQL-backed tests run against a **disposable** database (never one whose data you need):

```powershell
$env:DATABASE_URL = "postgresql://<user>:<password>@localhost:5434/<disposable_db>"
alembic upgrade head
# the persistence tests expect the pgvector extension to exist already:
#   CREATE EXTENSION IF NOT EXISTS vector;   (run once in that database)
python -m pytest -q tests/integration

# migration upgrade + rollback check against a disposable PostgreSQL database
$env:AUTH_MIGRATION_TEST_DATABASE_URL = "postgresql://<user>:<password>@localhost:5434/<another_disposable_db>"
python -m pytest -q tests/integration/test_auth_migration.py
```

Main test areas: `tests/unit/test_auth_*.py`, `test_password_hasher.py`, `test_user_admin_service.py`, `test_secured_services.py` (direct service calls for every role), `test_scan_comparison.py`, `test_streamlit_app_smoke.py` (headless UI for every role), `tests/security/` (masking, read-only scanning, localhost-only ports, no `.env` in the repository), and `tests/integration/`.

CI: `.github/workflows/tests.yml` runs `python -m pytest -q -rs` on Python 3.11 without Docker or a database. **No remote CI run has been observed yet.**

## Record of checks (2026-10-17, Windows 11, Python 3.12 host, Docker 29.8)

### Passed

| Check | Result |
| --- | --- |
| Full test suite (local, no live database) | 587 passed, 0 failed, 16 skipped |
| PostgreSQL integration tests on a fresh, migrated disposable database | 30 passed |
| Auth migration upgrade → re-run → downgrade on disposable PostgreSQL and SQLite | Passed; existing rows unchanged; only `users` added and removed |
| Upgrade of a populated pre-auth database (version `15cfd06` in Docker → current code on the same volume) | Migration `a14a5514b9ab → 0004_auth_users` applied on start; content checksums of all 9 existing tables identical before and after |
| Docker build and health | `app` and `db` healthy; migrations ran on start |
| Localhost-only exposure | 8085 (app) and 5434 (db) answer on `127.0.0.1`; refused on the Wi-Fi and WSL interfaces |
| First admin via `create_admin --credentials-file -` (stdin, from bash and from PowerShell `Get-Content`) | Account created; re-run left it unchanged; `admin.credentials` absent from the image |
| Demo users via `seed_demo_users` | Refused without `--demo`; created 3 accounts with `--demo` |
| Browser walkthrough (Chrome, against Docker) | Employee: sign-in, Full Assessment (42 findings / 16 domains / 68 control evaluations / 5 audit events), read-only Review Queue, sign-out. Manager: generic failed-sign-in message, finding approval (42 → 41 pending, attributed to the user), comparison (1 new, 41 unchanged). Admin: Users page, read-only Review Queue, Audit Log |
| Audit content | No passwords or hashes in any audit summary or payload; every event carries the authenticated actor |
| Local run outside Docker | `python -m streamlit run ui/app.py` renders the sign-in page |
| Documentation | Relative links and image paths in all maintained Markdown files resolve; the README Mermaid diagram renders with Mermaid 10.9.1; no credentials or personal email addresses in the docs |
| Docker startup fix (Compose project `deployment`, existing July volume) | Both containers healthy; app published as `127.0.0.1:8085->8501`; `/_stcore/health` and `/` return 200 on <http://localhost:8085>; sign-in page renders and an admin sign-in shows the existing assessments; migration `a14a5514b9ab → 0004_auth_users` applied; 10 scans / 254 findings / 44 audit events unchanged; `docker compose exec` scripts reach `db:5432` |

### Found and fixed during verification

- Docker UI unreachable: the app's `DATABASE_URL` was built by Compose interpolation, which never reads the root `.env`, so the app used a different password than the existing database volume and stopped after 30 retries before Streamlit started. Both containers now read the same `.env`, the app derives its connection from it, and a credential mismatch is reported immediately with a clear message. Host port moved to 8085.
- Header "Sign out" button truncated; admin pages hidden behind Streamlit's "View 4 more"; metric values truncated ("Bloc…"). Fixed and re-checked in the browser.
- The bare `streamlit run ui/app.py` (outside Docker) fails with `No module named 'ui'`. Documented `python -m streamlit run` instead, which works.

### Skipped

- 12 PostgreSQL tests in the local run (no `DATABASE_URL`). They passed separately against a disposable database, as listed above.
- 3 legacy-repository immutability tests: the gitlinked repositories are not checked out in this clone.
- 1 symlink test: creating symlinks is not permitted on this Windows account.

### Not run or inconclusive

- Remote GitHub Actions run: not observed.
- Interactive `create_admin` through a terminal TTY: only the piped-stdin path was exercised.
- Narrow (mobile-width) layout: the browser tool could not shrink the viewport, so it was not verified visually.

## Feature parity with the retired single-page UI

| Former capability | Now |
| --- | --- |
| Status banner (mode, local-only, providers, vector backend, database) | Header badges on every page |
| Help / System Information panel | Help & About page; System page (Admin) |
| Full Assessment from 4 source types | Run & History |
| Load an existing scan; summary metrics; domain scores with history | Sidebar "Active assessment"; Run & History |
| Findings with filters, evidence, traceability | Findings |
| Control evaluations | Controls |
| Finalization status, finding review, score override | Review Queue (decisions: Manager only) |
| Per-scan audit trail | Review Queue tab (Manager, Admin); Audit Log page |
| JSON / Markdown / CSV exports | Reports (Manager, Admin) |
| AI Assistant (4 actions) | AI Assistant |
| Quick Scan without a database | Quick Scan — now requires sign-in, so the database must be configured |
