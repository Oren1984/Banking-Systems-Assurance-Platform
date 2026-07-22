from __future__ import annotations

# Importing every model module registers its table with
# storage.db.base.Base.metadata — required by alembic/env.py for
# autogeneration and by Base.metadata.create_all() in tests. This mirrors
# ai-project-control-tower/app/db/models/__init__.py's own
# "# noqa: F401 — registers all models with Base.metadata" pattern.

from storage.db.models.control import Control  # noqa: F401
from storage.db.models.domain_mapping import DomainMappingRecord  # noqa: F401
from storage.db.models.evidence import Evidence  # noqa: F401
from storage.db.models.file_inventory import FileInventoryRecord  # noqa: F401
from storage.db.models.finding import Finding  # noqa: F401
from storage.db.models.recommendation import Recommendation  # noqa: F401
from storage.db.models.scan import Scan  # noqa: F401
from storage.db.models.scanner_execution import ScannerExecutionRecord  # noqa: F401
from storage.db.models.score import Score  # noqa: F401

__all__ = [
    "Scan",
    "FileInventoryRecord",
    "DomainMappingRecord",
    "Finding",
    "ScannerExecutionRecord",
    "Control",
    "Evidence",
    "Recommendation",
    "Score",
]
