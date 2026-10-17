from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, Optional

from models.enums import Role

# Role -> permission policy. One fixed, explicit table: every role lists
# its permissions in full, and no role inherits another's. In particular
# ADMIN is deliberately NOT a superset of MANAGER — separation of duties:
# an administrator manages accounts and can see everything, but cannot
# make governance decisions (finding review, score override). Changing
# this table is a policy change and must be reflected in README.md's
# role matrix and tests/unit/test_auth_permissions.py.


class Permission(str, Enum):
    VIEW_ASSESSMENTS = "view_assessments"
    RUN_ASSESSMENT = "run_assessment"
    RUN_QUICK_SCAN = "run_quick_scan"
    USE_AI_ASSISTANT = "use_ai_assistant"
    REVIEW_FINDINGS = "review_findings"
    OVERRIDE_SCORES = "override_scores"
    EXPORT_REPORTS = "export_reports"
    VIEW_AUDIT_LOG = "view_audit_log"
    MANAGE_USERS = "manage_users"
    VIEW_SYSTEM_INFO = "view_system_info"


ROLE_PERMISSIONS: Dict[Role, FrozenSet[Permission]] = {
    Role.EMPLOYEE: frozenset(
        {
            Permission.VIEW_ASSESSMENTS,
            Permission.RUN_ASSESSMENT,
            Permission.RUN_QUICK_SCAN,
            Permission.USE_AI_ASSISTANT,
        }
    ),
    Role.MANAGER: frozenset(
        {
            Permission.VIEW_ASSESSMENTS,
            Permission.RUN_ASSESSMENT,
            Permission.RUN_QUICK_SCAN,
            Permission.USE_AI_ASSISTANT,
            Permission.REVIEW_FINDINGS,
            Permission.OVERRIDE_SCORES,
            Permission.EXPORT_REPORTS,
            Permission.VIEW_AUDIT_LOG,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.VIEW_ASSESSMENTS,
            Permission.RUN_ASSESSMENT,
            Permission.RUN_QUICK_SCAN,
            Permission.USE_AI_ASSISTANT,
            Permission.EXPORT_REPORTS,
            Permission.VIEW_AUDIT_LOG,
            Permission.MANAGE_USERS,
            Permission.VIEW_SYSTEM_INFO,
        }
    ),
}


class AccessPolicy:
    """Answers "may this role do X?". Pure — no database, no session; the
    session/account-status checks live in auth/auth_service.py and both are
    applied together by auth/secured_services.py."""

    def __init__(self, table: Optional[Dict[Role, FrozenSet[Permission]]] = None) -> None:
        self._table = table if table is not None else ROLE_PERMISSIONS

    def permissions_for(self, role: Role) -> FrozenSet[Permission]:
        return self._table.get(role, frozenset())

    def can(self, role: Role, permission: Permission) -> bool:
        return permission in self.permissions_for(role)


__all__ = ["Permission", "ROLE_PERMISSIONS", "AccessPolicy"]
