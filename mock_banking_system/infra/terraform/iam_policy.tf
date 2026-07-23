# SYNTHETIC MOCK BANKING SYSTEM — fake Terraform IAM policy, not real.
# Deliberately planted findings — see docs/mock_banking_planted_findings.md.
resource "fake_iam_policy" "overly_broad" {
  policy = jsonencode({
    Statement = [
      {
        "Action"   = "*"
        "Resource" = "*"
        "Effect"   = "Allow"
      }
    ]
  })
}
