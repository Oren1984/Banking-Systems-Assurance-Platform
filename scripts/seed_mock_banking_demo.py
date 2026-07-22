from __future__ import annotations

# Phase 1 documented interface placeholder for the mock-banking-system seed
# script (see BANKING_PLATFORM_INTEGRATION_PLAN.md Part A §10 of the
# approved plan revision). Actual seeding is scheduled for Phase 5.
#
# This placeholder deliberately does NOT create any synthetic data yet.
# Running it validates configuration and reports the actions it will take
# once implemented, so it is safe to run today and will remain safe to
# re-run once implemented (idempotent, per the Phase 5 requirements below).
#
# Phase 5 requirements this script must eventually satisfy:
#   - idempotent, safe to rerun
#   - deterministic where possible
#   - free of real secrets
#   - initializes sample controls, documents, findings, and assessment
#     targets under mock_banking_system/
#   - documented in README.md
#   - covered by tests

import sys

from core.config import Settings, get_settings
from core.domains import BankingDomain
from core.logging import get_logger

logger = get_logger(__name__)

PLANNED_ACTIONS = [
    "Validate LOCAL_ONLY_MODE and EXTERNAL_PROVIDERS_ENABLED are both safe for demo use.",
    "Create mock_banking_system/ synthetic controls across all 16 BankingDomain values.",
    "Create mock_banking_system/ synthetic policy documents for RAG ingestion.",
    "Create a mix of compliant / weak / missing / ambiguous / insufficient-evidence examples.",
    "Register one or more synthetic AssessmentTarget records.",
    "Run a full assessment against the mock system and persist sample findings/scores.",
    "Render a sample technical report and a sample executive report.",
]


def seed(settings: Settings | None = None) -> dict:
    """
    Phase 1 placeholder: validates configuration and returns the plan of
    action for Phase 5. Does not write any data.
    """
    s = settings or get_settings()

    logger.info(
        "seed_mock_banking_demo_placeholder_invoked",
        local_only_mode=s.local_only_mode,
        external_providers_enabled=s.external_providers_enabled,
        vector_backend=s.vector_backend,
    )

    return {
        "implemented": False,
        "scheduled_for": "Phase 5",
        "domain_count": len(BankingDomain),
        "planned_actions": PLANNED_ACTIONS,
    }


def main() -> int:
    result = seed()
    print("mock_banking_system seed script — Phase 1 placeholder (not yet implemented)")
    print(f"Scheduled for: {result['scheduled_for']}")
    print(f"Banking domains defined: {result['domain_count']}")
    print("Planned actions once implemented:")
    for action in result["planned_actions"]:
        print(f"  - {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
