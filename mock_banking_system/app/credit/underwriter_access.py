# SYNTHETIC MOCK BANKING SYSTEM — fake credit/lending access assignment, not real code.
# Deliberately planted finding — see docs/mock_banking_planted_findings.md.


def grant_underwriter_access(user):
    role = "admin"  # expect PERM-003 (administrator-level role assignment)
    user.role = role
    return user
