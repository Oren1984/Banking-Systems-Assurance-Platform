from __future__ import annotations

import streamlit as st

from auth.permissions import Permission
from core.logging import get_logger
from ui.app_context import page_setup, run_action
from ui.components.layout import page_title, require_active_assessment

# Sanitized report exports (MANAGER, ADMIN). Same four formats the legacy
# "Export" tab offered, produced by the unchanged reporting/ exporters.
# Each actual download is recorded in the audit trail.

_logger = get_logger(__name__)
ctx, principal = page_setup(Permission.EXPORT_REPORTS)
page_title("Reports", "Download sanitized exports of the active assessment. Every download is audited.")
result = require_active_assessment(ctx, principal)
scan_id = result.scan_id

ok, exports = run_action("Preparing exports", ctx.assessments.export_assessment, principal, scan_id)
if not ok:
    st.stop()
if exports is None:
    st.warning("Nothing to export.")
    st.stop()


def _record(fmt: str) -> None:
    try:
        ctx.assessments.record_export(principal, fmt, scan_id=scan_id)
    except Exception as exc:  # noqa: BLE001 — never block a download on audit logging
        _logger.error("export_audit_failed", error_type=type(exc).__name__)


FORMATS = [
    ("json", "Full assessment (JSON)", "Machine-readable: scan, findings, scores, controls, recommendations.", f"assessment_{scan_id}.json", "application/json"),
    ("markdown", "Assessment report (Markdown)", "Human-readable report for reviewers and stakeholders.", f"assessment_{scan_id}.md", "text/markdown"),
    ("findings_csv", "Findings (CSV)", "One row per finding, for spreadsheets and trackers.", f"findings_{scan_id}.csv", "text/csv"),
    ("scores_csv", "Domain scores (CSV)", "One row per domain score, including overrides.", f"scores_{scan_id}.csv", "text/csv"),
]
cols = st.columns(2)
for i, (key, title, description, file_name, mime) in enumerate(FORMATS):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(description)
            st.download_button(
                f"Download {title.split(' (')[-1].rstrip(')')}",
                exports[key],
                file_name=file_name,
                mime=mime,
                on_click=_record,
                args=(key,),
                key=f"download_{key}",
            )
st.caption("Secrets and PII are masked before storage; exports pass through the same report sanitizer.")
