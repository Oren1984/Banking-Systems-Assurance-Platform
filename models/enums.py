from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """How serious an identified problem is. Reused from
    ai-project-control-tower/app/audit/models.py::Severity (already a
    clean, minimal enum — see BANKING_PLATFORM_INTEGRATION_PLAN.md §9)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ConfidenceLevel(str, Enum):
    """How certain the platform is about a finding. Net-new: neither
    existing scoring engine audited (ai-project-control-tower,
    AI-Project-Scope-Guard) distinguished confidence from severity — see
    BANKING_PLATFORM_INTEGRATION_PLAN.md §1 and Executive Summary."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceCompleteness(str, Enum):
    """Whether enough evidence was available to evaluate a control.

    The platform must never treat lack of evidence as a successful
    control: `INSUFFICIENT` is a first-class outcome, not an error state,
    and must never silently collapse into a passing score."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class HumanReviewStatus(str, Enum):
    """Whether a qualified reviewer confirmed, rejected, or overrode a
    finding or score. No report may be marked final while a required
    review remains `PENDING`."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"


class DecisionCategory(str, Enum):
    """Required decision categories (BANKING_PLATFORM_INTEGRATION_PLAN.md
    Part A §9 / §11 `Score.decision_category`)."""

    ACCEPTABLE = "acceptable"
    ACCEPTABLE_WITH_OBSERVATIONS = "acceptable_with_observations"
    REMEDIATION_REQUIRED = "remediation_required"
    HIGH_RISK = "high_risk"
    CRITICAL_RISK = "critical_risk"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class ControlType(str, Enum):
    """Explicit separation required between technical controls, internal
    policies, architecture standards, business rules, and regulatory
    references (BANKING_PLATFORM_INTEGRATION_PLAN.md §9). The platform must
    never claim regulatory compliance from automated checks alone."""

    TECHNICAL = "technical"
    INTERNAL_POLICY = "internal_policy"
    ARCHITECTURE_STANDARD = "architecture_standard"
    BUSINESS_RULE = "business_rule"
    REGULATORY_REFERENCE = "regulatory_reference"


# ---------------------------------------------------------------------------
# Phase 2 additions (scanning/ingestion pipeline). Added here — not in a
# second enums module — per the Phase 1 rule that this file is the single
# home for platform-wide vocabulary enums.
# ---------------------------------------------------------------------------


class ScanStatus(str, Enum):
    """Lifecycle state of a scan run (scanners/scan_orchestrator.py)."""

    PENDING = "pending"
    VALIDATING = "validating"
    SCANNING = "scanning"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SkipReason(str, Enum):
    """Why a discovered file was not scanned (scanners/file_discovery.py)."""

    SIZE_LIMIT = "size_limit"
    TOTAL_SIZE_LIMIT = "total_size_limit"
    DEPTH_LIMIT = "depth_limit"
    COUNT_LIMIT = "count_limit"
    SYMLINK = "symlink"
    BINARY_UNSUPPORTED = "binary_unsupported"
    UNREADABLE = "unreadable"
    IGNORED_PATH = "ignored_path"
    UNSUPPORTED_TYPE = "unsupported_type"


class FindingCategory(str, Enum):
    """The Phase 2 scanner categories (BANKING_PLATFORM_INTEGRATION_PLAN.md
    Phase 2 brief, §6.A-H)."""

    SECRET_EXPOSURE = "secret_exposure"
    PII_EXPOSURE = "pii_exposure"
    UNSAFE_LOGGING = "unsafe_logging"
    AUDIT_GAP = "audit_gap"
    BROAD_PERMISSIONS = "broad_permissions"
    UNSAFE_SQL = "unsafe_sql"
    INSECURE_CONFIGURATION = "insecure_configuration"
    UNSUPPORTED_SENSITIVE_FILE = "unsupported_sensitive_file"


class FindingType(str, Enum):
    """Whether a finding states directly observed evidence (e.g. a regex
    matched this exact text) or a lower-certainty inference drawn from
    surrounding context. Findings must not blur this distinction."""

    OBSERVED_EVIDENCE = "observed_evidence"
    INFERENCE = "inference"


class RemediationMode(str, Enum):
    """Every finding's remediation mode. Exactly one value exists on
    purpose: the platform recommends, it never applies a fix. Modeling
    this as an enum (rather than a free-text field or an implicit
    assumption) makes "advisory only" a machine-checkable invariant —
    see governance/report_sanitizer.py, which already strips any
    auto-fix/patch-plan content that manages to reach a report."""

    ADVISORY_ONLY = "advisory_only"


class MappingSource(str, Enum):
    """What kind of evidence a domain mapping (scanners/domain_mapper.py)
    was derived from."""

    FILE_PATH = "file_path"
    FILE_NAME = "file_name"
    DIRECTORY_NAME = "directory_name"
    CONFIG_KEY = "config_key"
    SCHEMA_NAME = "schema_name"
    TABLE_NAME = "table_name"
    API_PATH = "api_path"
    BANKING_TERMINOLOGY = "banking_terminology"
    SCANNER_RESULT = "scanner_result"


# ---------------------------------------------------------------------------
# Phase 3 additions (controls/evidence/scoring/recommendations). Added here
# for the same reason the Phase 2 enums were added here, not in a second
# file: this module is the single home for platform-wide vocabulary.
# ---------------------------------------------------------------------------


class EvidenceType(str, Enum):
    """What kind of material an Evidence row captures
    (BANKING_PLATFORM_INTEGRATION_PLAN.md §11)."""

    FILE_EXCERPT = "file_excerpt"
    CONFIG_VALUE = "config_value"
    SCAN_RESULT = "scan_result"
    RETRIEVED_CHUNK = "retrieved_chunk"


class RecommendationStatus(str, Enum):
    """Lifecycle of a Recommendation (BANKING_PLATFORM_INTEGRATION_PLAN.md
    §11) — deliberately a different vocabulary from HumanReviewStatus:
    a recommendation is *acted on* (accepted/deferred/rejected), a finding
    is *reviewed* (approved/rejected/overridden). Conflating the two would
    blur "do we agree this is a real issue" with "what are we doing about
    it"."""

    OPEN = "open"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class RecommendationSource(str, Enum):
    """Who/what generated a recommendation's text. Exactly one value
    exists today — Phase 3 has no AI/LLM component, so every
    recommendation is deterministic-template output. This mirrors
    RemediationMode's one-member-today design: an explicit, checkable
    field now, an extension point for Phase 6 (`llm:<provider>` values)
    later — never an implicit assumption."""

    DETERMINISTIC_TEMPLATE = "deterministic_template"


# ---------------------------------------------------------------------------
# Phase 4 additions (assessment orchestration, control evaluation, audit
# trail, human-in-the-loop governance). Appended here for the same reason
# the Phase 2 and Phase 3 additions were — this module is the single home
# for platform-wide vocabulary.
# ---------------------------------------------------------------------------


class ControlEvaluationStatus(str, Enum):
    """The outcome of checking one control against one banking domain for
    one scan (assessment/evaluators/control_evaluator.py). Deliberately
    distinct from DecisionCategory (a domain-level, severity-weighted
    aggregate) — this is a per-control, presence/absence determination:
    did any finding within this domain match this control's rule prefix.

    INSUFFICIENT_EVIDENCE mirrors scoring/engine.py's core fix at the
    control granularity: a domain that was never evaluated must not
    silently report every one of its applicable controls as SATISFIED."""

    SATISFIED = "satisfied"
    GAP = "gap"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AuditEventType(str, Enum):
    """The fixed vocabulary of governance-relevant events
    (governance/audit_trail.py). Closed on purpose — an append-only log
    whose event types could be arbitrary free text would not be reliably
    queryable or reportable."""

    SCAN_PERSISTED = "scan_persisted"
    SCORING_COMPLETED = "scoring_completed"
    CONTROL_EVALUATION_COMPLETED = "control_evaluation_completed"
    ASSESSMENT_COMPLETED = "assessment_completed"
    FINDING_REVIEWED = "finding_reviewed"
    RECOMMENDATION_REVIEWED = "recommendation_reviewed"
    SCORE_OVERRIDDEN = "score_overridden"
    AGENT_ACTION = "agent_action"


# ---------------------------------------------------------------------------
# Phase 6 additions (optional external-agent infrastructure). Appended here
# for the same reason every prior phase's additions were — this module is
# the single home for platform-wide vocabulary. The agent boundary sits
# outside the deterministic assessment core (see agents/README.md); its
# actions still use this shared vocabulary rather than defining a second,
# competing enum module.
# ---------------------------------------------------------------------------


class AgentActionType(str, Enum):
    """The fixed set of advisory actions the optional agent boundary
    supports (agents/agent_service.py). Closed on purpose — every action
    has its own dedicated, size-limited context-sanitization function
    (agents/sanitizer.py); an open-ended action type would make that
    boundary impossible to reason about."""

    EXPLAIN_FINDING = "explain_finding"
    SUMMARIZE_DOMAIN = "summarize_domain"
    ANSWER_QUESTION = "answer_question"
    EXECUTIVE_SUMMARY = "executive_summary"


__all__ = [
    "Severity",
    "ConfidenceLevel",
    "EvidenceCompleteness",
    "HumanReviewStatus",
    "DecisionCategory",
    "ControlType",
    "ScanStatus",
    "SkipReason",
    "FindingCategory",
    "FindingType",
    "RemediationMode",
    "MappingSource",
    "EvidenceType",
    "RecommendationStatus",
    "RecommendationSource",
    "ControlEvaluationStatus",
    "AuditEventType",
    "AgentActionType",
]
