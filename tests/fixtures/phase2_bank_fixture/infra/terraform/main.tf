# SYNTHETIC TEST FIXTURE — fake Terraform IAM policy, not real.
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
