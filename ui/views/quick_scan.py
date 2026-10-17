from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from core.logging import get_logger
from ui.app_context import page_setup, run_action
from ui.components.badges import severity_rank
from ui.components.layout import page_title

# Quick Scan: the Phase 2 scanner only, in memory — nothing is persisted
# except the audit event recording who ran it. Parity with the legacy UI's
# "Quick Scan only" mode (which no longer runs without a database, because
# sign-in itself needs the database).

_logger = get_logger(__name__)
ctx, principal = page_setup(Permission.RUN_QUICK_SCAN)
page_title("Quick Scan", "Scanner only, in memory: no scoring, no persistence, nothing written to the source.")


def _uses_container_scan_mounts() -> bool:
    s = ctx.settings
    if s.mock_banking_system_path.startswith("/"):
        return True
    return any(p.replace("\\", "/").startswith("/scan-targets") for p in s.allowed_scan_paths)


with st.container(border=True):
    source_kind = st.radio("Source type", ["Local directory", "ZIP archive"], horizontal=True)
    if _uses_container_scan_mounts():
        example = "/scan-targets/target-system.zip" if source_kind == "ZIP archive" else ctx.settings.mock_banking_system_path
        help_text = (
            "Running in Docker: scan targets must be bind-mounted into the app container. "
            f"Example {'ZIP file' if source_kind == 'ZIP archive' else 'directory'} path: `{example}`."
        )
    else:
        example = r"C:\path\to\archive.zip" if source_kind == "ZIP archive" else r"C:\path\to\project"
        help_text = "Enter a local directory or ZIP archive path inside one of the configured ALLOWED_SCAN_PATHS entries."
    source_path = st.text_input("Path (must be inside an ALLOWED_SCAN_PATHS entry)", placeholder=example)
    st.caption(help_text)
    if st.button("Validate and Start Read-Only Scan", type="primary", disabled=not source_path):
        with st.spinner("Validating source and running read-only scan..."):
            ok, scan = run_action(
                "Scan", ctx.assessments.run_quick_scan, principal, source_path, is_archive=source_kind == "ZIP archive"
            )
        st.session_state["quick_scan_result"] = scan if ok else None

result = st.session_state.get("quick_scan_result")
if result is None:
    st.stop()

summary = result.summary
c1, c2, c3, c4 = st.columns(4)
c1.metric("Status", summary.status.value)
c2.metric("Files scanned", summary.files_scanned)
c3.metric("Total findings", summary.total_findings)
c4.metric("Source integrity verified", "YES" if summary.integrity_verified else "NO — SEE WARNINGS")

if result.findings:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Severity": n.raw.severity.value.upper(),
                    "Rule": n.raw.rule_id,
                    "File": n.source_relative_path,
                    "Line": n.raw.line_start,
                    "Evidence (masked)": n.raw.masked_evidence,
                }
                for n in sorted(result.findings, key=lambda n: (severity_rank(n.raw.severity.value), n.raw.rule_id))
            ]
        ),
        hide_index=True,
        width="stretch",
    )

if ctx.can(principal, Permission.EXPORT_REPORTS):
    ok, exports = run_action("Preparing export", ctx.assessments.export_quick_scan, principal, result)
    if ok:

        def _record(fmt: str) -> None:
            try:
                ctx.assessments.record_export(principal, fmt, quick_scan_id=summary.scan_id)
            except Exception as exc:  # noqa: BLE001 — never block a download on audit logging
                _logger.error("export_audit_failed", error_type=type(exc).__name__)

        d1, d2 = st.columns(2)
        d1.download_button("Download JSON", exports["json"], file_name=f"scan_{summary.scan_id}.json", mime="application/json", on_click=_record, args=("quick_scan_json",))
        d2.download_button("Download Markdown", exports["markdown"], file_name=f"scan_{summary.scan_id}.md", mime="text/markdown", on_click=_record, args=("quick_scan_markdown",))
else:
    st.caption("Report downloads are available to Managers and Administrators.")
