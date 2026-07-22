# scanners/

## Phase 1 (implemented)

- `path_validator.py` — allowlist-based, fail-closed scan-target path validation. Adapted
  from `ai-project-control-tower/app/scanner/path_validator.py`.

## Phase 2 (implemented — see `PHASE_2_COMPLETION_REPORT.md` and `docs/phase2_scanning_guide.md`)

- `source_ingestion.py` — safe local-directory + ZIP ingestion.
- `file_discovery.py` — recursive discovery with safety limits, hashing, source-integrity hash.
- `content_reader.py` — safe text reading.
- `file_classifier.py` — deterministic file/technology classification. (Net-new: no
  `ai-project-control-tower/app/scanner/file_classifier.py` existed in the delivered source
  repository to adapt from, despite the original Phase 1 placeholder note below expecting one.)
- `domain_mapper.py` — maps files to the 16 approved banking domains.
- `scan_orchestrator.py` — the full scan pipeline. This is where the originally-planned
  `repo_scanner.py`'s "read-only repository crawl" responsibility actually lives — it was not
  built as a separate file with that name; discovery, classification, and domain mapping are
  each their own module instead (see `docs/architecture.md` for the reasoning).
- `rules/` — the 8 Phase 2 content scanners plus the skipped-file scanner. See
  `docs/phase2_scanning_guide.md` for the full list.

Per the approved Phase 1 scope, no fake/stub implementation of the Phase 2 scanner modules was
provided ahead of Phase 2 — see `BANKING_PLATFORM_INTEGRATION_PLAN.md` Part C §2: "Do not
populate later-phase modules with fake implementations." That constraint no longer applies to
this directory now that Phase 2 is implemented.
