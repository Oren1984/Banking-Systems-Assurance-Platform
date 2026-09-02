from __future__ import annotations

import streamlit as st

import ui.services.agent_ui_service as agent_svc
import ui.services.assessment_service as svc
from core.config import get_settings
from core.domains import get_domain_label
from core.logging import get_logger
from governance.approval_workflow import FinalizationCheckResult
from governance.report_sanitizer import sanitize_report
from models.enums import DecisionCategory, HumanReviewStatus
from reporting.scan_report_exporter import to_json as to_scan_json
from reporting.scan_report_exporter import to_markdown as to_scan_markdown
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory, ingest_zip_archive
from storage.db.session import check_database_connectivity

_logger = get_logger(__name__)

# Phase 5 — End-to-end demonstration UI
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 5: "Extend the existing
# Streamlit application into a coherent end-to-end demonstration
# workflow"). Extends, rather than replaces, Phase 2's original
# ingest-and-scan flow (kept below as "Quick Scan" — it never needs a
# database, so it stays available for an operator without DATABASE_URL
# configured). The new "Full Assessment" mode is the Phase 5 deliverable:
# select a source (mock_banking_system/ by default) → run a real,
# persisted assessment.engine.run_assessment() → view domain scores,
# findings, control evaluations, and traceability → perform governance
# review/override actions through governance/approval_workflow.py → check
# finalization eligibility → export a sanitized report.
#
# Phase 6 — added the "AI Assistant (Optional)" tab: a clearly separated,
# optional advisory layer (agents/, via ui/services/agent_ui_service.py)
# offered alongside every other Full Assessment tab, never in place of
# one. Defaults to local mode (no external call, no API key required);
# every action still requires an explicit button click — nothing here
# runs when a scan is opened or another tab is viewed. See
# docs/agent_guide.md.
#
# All business logic lives in ui/services/{assessment_service,
# agent_ui_service}.py (no Streamlit import in either, fully unit-tested);
# this file only renders. See docs/demo_guide.md for a full walkthrough
# with expected results.

st.set_page_config(page_title="Banking Systems Assurance Platform", layout="wide")


def _operation_failed_message(action: str, exc: Exception) -> str:
    """Log the full (sanitized) exception for operators and return a
    generic, non-leaking message for the UI. Raw exception text is never
    shown to the viewer — it can incidentally include internal paths, DB
    connection details, or library internals, and this UI has no
    authentication gate. Reuses governance/report_sanitizer.py's masking
    (secrets/PII patterns) rather than a second implementation."""
    _logger.error(
        "ui_operation_failed",
        action=action,
        error_type=type(exc).__name__,
        error=sanitize_report(str(exc)),
    )
    return f"{action} — see application logs for details."


@st.cache_data(ttl=15, show_spinner=False)
def _cached_database_status(database_url: str | None) -> bool:
    """Cached for 15s so the connectivity probe in the status banner does not
    run a fresh network round-trip on every Streamlit rerun (every widget
    interaction reruns this whole script)."""
    return check_database_connectivity(database_url)


def _status_banner(settings) -> None:
    cols = st.columns(5)
    cols[0].metric("Mode", "READ-ONLY")
    cols[1].metric("Local-only", "YES" if settings.local_only_mode else "NO")
    cols[2].metric("External providers", "DISABLED" if not settings.external_providers_enabled else "ENABLED")
    cols[3].metric("Vector backend", settings.vector_backend)
    if not settings.database_url:
        db_status = "NOT CONFIGURED"
    elif _cached_database_status(settings.database_url):
        db_status = "CONNECTED"
    else:
        db_status = "UNREACHABLE"
    cols[4].metric("Database", db_status)


def _help_section() -> None:
    """Compact in-app Help / System Information panel. Summarizes (does not
    replace) docs/security_boundaries.md, docs/architecture.md, and
    README.md — kept here so someone using the running app, not just the
    repository, can see what this platform is, its POC/MVP boundaries, and
    what Production would additionally require, without leaving the UI."""
    with st.sidebar.expander("Help / System Information", expanded=False):
        st.markdown(
            "**What this is**\n"
            "A read-only assessment/governance tool for banking-adjacent codebases — it scans "
            "an approved local source, maps findings to banking-domain controls, scores risk, "
            "and supports human governance review. **It is not a banking transaction system** "
            "and holds no customer accounts, balances, or payment functionality.\n\n"
            "**Primary workflow**\n"
            "Select a source → run a Full Assessment (ingest → scan → score → control "
            "evaluation) → review findings and domain scores → governance review/override with "
            "a reason → export a sanitized report. See `docs/demo_guide.md` for a full "
            "walkthrough.\n\n"
            "**Security and privacy boundaries (implemented today)**\n"
            "- Scanning is strictly read-only; source-integrity hashing verifies nothing was "
            "modified.\n"
            "- Secrets and PII in scan output are masked before storage/display (regex-based, "
            "documented as non-exhaustive).\n"
            "- Recommendations are advisory only — this platform never auto-remediates a "
            "scanned system.\n"
            "- The optional AI Assistant tab defaults to a local, non-network mode; an external "
            "provider is off unless explicitly configured, and its use is clearly labeled.\n"
            "- The audit trail is append-only, but the reviewer/actor identity recorded in it "
            "is **self-typed and not authenticated** (see below).\n\n"
            "**Known limitations (this POC/MVP)**\n"
            "- No authentication, login, or session management — anyone who can reach this app "
            "can perform every action.\n"
            "- No roles or access control — every user can review findings, override scores, "
            "and use the AI assistant identically.\n"
            "- Governance actor/reviewer identity is an unverified free-text field, not a "
            "verified or session-bound identity.\n"
            "- PII/secret detection is pattern-based and explicitly not exhaustive.\n"
            "- No production-grade monitoring/alerting stack; this is a single-operator local "
            "demo, not a hosted service.\n\n"
            "**Deployment assumption**\n"
            "Designed to run locally (Docker Compose or a local Python environment) for a "
            "single operator, on a trusted machine/network — see `README.md` and "
            "`docs/PROJECT_RUNBOOK.md`.\n\n"
            "**Would be mandatory before any Production use** (not implemented here — see "
            "`docs/security_boundaries.md`)\n"
            "- Real authentication with secure login/logout and verified user identity.\n"
            "- Role separation / RBAC for governance actions.\n"
            "- Session management with server-side, tamper-resistant identity.\n"
            "- Audit events bound to a verified identity, not free text.\n"
            "- MFA/SSO integration as applicable to the deployment environment.\n"
            "- Production-grade monitoring, alerting, and secrets management.\n"
            "- Deployment hardening (network isolation, TLS termination, secrets rotation).\n\n"
            "**This is a portfolio-grade POC/MVP.** It demonstrates an assurance workflow, "
            "not a production-ready or regulation-compliant system."
        )


def main() -> None:
    settings = get_settings()
    _help_section()

    st.title("Banking Systems Assurance Platform")
    st.caption(
        "Read-only assessment, evidence, scoring, control evaluation, and governance review — "
        "advisory only, never auto-remediated. See docs/demo_guide.md."
    )
    _status_banner(settings)
    st.divider()

    mode = st.sidebar.radio(
        "Mode",
        ["Full Assessment (recommended)", "Quick Scan only (no database)"],
        help="Full Assessment persists results and unlocks scoring, control evaluation, and "
        "governance review. Quick Scan runs the Phase 2 scanner only, in memory, with no "
        "database required.",
    )

    if mode == "Quick Scan only (no database)":
        _quick_scan_tab(settings)
        st.caption("Designed and developed by Oren Salami")
        return

    if not settings.database_url:
        st.error(
            "DATABASE_URL is not configured. Full Assessment mode requires a database — "
            "set DATABASE_URL, or switch to 'Quick Scan only' in the sidebar."
        )
        st.caption("Designed and developed by Oren Salami")
        return

    _full_assessment_mode(settings)
    st.caption("Designed and developed by Oren Salami")


# --------------------------------------------------------------------- #
# Full Assessment mode (Phase 5)
# --------------------------------------------------------------------- #


def _full_assessment_mode(settings) -> None:
    st.header("1. Select Source and Run Assessment")
    _run_assessment_section(settings)

    st.divider()
    st.header("2. Load an Existing Scan")
    _scan_picker_section(settings)

    scan_id = st.session_state.get("current_scan_id")
    if not scan_id:
        st.info("Run a new assessment or select an existing scan above to continue.")
        return

    result = svc.get_assessment(settings, scan_id)
    if result is None:
        st.warning(f"Scan `{scan_id}` no longer exists.")
        return

    st.divider()
    st.header(f"3. Assessment Summary — `{scan_id}`")
    _summary_section(result)

    tabs = st.tabs(
        [
            "Domain Scores",
            "Findings & Evidence",
            "Control Evaluations",
            "Governance",
            "Export",
            "AI Assistant (Optional)",
        ]
    )
    with tabs[0]:
        _domain_scores_tab(settings, result)
    with tabs[1]:
        _findings_tab(settings, result)
    with tabs[2]:
        _control_evaluations_tab(result)
    with tabs[3]:
        _governance_tab(settings, result)
    with tabs[4]:
        _export_tab(settings, scan_id)
    with tabs[5]:
        _agent_tab(settings, result)


def _run_assessment_section(settings) -> None:
    source_kind = st.radio(
        "Source",
        [
            "Mock Banking System (demo)",
            "Reference Banking System (well-governed demo)",
            "Custom local directory",
            "Custom ZIP archive",
        ],
        horizontal=True,
    )
    if source_kind == "Mock Banking System (demo)":
        source_path = settings.mock_banking_system_path
        is_archive = False
        st.caption(
            "See `mock_banking_system/README.md` and `docs/mock_banking_planted_findings.md` "
            f"for what this fixture contains and exactly what results to expect. Source path: `{source_path}`."
        )
    elif source_kind == "Reference Banking System (well-governed demo)":
        source_path = settings.reference_banking_system_path
        is_archive = False
        st.caption(
            "A second, small, deliberately well-governed fixture — contrast this against the "
            "Mock Banking System result above. See `reference_banking_system/README.md` and "
            f"`docs/reference_banking_system_findings.md`. Source path: `{source_path}`."
        )
    else:
        source_path = st.text_input("Path (must be inside an ALLOWED_SCAN_PATHS entry)")
        is_archive = source_kind == "Custom ZIP archive"

    if st.button("Run Full Assessment", type="primary", disabled=not source_path):
        with st.spinner("Ingesting, scanning, scoring, evaluating controls, and recording the audit trail..."):
            try:
                result = svc.run_new_assessment(settings, source_path, is_archive=is_archive)
                st.session_state["current_scan_id"] = result.scan_id
                st.success(f"Assessment complete — scan_id `{result.scan_id}`")
            except Exception as exc:  # noqa: BLE001 — surface any failure to the operator, not a crash
                st.error(_operation_failed_message("Assessment could not be completed", exc))


def _scan_picker_section(settings) -> None:
    scans = svc.list_recent_scans(settings)
    if not scans:
        st.write("No scans recorded yet.")
        return
    options = {f"{s.created_at} — {s.scan_id} ({s.total_findings} findings, {s.status})": s.scan_id for s in scans}
    choice = st.selectbox("Recent scans", ["(none selected)"] + list(options.keys()))
    if choice != "(none selected)":
        st.session_state["current_scan_id"] = options[choice]


def _summary_section(result) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Findings", len(result.findings))
    c2.metric("Domains scored", len(result.scores))
    c3.metric("Control evaluations", len(result.control_evaluations))
    c4.metric("Recommendations", len(result.recommendations))
    c5.metric("Audit events", len(result.audit_events))


def _domain_scores_tab(settings, result) -> None:
    by_category: dict[str, int] = {}
    for s in result.scores:
        by_category[s.decision_category] = by_category.get(s.decision_category, 0) + 1
    st.subheader("Decision category distribution")
    st.bar_chart(by_category)

    st.subheader("Domain scores")
    for s in sorted(result.scores, key=lambda s: s.domain):
        label = _domain_label_safe(s.domain)
        weighted = f"{s.weighted_score:.1f}" if s.weighted_score is not None else "N/A (insufficient evidence)"
        with st.expander(f"{label} — {s.decision_category} (weighted: {weighted})"):
            st.write(
                f"**Raw score:** {s.raw_score}  |  **Weighted score:** {s.weighted_score}  |  "
                f"**Confidence:** {s.confidence_level}  |  **Evidence completeness:** {s.evidence_completeness}"
            )
            st.write(f"**Findings:** {s.findings_count}  |  **Files evaluated:** {s.files_evaluated}")
            if s.override_of:
                st.info(f"This is an override of score `{s.override_of}`.")
            history = svc.get_score_history(settings, result.scan_id, s.domain)
            if len(history) > 1:
                st.write("**Score history (oldest first):**")
                for h in history:
                    marker = " (override)" if h.override_of else " (original)"
                    st.write(f"- `{h.id}`{marker}: {h.decision_category}, weighted={h.weighted_score}")


def _findings_tab(settings, result) -> None:
    findings = result.findings
    all_severities = sorted({f.severity for f in findings})
    all_domains = sorted({d for f in findings for d in (f.banking_domains or [])})
    all_rules = sorted({f.rule_id for f in findings})

    fc1, fc2, fc3, fc4 = st.columns(4)
    severity_filter = fc1.multiselect("Severity", all_severities)
    domain_filter = fc2.multiselect("Banking domain", all_domains)
    rule_filter = fc3.multiselect("Rule", all_rules)
    path_filter = fc4.text_input("File path contains")

    filtered = [
        f
        for f in findings
        if (not severity_filter or f.severity in severity_filter)
        and (not domain_filter or set(f.banking_domains or []) & set(domain_filter))
        and (not rule_filter or f.rule_id in rule_filter)
        and (not path_filter or path_filter.lower() in f.source_relative_path.lower())
    ]
    st.write(f"Showing {len(filtered)} of {len(findings)} findings")

    for f in filtered:
        with st.expander(
            f"[{f.severity.upper()}] {f.rule_id} — {f.source_relative_path}:{f.line_start} "
            f"({f.human_review_status})"
        ):
            st.write(f"**Confidence:** {f.confidence}  |  **Banking domains:** {', '.join(f.banking_domains or []) or 'none'}")
            st.code(f.masked_evidence)
            st.write(f"**Description:** {f.description}")
            st.write(f"**Recommended action (advisory only):** {f.recommended_action}")
            if st.button("Show full traceability", key=f"trace_{f.id}"):
                trace = svc.trace_finding(settings, f.id)
                if trace is not None:
                    st.json(
                        {
                            "control_ids": trace.control_ids,
                            "control_evaluation_statuses": trace.control_evaluation_statuses,
                            "evidence_ids": trace.evidence_ids,
                            "domain_scores": trace.domain_scores,
                            "recommendation_ids": trace.recommendation_ids,
                        }
                    )


def _control_evaluations_tab(result) -> None:
    from collections import Counter

    counts = Counter(ce.status for ce in result.control_evaluations)
    st.bar_chart(dict(counts))
    by_domain: dict[str, list] = {}
    for ce in result.control_evaluations:
        by_domain.setdefault(ce.domain, []).append(ce)
    for domain in sorted(by_domain):
        label = _domain_label_safe(domain)
        with st.expander(f"{label} — {len(by_domain[domain])} control result(s)"):
            for ce in by_domain[domain]:
                st.write(f"- `{ce.control_id or 'N/A'}`: **{ce.status}** (findings: {ce.finding_ids})")


def _governance_tab(settings, result) -> None:
    scan_id = result.scan_id

    st.subheader("Finalization status")
    check: FinalizationCheckResult = svc.check_finalization(settings, scan_id)
    if check.can_finalize:
        st.success("This assessment CAN be finalized — no high/critical-risk domain has a pending review.")
    else:
        st.error("This assessment CANNOT be finalized yet:")
        for blocker in check.blockers:
            st.write(f"- {blocker.reason}")

    st.subheader("Review a finding")
    pending = [f for f in result.findings if f.human_review_status == HumanReviewStatus.PENDING.value]
    st.write(f"{len(pending)} of {len(result.findings)} findings are pending review.")
    if pending:
        options = {f"[{f.severity.upper()}] {f.rule_id} — {f.source_relative_path}": f.id for f in pending}
        choice = st.selectbox("Pending finding", list(options.keys()), key="review_finding_choice")
        finding_id = options[choice]
        new_status = st.selectbox(
            "Decision",
            [HumanReviewStatus.APPROVED.value, HumanReviewStatus.REJECTED.value, HumanReviewStatus.OVERRIDDEN.value],
        )
        reviewer = st.text_input(
            "Reviewer identity (unverified demo entry — not authenticated)",
            value="demo-reviewer@example.com",
            key="review_reviewer",
            help="This platform has no login/authentication. This value is recorded in the "
            "audit trail as typed, with no identity verification. See Help / System "
            "Information for what Production would require.",
        )
        reason = st.text_area("Reviewer comment / reason (required for 'overridden')", key="review_reason")
        if st.button("Submit review"):
            try:
                svc.review_finding(settings, finding_id, HumanReviewStatus(new_status), reviewer, reason or None)
                st.success("Review recorded — recorded in the append-only audit trail.")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(_operation_failed_message("Could not record review", exc))

    st.subheader("Override a domain score")
    scores = svc.get_scores(settings, scan_id)
    score_options = {f"{s.domain} — {s.decision_category} (weighted={s.weighted_score})": s for s in scores}
    score_choice = st.selectbox("Domain score", list(score_options.keys()), key="override_score_choice")
    chosen_score = score_options[score_choice]
    new_category = st.selectbox("New decision category", [c.value for c in DecisionCategory], key="override_category")
    override_reviewer = st.text_input(
        "Reviewer identity (unverified demo entry — not authenticated)",
        value="demo-reviewer@example.com",
        key="override_reviewer",
        help="This platform has no login/authentication. This value is recorded in the "
        "audit trail as typed, with no identity verification. See Help / System "
        "Information for what Production would require.",
    )
    override_reason = st.text_area("Justification (required)", key="override_reason")
    if st.button("Submit override"):
        if not override_reason.strip():
            st.error("A justification is required to override a score.")
        else:
            try:
                svc.override_score(
                    settings,
                    chosen_score.id,
                    scan_id,
                    chosen_score.domain,
                    DecisionCategory(new_category),
                    override_reviewer,
                    override_reason,
                )
                st.success(
                    "Override recorded as a new Score row (the original is preserved, never mutated)."
                )
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(_operation_failed_message("Could not record override", exc))

    st.subheader("Audit trail")
    st.caption(
        "The `actor` on each event below is the unverified identity typed into this demo's "
        "reviewer/user fields — this platform has no authentication, so it is not a "
        "cryptographically verified or session-bound identity. See Help / System Information."
    )
    events = svc.get_audit_trail(settings, scan_id)
    for e in events:
        st.write(f"- `{e.created_at}` [{e.event_type}] ({e.actor}): {e.summary}")


def _export_tab(settings, scan_id: str) -> None:
    exports = svc.export_assessment(settings, scan_id)
    if exports is None:
        st.warning("Nothing to export.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("Download JSON", exports["json"], file_name=f"assessment_{scan_id}.json", mime="application/json")
    c2.download_button("Download Markdown", exports["markdown"], file_name=f"assessment_{scan_id}.md", mime="text/markdown")
    c3.download_button("Download Findings CSV", exports["findings_csv"], file_name=f"findings_{scan_id}.csv", mime="text/csv")
    c4.download_button("Download Scores CSV", exports["scores_csv"], file_name=f"scores_{scan_id}.csv", mime="text/csv")


def _agent_tab(settings, result) -> None:
    scan_id = result.scan_id

    st.subheader("Optional AI Assistant")
    status = agent_svc.get_agent_status(settings)
    if status["is_local"]:
        st.info(
            f"**Mode: Local (no external AI provider)** — {status['reason']}. "
            "No data leaves this environment. Responses below are deterministic, sanitized "
            "restatements of existing assessment data, not AI-generated prose."
        )
    else:
        st.warning(
            f"**Mode: External — provider `{status['provider']}`.** Sanitized, size-limited "
            "evidence for the specific action you trigger below **may leave the local "
            "environment** and be sent to this external provider. Nothing is sent until you "
            "click an action button."
        )
    st.caption(
        "Output here is AI-assisted, advisory, and non-deterministic. It is never a scanner "
        "finding, a score, or a governance decision — deterministic findings, scores, control "
        "evaluations, and finalization status are never changed by anything on this tab. "
        "See docs/agent_guide.md."
    )
    if status["warnings"]:
        with st.expander("Configuration notes"):
            for w in status["warnings"]:
                st.write(f"- {w}")

    triggered_by = st.text_input(
        "Your identity (unverified demo entry — not authenticated, for the audit trail)",
        value="demo-user@example.com",
        key="agent_user",
        help="This platform has no login/authentication. This value is recorded in the "
        "audit trail as typed, with no identity verification.",
    )

    st.divider()
    st.markdown("**Explain a finding**")
    if result.findings:
        options = {f"[{f.severity.upper()}] {f.rule_id} — {f.source_relative_path}": f.id for f in result.findings}
        choice = st.selectbox("Finding", list(options.keys()), key="agent_finding_choice")
        if st.button("Explain this finding", key="agent_explain_btn"):
            response = agent_svc.explain_finding(settings, scan_id, options[choice], triggered_by)
            _render_agent_response(response)
    else:
        st.write("No findings to explain.")

    st.divider()
    st.markdown("**Summarize a domain**")
    domains = sorted({d for f in result.findings for d in (f.banking_domains or [])} | {s.domain for s in result.scores})
    if domains:
        domain_choice = st.selectbox("Domain", domains, key="agent_domain_choice")
        if st.button("Summarize this domain", key="agent_summarize_btn"):
            response = agent_svc.summarize_domain(settings, scan_id, domain_choice, triggered_by)
            _render_agent_response(response)

    st.divider()
    st.markdown("**Ask about the assessment evidence**")
    question = st.text_area("Question", key="agent_question")
    if st.button("Ask", key="agent_ask_btn", disabled=not question.strip()):
        try:
            response = agent_svc.answer_question(settings, scan_id, question, triggered_by)
            _render_agent_response(response)
        except Exception as exc:  # noqa: BLE001 — a rejected/unsafe question must not crash the UI
            st.error(_operation_failed_message("Question could not be processed", exc))

    st.divider()
    st.markdown("**Generate an executive narrative**")
    if st.button("Generate executive summary", key="agent_exec_btn"):
        response = agent_svc.generate_executive_summary(settings, scan_id, triggered_by)
        _render_agent_response(response)


def _render_agent_response(response) -> None:
    if response is None:
        st.warning("Nothing to show for this selection.")
        return
    badge = "Local" if response.is_local else f"External — {response.provider_name}"
    if not response.success:
        st.error(f"Provider call failed (fell back to local): {response.error}")
    st.caption(f"[{badge}] {response.disclaimer}")
    st.write(response.content)


def _domain_label_safe(domain_value: str) -> str:
    from core.domains import BankingDomain

    try:
        return get_domain_label(BankingDomain(domain_value))
    except ValueError:
        return domain_value


def _uses_container_scan_mounts(settings) -> bool:
    if settings.mock_banking_system_path.startswith("/"):
        return True
    return any(path.replace("\\", "/").startswith("/scan-targets") for path in settings.allowed_scan_paths)


def _quick_scan_example_path(settings, source_kind: str) -> str:
    if _uses_container_scan_mounts(settings):
        if source_kind == "ZIP archive":
            return "/scan-targets/target-system.zip"
        return settings.mock_banking_system_path
    if source_kind == "ZIP archive":
        return r"C:\path\to\archive.zip"
    return r"C:\path\to\project"


def _quick_scan_help_text(settings, source_kind: str, example_path: str) -> str:
    if _uses_container_scan_mounts(settings):
        kind = "directory" if source_kind == "Local directory" else "ZIP file"
        return (
            f"Running in Docker: scan targets must be bind-mounted into the app container. "
            f"Example {kind} path: `{example_path}`."
        )
    return "Enter a local directory or ZIP archive path inside one of the configured ALLOWED_SCAN_PATHS entries."


# --------------------------------------------------------------------- #
# Quick Scan mode (Phase 2 — unchanged in spirit, no database required)
# --------------------------------------------------------------------- #


def _quick_scan_tab(settings) -> None:
    st.header("Quick Scan (no persistence, no database required)")
    source_kind = st.radio("Source type", ["Local directory", "ZIP archive"], horizontal=True)
    example_path = _quick_scan_example_path(settings, source_kind)
    source_path = st.text_input(
        "Path (must be inside an ALLOWED_SCAN_PATHS entry)",
        placeholder=example_path,
    )
    st.caption(_quick_scan_help_text(settings, source_kind, example_path))

    if "scan_result" not in st.session_state:
        st.session_state["scan_result"] = None

    if st.button("Validate and Start Read-Only Scan", type="primary", disabled=not source_path):
        with st.spinner("Validating source and running read-only scan..."):
            try:
                source = ingest_zip_archive(source_path, settings) if source_kind == "ZIP archive" else ingest_local_directory(source_path, settings)
                try:
                    st.session_state["scan_result"] = run_scan(source, settings)
                finally:
                    source.cleanup()
            except Exception as exc:  # noqa: BLE001
                st.session_state["scan_result"] = None
                st.error(_operation_failed_message("Scan could not be completed", exc))

    result = st.session_state["scan_result"]
    if result is None:
        return

    summary = result.summary
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", summary.status.value)
    c2.metric("Files scanned", summary.files_scanned)
    c3.metric("Total findings", summary.total_findings)
    c4.metric("Source integrity verified", "YES" if summary.integrity_verified else "NO — SEE WARNINGS")

    st.download_button("Download JSON", to_scan_json(result), file_name=f"scan_{summary.scan_id}.json", mime="application/json")
    st.download_button("Download Markdown", to_scan_markdown(result), file_name=f"scan_{summary.scan_id}.md", mime="text/markdown")


if __name__ == "__main__":
    main()
