<!-- SYNTHETIC REFERENCE BANKING SYSTEM — fake model-governance documentation, not real. -->
<!-- Deliberate positive example: this domain is evaluated here, unlike mock_banking_system/,
     where model_ai_governance is deliberately left unevaluated (see that fixture's README). -->

# Credit Risk Scoring Model — Governance Summary

- Review cadence: quarterly, by the model risk committee.
- Monitoring: prediction drift and feature-distribution checks run on every scoring batch.
- Approval: a named model owner signs off on every retraining before deployment.
- Documentation: model card and validation report are stored with the deployment record.
