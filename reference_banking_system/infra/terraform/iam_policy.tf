# SYNTHETIC REFERENCE BANKING SYSTEM — fake least-privilege IAM policy, not real.
# Deliberate positive example: scoped resource, no wildcard action or resource.

resource "aws_iam_policy" "reference_reporting_readonly" {
  name = "reference-reporting-readonly"

  policy = jsonencode({
    Statement = [
      {
        Action   = ["s3:GetObject"]
        Resource = "arn:aws:s3:::reference-bank-reports/*"
        Effect   = "Allow"
      }
    ]
  })
}
