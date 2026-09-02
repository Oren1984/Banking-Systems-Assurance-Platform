# SYNTHETIC REFERENCE BANKING SYSTEM — fake least-privilege access policy, not real code.
# Deliberate positive example: scoped IAM statement, no wildcard action or resource.

IAM_POLICY_EXAMPLE = {
    "Statement": [
        {
            "Action": ["s3:GetObject", "s3:PutObject"],
            "Resource": "arn:aws:s3:::reference-bank-reports/*",
            "Effect": "Allow",
        }
    ]
}
