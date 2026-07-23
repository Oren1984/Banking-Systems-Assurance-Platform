from __future__ import annotations

import json
from pathlib import Path

from assessment.evaluators.control_evaluator import domain_coverage_manifest
from controls.catalog import CONTROL_CATALOG, applies_to_domain
from core.domains import BankingDomain, get_domain_label

# Phase 4 — knowledge_base/controls/ manifest generator
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 4: "knowledge_base/
# controls/ structure across all 16 BankingDomain values"). This script
# regenerates knowledge_base/controls/domain_coverage.json from
# controls/catalog.py — the manifest is DATA, never hand-authored prose,
# so it can never drift from what the code actually evaluates.
# tests/unit/test_knowledge_base_manifest.py re-runs this same generation
# logic and asserts the committed file matches byte-for-byte, catching
# exactly the kind of docs-vs-reality gap
# BANKING_PLATFORM_INTEGRATION_PLAN.md §4/§10 flagged in the three legacy
# repositories (documented tests/behavior that did not match delivered
# code).
#
# NOT A REGULATORY CONTROL LIBRARY — see controls/catalog.py's own module
# docstring and BANKING_PLATFORM_INTEGRATION_PLAN.md §16 open question #4,
# which remains open. This manifest documents which of the 8 illustrative,
# engineering-derived technical controls apply to each of the 16 approved
# domains today — nothing more.

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "knowledge_base" / "controls" / "domain_coverage.json"

_DOMAIN_SPECIFIC_CONTROL_IDS = {c.control_id for c in CONTROL_CATALOG if c.domain is not None}


def build_manifest() -> dict:
    coverage = domain_coverage_manifest()
    domains = {}
    for domain in BankingDomain:
        control_ids = coverage[domain.value]
        domains[domain.value] = {
            "label": get_domain_label(domain),
            "applicable_control_ids": control_ids,
            "has_domain_specific_control": any(
                applies_to_domain(c, domain.value) and c.control_id in _DOMAIN_SPECIFIC_CONTROL_IDS
                for c in CONTROL_CATALOG
            ),
        }
    return {
        "generated_by": "scripts/generate_knowledge_base_manifest.py",
        "source_of_truth": "controls/catalog.py — this file is generated, never hand-edited",
        "note": (
            "Illustrative, engineering-derived technical control coverage per banking domain — "
            "not a regulatory or compliance control library. See "
            "BANKING_PLATFORM_INTEGRATION_PLAN.md §16 open question #4."
        ),
        "domain_count": len(domains),
        "domains": domains,
    }


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=False) + "\n"


def main() -> None:
    content = render(build_manifest())
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
