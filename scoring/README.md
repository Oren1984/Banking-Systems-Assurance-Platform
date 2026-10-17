# scoring/

- `engine.py` — per-domain raw and weighted scores, confidence, evidence completeness, and decision category (`insufficient_evidence` when there is not enough to judge).
- `recommendations.py` — advisory, template-based recommendations per finding. The platform never remediates anything.
