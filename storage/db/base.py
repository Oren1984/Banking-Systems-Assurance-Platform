from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

# Reused as-is from ai-project-control-tower/app/db/base.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3). No domain tables are declared
# against this Base yet — see storage/db/README.md for the migration
# boundary. Phase 3 ("Assessment, Evidence, and Scoring") introduces the
# first real models (models/control.py, models/finding.py, etc.).


class Base(DeclarativeBase):
    pass
