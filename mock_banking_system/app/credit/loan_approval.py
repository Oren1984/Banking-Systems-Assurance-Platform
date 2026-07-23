# SYNTHETIC MOCK BANKING SYSTEM — fake credit/lending approval logic, not real code.
# Deliberate NEGATIVE example: audit call IS present on a sensitive operation.
# Expect: no AUDIT-002 finding from this file.


def approve_loan(loan_id, approver_role):
    audit_log("loan_approved", user=approver_role, action="approve_loan", loan_id=loan_id)
    return True


def audit_log(event, user, action, loan_id):
    return {"event": event, "user": user, "action": action, "loan_id": loan_id}
