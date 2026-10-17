# storage/db/

- `models/` — SQLAlchemy tables: scans, file inventory, domain mappings, findings, scanner executions, controls, evidence, recommendations, scores, control evaluations, audit events, users.
- `repositories.py` — persistence for scans, scoring, control evaluations, governance, and the append-only audit trail (`AuditRepository` has no update or delete).
- `session.py` — lazily created engine and session, plus a connectivity probe.

Schema changes go through Alembic (`alembic/versions/`); migrations run automatically when the Docker app starts. User accounts are handled by `auth/user_repository.py`.
