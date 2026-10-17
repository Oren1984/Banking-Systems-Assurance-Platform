# scanners/

Read-only scanning of an allow-listed directory or ZIP archive.

- `path_validator.py`, `source_ingestion.py` — allow-list checks; ZIP extraction with path-traversal, entry-count, size, and compression-ratio limits.
- `file_discovery.py`, `file_classifier.py`, `content_reader.py` — find, classify, and read files (size and depth limits; symlinks skipped by default).
- `domain_mapper.py` — maps files to banking domains.
- `scan_orchestrator.py` — runs the scanners and hashes the source before and after (`integrity_verified`).
- `rules/` — secrets, PII, unsafe SQL, insecure configuration, broad permissions, audit gaps, unsafe logging, and a finding for skipped sensitive-looking files.
