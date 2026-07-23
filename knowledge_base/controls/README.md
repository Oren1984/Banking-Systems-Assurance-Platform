# knowledge_base/controls/

Phase 4 (`BANKING_PLATFORM_INTEGRATION_PLAN.md` §13: "knowledge_base/controls/ structure across
all 16 BankingDomain values"). This directory holds `domain_coverage.json` — a **generated**
manifest, not hand-authored prose — mapping each of the 16 approved `core.domains.BankingDomain`
values to the `controls/catalog.py` control IDs that apply to it.

## What this is

A machine-generated cross-reference: for each domain, which of the 8 illustrative technical
controls apply (`applicable_control_ids`) and whether the domain has a control specific to it
beyond the four cross-cutting ones (`has_domain_specific_control`). Regenerate it with:

```
python -m scripts.generate_knowledge_base_manifest
```

`tests/unit/test_knowledge_base_manifest.py` re-runs the same generation logic the script uses
and asserts the committed file matches byte-for-byte — this manifest can never silently drift
from `controls/catalog.py` the way `RAG-Engineering-Lab/docs/testing_strategy.md` drifted from
its actual (nonexistent) tests (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §4/§10).

## What this is not

**Not a banking regulatory or compliance control library.** Every control referenced here is an
engineering-derived technical check tied 1:1 to a Phase 2 deterministic scanner
(`scanners/rules/*.py`) — e.g. "no hardcoded secrets" — not a citation to any specific banking
regulation, standard, or internal policy document. Authoring a real regulatory control library
per domain requires banking/compliance domain expertise outside this engineering phase's scope.
This remains **open question #4** in `BANKING_PLATFORM_INTEGRATION_PLAN.md` §16 — still
unresolved after Phase 4.

## Why every domain already has coverage

Four of the eight catalog controls (`CTRL-SECRET-001`, `CTRL-PII-001`, `CTRL-LOG-001`,
`CTRL-SKIP-001`) are cross-cutting — they apply to every domain, per
`controls/catalog.py::applies_to_domain()`'s documented precedence. The remaining four are
domain-specific (`CTRL-AUDIT-001` → `human_approval_auditability`, `CTRL-PERM-001` →
`application_security`, `CTRL-SQL-001` → `database_controls_sod`, `CTRL-CFG-001` →
`infrastructure_api_security`). The practical result: every one of the 16 approved domains has
at least the 4 cross-cutting controls applicable to it today, and 4 domains additionally have
one domain-specific control — verified by `tests/unit/test_knowledge_base_manifest.py`.
