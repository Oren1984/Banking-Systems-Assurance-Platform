# governance/

Pure functions (no database access) used by the repositories and services:

- `approval_workflow.py` — validates finding reviews and score overrides; finalization policy (blocked while a high/critical-risk domain has pending findings).
- `audit_trail.py` — builds sanitized audit events (persisted only by `AuditRepository.record()`).
- `secret_masker.py`, `pii_redaction.py`, `report_sanitizer.py` — pattern-based masking; not exhaustive.
- `prompt_safety.py` — screens AI Assistant questions.
- `file_validation.py` — file type and size checks.
- `retention.py` — identifies scans older than `DATA_RETENTION_DAYS`; never deletes anything.
