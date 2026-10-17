# assessment/

- `engine.py` — `run_assessment()` runs the full pipeline for one source (ingest, scan, persist, score, evaluate controls, audit); `load_assessment_result()` reassembles a stored assessment with SELECT queries only.
- `evaluators/control_evaluator.py` — evaluates each catalog control per domain against the findings.
- `traceability.py` — links a finding to its controls, evidence, domain scores, and recommendations.
