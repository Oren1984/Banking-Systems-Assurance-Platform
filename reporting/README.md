# reporting/

## Phase 2 (implemented)

- `scan_report_exporter.py` — JSON, Markdown, and CSV export of a `scanners.scan_orchestrator.
  ScanResult`. Every free-text field is passed through `governance/report_sanitizer.py` (reused,
  not duplicated); only relative paths are ever included; findings only ever carry
  `masked_evidence`, never raw evidence — see `PHASE_2_COMPLETION_REPORT.md`.

## Phase 5 (planned — Governance Workflow, Audit Trail, Reporting)

Full assessment/control-evaluation reporting — adapted from
`ai-project-control-tower/app/reports/report_generator.py` and its Jinja2 templates. Not yet
implemented; this is a different, later report (assessment findings against a control library),
not the Phase 2 scan report above.
