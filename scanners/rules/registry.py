from __future__ import annotations

from typing import List

from scanners.rules.audit_scanner import AuditGapScanner
from scanners.rules.base import BaseScanner
from scanners.rules.insecure_config_scanner import InsecureConfigurationScanner
from scanners.rules.permission_scanner import BroadPermissionScanner
from scanners.rules.pii_scanner import PiiExposureScanner
from scanners.rules.secret_scanner import SecretExposureScanner
from scanners.rules.sql_scanner import UnsafeSqlScanner
from scanners.rules.unsafe_logging_scanner import UnsafeLoggingScanner

# scanners/rules/unsupported_file_scanner.py is intentionally not included
# here — it operates on the skipped-file list, not on content, and is
# invoked directly by scanners/scan_orchestrator.py. See that module's
# docstring for why it does not implement BaseScanner.


def get_content_scanners() -> List[BaseScanner]:
    """All Phase 2 scanners that run against already-read file text.
    A fresh instance is returned each call since scanners are stateless."""
    return [
        SecretExposureScanner(),
        PiiExposureScanner(),
        UnsafeLoggingScanner(),
        AuditGapScanner(),
        BroadPermissionScanner(),
        UnsafeSqlScanner(),
        InsecureConfigurationScanner(),
    ]
