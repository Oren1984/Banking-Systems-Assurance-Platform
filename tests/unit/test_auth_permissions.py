from __future__ import annotations

from auth.permissions import ROLE_PERMISSIONS, AccessPolicy, Permission
from models.enums import Role

P = Permission

# The approved role matrix, written out in full. If this test fails, the
# policy changed — update README.md's role table in the same change.
EXPECTED = {
    Role.EMPLOYEE: {P.VIEW_ASSESSMENTS, P.RUN_ASSESSMENT, P.RUN_QUICK_SCAN, P.USE_AI_ASSISTANT},
    Role.MANAGER: {
        P.VIEW_ASSESSMENTS,
        P.RUN_ASSESSMENT,
        P.RUN_QUICK_SCAN,
        P.USE_AI_ASSISTANT,
        P.REVIEW_FINDINGS,
        P.OVERRIDE_SCORES,
        P.EXPORT_REPORTS,
        P.VIEW_AUDIT_LOG,
    },
    Role.ADMIN: {
        P.VIEW_ASSESSMENTS,
        P.RUN_ASSESSMENT,
        P.RUN_QUICK_SCAN,
        P.USE_AI_ASSISTANT,
        P.EXPORT_REPORTS,
        P.VIEW_AUDIT_LOG,
        P.MANAGE_USERS,
        P.VIEW_SYSTEM_INFO,
    },
}


def test_role_matrix_matches_the_approved_policy_exactly():
    assert {role: set(perms) for role, perms in ROLE_PERMISSIONS.items()} == EXPECTED


def test_admin_does_not_inherit_manager_governance_permissions():
    policy = AccessPolicy()
    assert not policy.can(Role.ADMIN, P.REVIEW_FINDINGS)
    assert not policy.can(Role.ADMIN, P.OVERRIDE_SCORES)
    assert not ROLE_PERMISSIONS[Role.MANAGER] <= ROLE_PERMISSIONS[Role.ADMIN]


def test_only_manager_can_make_governance_decisions():
    policy = AccessPolicy()
    for perm in (P.REVIEW_FINDINGS, P.OVERRIDE_SCORES):
        assert [r for r in Role if policy.can(r, perm)] == [Role.MANAGER]


def test_only_admin_can_manage_users():
    policy = AccessPolicy()
    assert [r for r in Role if policy.can(r, P.MANAGE_USERS)] == [Role.ADMIN]


def test_export_and_audit_log_are_manager_and_admin_only():
    policy = AccessPolicy()
    for perm in (P.EXPORT_REPORTS, P.VIEW_AUDIT_LOG):
        assert {r for r in Role if policy.can(r, perm)} == {Role.MANAGER, Role.ADMIN}


def test_employee_may_run_assessments_but_not_decide():
    policy = AccessPolicy()
    assert policy.can(Role.EMPLOYEE, P.RUN_ASSESSMENT)
    assert policy.can(Role.EMPLOYEE, P.RUN_QUICK_SCAN)
    assert not policy.can(Role.EMPLOYEE, P.REVIEW_FINDINGS)
    assert not policy.can(Role.EMPLOYEE, P.OVERRIDE_SCORES)


def test_every_role_has_an_entry():
    assert set(ROLE_PERMISSIONS) == set(Role)
