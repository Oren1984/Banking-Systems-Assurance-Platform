# reporting/

## Phase 2 (implemented)

- `scan_report_exporter.py` — JSON, Markdown, and CSV export of a `scanners.scan_orchestrator.
  ScanResult` (the raw scan — findings only, no scoring/control-evaluation/governance data).
  Every free-text field is passed through `governance/report_sanitizer.py` (reused, not
  duplicated); only relative paths are ever included; findings only ever carry
  `masked_evidence`, never raw evidence — see `PHASE_2_COMPLETION_REPORT.md`.

## Phase 4 (implemented — see `PHASE_4_COMPLETION_REPORT.md`)

- `assessment_report_exporter.py` — `to_assessment_json()`/`to_assessment_markdown()`. The
  assessment-level report: domain scores, control-evaluation summary, recommendations,
  human-review status, and the audit trail — the parts of the platform's output that don't
  exist in a raw `ScanResult`. Carries five governance disclaimers on every export (not a
  regulatory certification; pending-review/finalization rule; advisory-only, never
  auto-applied; deterministic-only, no AI/LLM/RAG involvement as of Phase 5; overrides always
  logged with a mandatory justification).

## Phase 5 (implemented — see `PHASE_5_COMPLETION_REPORT.md`)

- `assessment_report_exporter.py::{to_findings_csv,to_scores_csv}` — CSV export, added
  alongside the existing JSON/Markdown functions.

Neither exporter is a Jinja2-templated report (the illustrative
`ai-project-control-tower/app/reports/report_generator.py` pattern originally referenced here)
— both build their output directly in Python, consistent with this project's preference for
explicit, inspectable code over a templating layer for a small, fixed set of output shapes.
