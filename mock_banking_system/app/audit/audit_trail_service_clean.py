# SYNTHETIC MOCK BANKING SYSTEM — fake audit trail service, not real code.
# Deliberate NEGATIVE example: includes actor/action/timestamp/correlation_id fields.
# Expect: no findings from this file.


def record_full_audit_event(actor, action, timestamp, correlation_id):
    return {
        "actor": actor,
        "action": action,
        "timestamp": timestamp,
        "correlation_id": correlation_id,
    }
