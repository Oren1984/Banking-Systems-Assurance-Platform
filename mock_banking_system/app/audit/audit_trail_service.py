# SYNTHETIC MOCK BANKING SYSTEM — fake audit trail service, not real code.
# Deliberately planted finding — see docs/mock_banking_planted_findings.md.


def note_review(reviewer_comment):
    # Sparse audit note — no actor/timestamp/correlation_id nearby — expect AUDIT-003.
    return {"audit_note": reviewer_comment}
