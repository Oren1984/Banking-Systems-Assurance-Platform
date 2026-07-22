# SYNTHETIC TEST FIXTURE — fake credit/lending approval logic, not real code.


def approve_loan(loan_id, approver_role):
    # Good practice example: audit call IS present, should NOT trigger AUDIT-002.
    audit_log("loan_approved", user=approver_role, action="approve_loan", loan_id=loan_id)
    return True


def grant_underwriter_access(user):
    role = "admin"  # broad permission indicator
    user.role = role
    return user


def audit_log(event, user, action, loan_id):
    return {"event": event, "user": user, "action": action, "loan_id": loan_id}
