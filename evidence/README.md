# evidence/

## Phase 3 (implemented — see `PHASE_3_COMPLETION_REPORT.md`)

- `capture.py` — `build_evidence()`. Pure function, no database: turns an already-masked
  `Finding.masked_evidence` value into an `EvidenceResult` (human-readable `source_reference`
  — `path:line` or `path:start-end` — plus `evidence_type=SCAN_RESULT`, the only evidence
  source that exists as of Phase 5; no RAG-retrieved or manually-uploaded evidence source
  exists yet). Never receives raw evidence — only the caller
  (`storage/db/repositories.py::ScoringRepository`) ever passes
  `Finding.masked_evidence`, which is guaranteed sanitized by construction (see
  `storage/db/models/finding.py`'s module docstring).

`storage/db/models/evidence.py::Evidence` is the persisted form — `control_id` links each row
to the `controls/catalog.py` control it supports, when one matched.
