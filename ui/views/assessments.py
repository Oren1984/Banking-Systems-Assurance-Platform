from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from ui.app_context import active_scan_id, flash, page_setup, run_action, set_active_scan
from ui.components.badges import decision_badge, domain_label, humanize
from ui.components.charts import count_chart
from ui.components.layout import empty_state, page_title, scan_label
from ui.services.comparison_service import effective_scores

# Run a Full Assessment and browse assessment history. Feature parity with
# the legacy UI's "Select Source and Run Assessment", "Load an Existing
# Scan", "Assessment Summary" and "Domain Scores" sections.

ctx, principal = page_setup(Permission.VIEW_ASSESSMENTS)
page_title("Run & History", "Run a read-only Full Assessment, or open a previous one.")

SOURCES = [
    "Mock Banking System (demo)",
    "Reference Banking System (well-governed demo)",
    "Custom local directory",
    "Custom ZIP archive",
]

if ctx.can(principal, Permission.RUN_ASSESSMENT):
    with st.container(border=True):
        st.markdown("#### Run a new assessment")
        st.caption("Ingest → scan → score → evaluate controls → record the audit trail. The source is never modified.")
        source_kind = st.radio("Source", SOURCES, horizontal=True, key="run_source_kind")
        if source_kind == SOURCES[0]:
            source_path, is_archive = ctx.settings.mock_banking_system_path, False
            st.caption(
                "Planted findings — see `docs/mock_banking_planted_findings.md` for the expected results. "
                f"Source path: `{source_path}`."
            )
        elif source_kind == SOURCES[1]:
            source_path, is_archive = ctx.settings.reference_banking_system_path, False
            st.caption(
                "A small, deliberately well-governed fixture to contrast with the mock system. "
                f"See `docs/reference_banking_system_findings.md`. Source path: `{source_path}`."
            )
        else:
            source_path = st.text_input("Path (must be inside an ALLOWED_SCAN_PATHS entry)", key="run_custom_path")
            is_archive = source_kind == SOURCES[3]
        if st.button("Run Full Assessment", type="primary", disabled=not source_path, key="run_assessment_btn"):
            with st.spinner("Ingesting, scanning, scoring, evaluating controls, and recording the audit trail..."):
                ok, result = run_action(
                    "Assessment", ctx.assessments.run_new_assessment, principal, source_path, is_archive=is_archive
                )
            if ok:
                set_active_scan(result.scan_id)
                flash(f"Assessment complete — {len(result.findings)} findings. It is now the active assessment.")
                st.rerun()

st.markdown("#### Assessment history")
ok, scans = run_action("Loading assessments", ctx.assessments.list_recent_scans, principal, 50)
if not scans:
    empty_state("No assessments yet", "Run a Full Assessment above to create the first one.")
    st.stop()

st.dataframe(
    pd.DataFrame(
        [
            {
                "Run at": s.created_at[:19].replace("T", " "),
                "Source": s.source_path,
                "Status": humanize(s.status),
                "Findings": s.total_findings,
                "Integrity verified": s.integrity_verified,
                "Scan ID": s.scan_id,
            }
            for s in scans
        ]
    ),
    hide_index=True,
    width="stretch",
)

ids = [s.scan_id for s in scans]
labels = {s.scan_id: scan_label(s) for s in scans}
current = active_scan_id() if active_scan_id() in labels else ids[0]
chosen = st.selectbox("Open assessment", ids, index=ids.index(current), format_func=lambda i: labels[i], key=f"history_pick_{current}")
if chosen != current:
    set_active_scan(chosen)
    st.rerun()

ok, result = run_action("Loading assessment", ctx.assessments.get_assessment, principal, chosen)
if not ok or result is None:
    st.stop()

st.markdown(f"#### Assessment summary — `{result.scan_id}`")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Findings", len(result.findings))
c2.metric("Domains scored", len({s.domain for s in result.scores}))
c3.metric("Control evaluations", len(result.control_evaluations))
c4.metric("Recommendations", len(result.recommendations))
c5.metric("Audit events", len(result.audit_events))

st.markdown("#### Domain scores")
st.caption("Overrides never replace a score — they add a new score row; the full history is shown per domain.")
with st.container(border=True):
    st.markdown("**Decision category distribution** (effective scores)")
    count_chart(dict(Counter(s.decision_category for s in effective_scores(result.scores).values())), "Decision")
by_domain: dict = {}
for s in result.scores:
    by_domain.setdefault(s.domain, []).append(s)
for domain in sorted(by_domain):
    rows = sorted(by_domain[domain], key=lambda s: str(s.calculated_at))
    latest = rows[-1]
    weighted = f"{latest.weighted_score:.1f}" if latest.weighted_score is not None else "N/A (insufficient evidence)"
    with st.expander(f"{domain_label(domain)} — {humanize(latest.decision_category)} (weighted: {weighted})"):
        st.markdown(
            f"{decision_badge(latest.decision_category)}  \n"
            f"**Raw score:** {latest.raw_score} · **Weighted score:** {latest.weighted_score} · "
            f"**Confidence:** {latest.confidence_level} · **Evidence completeness:** {latest.evidence_completeness}  \n"
            f"**Findings:** {latest.findings_count} · **Files evaluated:** {latest.files_evaluated}"
        )
        if len(rows) > 1:
            st.markdown("**Score history (oldest first):**")
            for h in rows:
                marker = f"override of `{h.override_of}`" if h.override_of else "original"
                st.markdown(f"- `{h.id}` ({marker}): {humanize(h.decision_category)}, weighted={h.weighted_score}")
