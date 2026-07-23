from __future__ import annotations

import json
from pathlib import Path

from core.domains import BankingDomain
from scripts.generate_knowledge_base_manifest import OUTPUT_PATH, build_manifest, render

# Phase 4 — knowledge_base/controls/domain_coverage.json is generated, not
# hand-authored. This test proves it can never silently drift from
# controls/catalog.py the way RAG-Engineering-Lab's testing_strategy.md
# drifted from its actual (nonexistent) tests
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §4/§10) — by regenerating it from
# the same code path the script uses and asserting a byte-for-byte match
# against the committed file.


def test_generated_manifest_matches_the_committed_file():
    expected = render(build_manifest())
    actual = Path(OUTPUT_PATH).read_text(encoding="utf-8")
    assert actual == expected, (
        "knowledge_base/controls/domain_coverage.json is out of date — "
        "run `python -m scripts.generate_knowledge_base_manifest` and commit the result"
    )


def test_manifest_covers_all_sixteen_domains():
    manifest = json.loads(Path(OUTPUT_PATH).read_text(encoding="utf-8"))
    assert manifest["domain_count"] == 16
    assert set(manifest["domains"].keys()) == {d.value for d in BankingDomain}


def test_every_domain_has_at_least_one_applicable_control():
    manifest = json.loads(Path(OUTPUT_PATH).read_text(encoding="utf-8"))
    for domain, entry in manifest["domains"].items():
        assert len(entry["applicable_control_ids"]) >= 1, f"{domain} has no applicable control"


def test_manifest_is_not_framed_as_a_regulatory_library():
    manifest = json.loads(Path(OUTPUT_PATH).read_text(encoding="utf-8"))
    assert "not a regulatory" in manifest["note"].lower()
