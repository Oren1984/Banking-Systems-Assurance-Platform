# SYNTHETIC MOCK BANKING SYSTEM — fake application-security access-control policy, not real code.
# Deliberately planted findings — see docs/mock_banking_planted_findings.md.

IAM_POLICY_EXAMPLE = {
    "Statement": [
        {"Action": "*", "Resource": "*", "Effect": "Allow"}  # expect PERM-001 (CRITICAL) and PERM-002 (HIGH)
    ]
}
