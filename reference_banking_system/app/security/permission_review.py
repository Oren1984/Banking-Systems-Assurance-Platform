# SYNTHETIC REFERENCE BANKING SYSTEM — fake role assignment review, not real code.
# Deliberate positive example: scoped, non-administrator role assignment.


def assign_role(user_id, role_name):
    if role_name not in ("loan_officer", "teller", "risk_officer_readonly"):
        raise ValueError("unknown role")
    return {"user_id": user_id, "role": role_name}
