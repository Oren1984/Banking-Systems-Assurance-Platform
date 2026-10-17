# Security

What is implemented today, and where it stops. Code references point to the enforcing module.

## Authentication

- Local accounts only, in the `users` table. There is no self-registration and no default account; the first admin is created from the command line (`scripts/create_admin.py`).
- Passwords are stored as salted scrypt hashes (N=2¹⁷, r=8, p=1, 16-byte random salt) using Python's standard library (`auth/password_hasher.py`). Comparison is constant-time.
- Password rules: at least 12 characters (configurable via `PASSWORD_MIN_LENGTH`), must not contain the username, and must not be trivially repetitive.
- Failed sign-ins get one generic message whether the account is unknown, the password is wrong, or the account is locked or deactivated. An unknown username still costs one hash computation, so timing does not reveal it either.
- **Lockout:** 5 consecutive failures lock the account for 15 minutes. A successful sign-in resets the counter, and an admin password reset clears the lockout.
- Admin-issued passwords are temporary. Until the user sets a new one, only the change-password page is reachable and every service call is refused.

## Sessions

- The signed-in identity is held in Streamlit's server-side session state. It contains no password or secret. A browser refresh starts a new session.
- Every page load and every protected action re-checks the session against the database (`auth/auth_service.py::validate_session`). The session ends if:
  - it has been idle longer than `SESSION_IDLE_TIMEOUT_MINUTES` (default 30);
  - the account was deactivated;
  - the account's role or password changed. Each `users.session_version` change invalidates older sessions.

## Authorization

The role-to-permission table in `auth/permissions.py` lists each role's permissions in full; no role inherits another's.

| Permission | Employee | Manager | Admin |
| --- | :-: | :-: | :-: |
| View assessments, findings, controls, comparisons, finalization status | ✓ | ✓ | ✓ |
| Run Full Assessment / Quick Scan | ✓ | ✓ | ✓ |
| Use the AI Assistant | ✓ | ✓ | ✓ |
| Review findings | — | ✓ | — |
| Override domain scores | — | ✓ | — |
| Export reports | — | ✓ | ✓ |
| View audit log | — | ✓ | ✓ |
| Manage users | — | — | ✓ |
| View system configuration | — | — | ✓ |

- **Enforcement point:** every UI action calls `auth/secured_services.py`. Each method runs `Authorizer.require()` (session check, then permission check) before delegating to the existing service code. Hiding pages and buttons in the UI is a convenience, not the control.
- **Navigation:** pages a role cannot use are not registered, so they cannot be opened by URL.
- **Identity in records:** reviewer and actor fields always come from the signed-in user. There is no field where a user can type a name.
- **Admin safeguards:** an admin cannot change their own role or status, the last active admin cannot be demoted or deactivated, and users are never deleted.

## Audit trail

- `audit_events` is append-only: the repository exposes only `record()` and reads. Free text and payloads pass through the report sanitizer before storage.
- **Recorded events:**
  - pipeline steps (actor `system`);
  - assessment and quick-scan requests;
  - finding reviews and score overrides;
  - AI Assistant actions;
  - report downloads;
  - sign-in, failed sign-in (with a reason code), lockout, sign-out, session expiry and invalidation;
  - user creation, role change, activation and deactivation, password reset and change;
  - every denied action.
- **Never recorded:** passwords, password hashes, or session data.
- Records made before authentication existed keep their original, self-typed reviewer names.

## Data handling

- Scanning is read-only. The source tree is hashed before and after every scan, and `integrity_verified` records the result.
- Only masked evidence is stored. Secret and PII masking is pattern-based (`governance/secret_masker.py`, `governance/pii_redaction.py`) and not exhaustive.
- ZIP sources are extracted into an isolated temp directory with path-traversal, entry-count, size, and compression-ratio limits.
- The bundled `mock_banking_system/` and `reference_banking_system/` are synthetic. Their "credentials" are planted fake values that exist to be detected — for example `mock_banking_system/config/db_schema_credentials.env`. They must never be replaced with real data.
- Error details are logged (sanitized) rather than shown in the UI, and Streamlit's own error details are disabled (`.streamlit/config.toml`).

## Network exposure

Docker publishes the UI (host port 8085, container port 8501) and PostgreSQL (5434) on `127.0.0.1` only. The UI uses plain HTTP and Streamlit's XSRF protection is on. **Before allowing access from any other computer or the internet**, put the app behind HTTPS (a TLS-terminating reverse proxy) and set a strong `POSTGRES_PASSWORD`.

## Known limitations

- No multi-factor authentication and no single sign-on.
- No TLS in this delivery; local use only.
- Database credentials come from the local `.env` file, not a secrets manager. The shipped placeholder `CHANGE_ME` must be replaced before first start.
- No production monitoring or alerting; status is limited to in-app indicators and container health checks.
- Detection rules are pattern-based. The platform supports a review; it does not certify compliance.
