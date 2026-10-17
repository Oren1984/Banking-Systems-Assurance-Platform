from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import ui.services.agent_ui_service as agent_svc
import ui.services.assessment_service as svc
import ui.services.comparison_service as comparison_svc
from auth.auth_service import record_auth_event
from auth.authorizer import Authorizer
from auth.permissions import Permission
from auth.principal import Principal
from models.enums import AuthEventType, DecisionCategory, HumanReviewStatus
from reporting.scan_report_exporter import to_json as to_scan_json
from reporting.scan_report_exporter import to_markdown as to_scan_markdown
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory, ingest_zip_archive
from storage.db.models.audit_event import AuditEvent
from storage.db.models.control import Control

# Thin authorization wrappers around the EXISTING service layer
# (ui/services/assessment_service.py, agent_ui_service.py,
# comparison_service.py). No business logic is re-implemented here: each
# method (1) authorizes through Authorizer.require — session re-validated
# against the database, role checked, denial audited — then (2) delegates
# unchanged. Every reviewer/actor/triggered_by value passed down is the
# authenticated principal's username; callers cannot supply one.
#
# The UI must call these classes, never ui/services/* directly, for any
# action. Direct calls to these wrappers with an insufficient role raise
# AuthorizationError (tests/unit/test_secured_services.py).


class SecuredAssessmentService:
    def __init__(self, authorizer: Authorizer) -> None:
        self._authz = authorizer
        self._settings = authorizer.auth_service.settings

    def _require(self, principal: Principal, permission: Permission, action: str, scan_id: Optional[str] = None) -> Principal:
        return self._authz.require(principal, permission, action, scan_id=scan_id)

    def _audit(self, principal: Principal, event_type: AuthEventType, summary: str, payload: dict, scan_id: Optional[str] = None) -> None:
        with self._authz.auth_service.session() as session:
            record_auth_event(session, event_type, principal.username, summary, payload, scan_id=scan_id)

    # --- Running assessments / scans ---------------------------------------

    def run_new_assessment(self, principal: Principal, source_path: str, is_archive: bool = False):
        principal = self._require(principal, Permission.RUN_ASSESSMENT, "run a full assessment")
        result = svc.run_new_assessment(self._settings, source_path, is_archive=is_archive)
        # The pipeline records its own steps with actor "system"; this event
        # attributes the run to the authenticated user who requested it.
        self._audit(
            principal,
            AuthEventType.ASSESSMENT_REQUESTED,
            "Full assessment requested",
            {"source_type": "archive" if is_archive else "directory"},
            scan_id=result.scan_id,
        )
        return result

    def run_quick_scan(self, principal: Principal, source_path: str, is_archive: bool = False):
        principal = self._require(principal, Permission.RUN_QUICK_SCAN, "run a quick scan")
        source = ingest_zip_archive(source_path, self._settings) if is_archive else ingest_local_directory(source_path, self._settings)
        try:
            result = run_scan(source, self._settings)
        finally:
            source.cleanup()
        # Quick Scan results are never persisted, so its scan id is not a
        # scans row — recorded in the payload, not the FK column.
        self._audit(
            principal,
            AuthEventType.QUICK_SCAN_REQUESTED,
            "Quick scan run (not persisted)",
            {"quick_scan_id": result.summary.scan_id, "total_findings": result.summary.total_findings},
        )
        return result

    # --- Read-only views ----------------------------------------------------

    def list_recent_scans(self, principal: Principal, limit: int = 20) -> List[svc.ScanSummaryRow]:
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments")
        return svc.list_recent_scans(self._settings, limit=limit)

    def get_assessment(self, principal: Principal, scan_id: str):
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments", scan_id)
        return svc.get_assessment(self._settings, scan_id)

    def get_scores(self, principal: Principal, scan_id: str):
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments", scan_id)
        return svc.get_scores(self._settings, scan_id)

    def get_score_history(self, principal: Principal, scan_id: str, domain: str):
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments", scan_id)
        return svc.get_score_history(self._settings, scan_id, domain)

    def trace_finding(self, principal: Principal, finding_id: str):
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments")
        return svc.trace_finding(self._settings, finding_id)

    def check_finalization(self, principal: Principal, scan_id: str):
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments", scan_id)
        return svc.check_finalization(self._settings, scan_id)

    def get_control_catalog(self, principal: Principal) -> Dict[str, Tuple[str, str]]:
        """{controls.id: (control code, title)} — lets the UI show
        human-readable control codes instead of row UUIDs."""
        self._require(principal, Permission.VIEW_ASSESSMENTS, "view assessments")
        with self._authz.auth_service.session() as session:
            return {c.id: (c.control_id, c.title) for c in session.query(Control).all()}

    def compare_scans(self, principal: Principal, baseline_scan_id: str, current_scan_id: str):
        self._require(principal, Permission.VIEW_ASSESSMENTS, "compare assessments")
        return comparison_svc.compare_scans(self._settings, baseline_scan_id, current_scan_id)

    # --- Governance decisions (MANAGER only) ------------------------------

    def review_finding(self, principal: Principal, finding_id: str, new_status: HumanReviewStatus, reason: Optional[str] = None):
        principal = self._require(principal, Permission.REVIEW_FINDINGS, "review findings")
        return svc.review_finding(self._settings, finding_id, new_status, principal.username, reason)

    def override_score(
        self,
        principal: Principal,
        original_score_id: str,
        scan_id: str,
        domain: str,
        new_decision_category: DecisionCategory,
        reason: str,
        new_weighted_score: Optional[float] = None,
    ):
        principal = self._require(principal, Permission.OVERRIDE_SCORES, "override domain scores", scan_id)
        return svc.override_score(
            self._settings,
            original_score_id,
            scan_id,
            domain,
            new_decision_category,
            principal.username,
            reason,
            new_weighted_score=new_weighted_score,
        )

    # --- Exports (MANAGER, ADMIN) -------------------------------------------

    def export_assessment(self, principal: Principal, scan_id: str) -> Optional[Dict[str, str]]:
        self._require(principal, Permission.EXPORT_REPORTS, "export reports", scan_id)
        return svc.export_assessment(self._settings, scan_id)

    def export_quick_scan(self, principal: Principal, scan_result) -> Dict[str, str]:
        self._require(principal, Permission.EXPORT_REPORTS, "export reports")
        return {"json": to_scan_json(scan_result), "markdown": to_scan_markdown(scan_result)}

    def record_export(self, principal: Principal, export_format: str, scan_id: Optional[str] = None, quick_scan_id: Optional[str] = None) -> None:
        """Called when a download is actually clicked, so the audit trail
        shows who took which report out of the platform."""
        principal = self._require(principal, Permission.EXPORT_REPORTS, "export reports", scan_id)
        self._audit(
            principal,
            AuthEventType.REPORT_EXPORTED,
            f"Exported report ({export_format})",
            {"format": export_format, "quick_scan_id": quick_scan_id},
            scan_id=scan_id,
        )

    # --- Audit log (MANAGER, ADMIN) ------------------------------------------

    def get_audit_trail(self, principal: Principal, scan_id: str) -> List[AuditEvent]:
        self._require(principal, Permission.VIEW_AUDIT_LOG, "view the audit log", scan_id)
        return svc.get_audit_trail(self._settings, scan_id)

    def get_platform_audit_log(self, principal: Principal, limit: int = 500) -> List[AuditEvent]:
        self._require(principal, Permission.VIEW_AUDIT_LOG, "view the audit log")
        with self._authz.auth_service.session() as session:
            return list(session.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).all())

    def get_recent_activity(self, principal: Principal, limit: int = 8) -> List[AuditEvent]:
        """Dashboard feed: platform-wide for roles with audit access,
        otherwise only the signed-in user's own events."""
        principal = self._require(principal, Permission.VIEW_ASSESSMENTS, "view recent activity")
        with self._authz.auth_service.session() as session:
            query = session.query(AuditEvent)
            if not self._authz.can(principal, Permission.VIEW_AUDIT_LOG):
                query = query.filter(AuditEvent.actor == principal.username)
            return list(query.order_by(AuditEvent.created_at.desc()).limit(limit).all())


class SecuredAgentService:
    """The advisory AI Assistant behind the same gate. agent_ui_service
    only ever writes AGENT_ACTION audit events — it has no path to change a
    finding, score, or review status, so USE_AI_ASSISTANT cannot be used to
    make a governance decision on anyone's behalf."""

    def __init__(self, authorizer: Authorizer) -> None:
        self._authz = authorizer
        self._settings = authorizer.auth_service.settings

    def _require(self, principal: Principal, scan_id: Optional[str] = None) -> Principal:
        return self._authz.require(principal, Permission.USE_AI_ASSISTANT, "use the AI Assistant", scan_id=scan_id)

    def get_agent_status(self, principal: Principal) -> dict:
        self._require(principal)
        return agent_svc.get_agent_status(self._settings)

    def explain_finding(self, principal: Principal, scan_id: str, finding_id: str):
        principal = self._require(principal, scan_id)
        return agent_svc.explain_finding(self._settings, scan_id, finding_id, principal.username)

    def summarize_domain(self, principal: Principal, scan_id: str, domain: str):
        principal = self._require(principal, scan_id)
        return agent_svc.summarize_domain(self._settings, scan_id, domain, principal.username)

    def answer_question(self, principal: Principal, scan_id: str, question: str):
        principal = self._require(principal, scan_id)
        return agent_svc.answer_question(self._settings, scan_id, question, principal.username)

    def generate_executive_summary(self, principal: Principal, scan_id: str):
        principal = self._require(principal, scan_id)
        return agent_svc.generate_executive_summary(self._settings, scan_id, principal.username)


__all__ = ["SecuredAssessmentService", "SecuredAgentService"]
