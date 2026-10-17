from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from ui.app_context import active_scan_id, page_setup, run_action
from ui.components.badges import domain_label, humanize
from ui.components.layout import empty_state, page_title, scan_label

# Read-only comparison of two stored assessments of the same source. The
# matching method is documented in ui/services/comparison_service.py and
# summarized on this page.

ctx, principal = page_setup(Permission.VIEW_ASSESSMENTS)
page_title("Compare Assessments", "What changed between two runs against the same source — read-only.")

_, scans = run_action("Loading assessments", ctx.assessments.list_recent_scans, principal, 100)
scans = scans or []
if len(scans) < 2:
    empty_state(
        "Two assessments are needed",
        "Run at least two Full Assessments of the same source to compare them.",
        "views/assessments.py",
        "Go to Run & History",
    )
    st.stop()

labels = {s.scan_id: scan_label(s) for s in scans}
by_id = {s.scan_id: s for s in scans}
ids = list(labels)
current_default = active_scan_id() if active_scan_id() in labels else ids[0]
same_source_older = [
    s.scan_id
    for s in scans
    if s.source_path == by_id[current_default].source_path and s.created_at < by_id[current_default].created_at
]
baseline_default = same_source_older[0] if same_source_older else next(i for i in ids if i != current_default)

c1, c2 = st.columns(2)
baseline = c1.selectbox("Baseline (earlier)", ids, index=ids.index(baseline_default), format_func=lambda i: labels[i])
current = c2.selectbox("Current (later)", ids, index=ids.index(current_default), format_func=lambda i: labels[i])

with st.expander("How findings are matched"):
    st.markdown(
        "A finding in the current run is **unchanged** when the baseline has a finding with the same "
        "**rule**, **file path**, and **masked evidence** (whitespace-normalized). Line numbers are ignored, "
        "so a finding that only moved because other lines changed is not reported as new. Repeated identical "
        "findings are matched one-to-one. Only assessments of the **same source** that **completed** can be "
        "compared; domain scores use each domain's effective score (human overrides applied). Nothing is written."
    )

if not st.button("Compare", type="primary"):
    st.stop()

ok, comparison = run_action("Comparison", ctx.assessments.compare_scans, principal, baseline, current)
if not ok:
    st.stop()
if comparison.reordered:
    st.info("The selected baseline was the later run; the two were swapped so the comparison reads earlier → later.")

changed_domains = [c for c in comparison.domain_changes if c.category_changed or (c.delta or 0) != 0]
m1, m2, m3, m4 = st.columns(4)
m1.metric("New findings", len(comparison.new_findings))
m2.metric("Resolved findings", len(comparison.resolved_findings))
m3.metric("Unchanged findings", len(comparison.unchanged_findings))
m4.metric("Domains changed", len(changed_domains))


def _findings_frame(refs):
    return pd.DataFrame(
        [
            {
                "Severity": r.severity.upper(),
                "Rule": r.rule_id,
                "Title": r.title,
                "File": r.source_relative_path,
                "Line": r.line_start,
                "Review": humanize(r.human_review_status),
            }
            for r in refs
        ]
    )


tabs = st.tabs(["New", "Resolved", "Unchanged", "Domain scores"])
for tab, refs, empty in (
    (tabs[0], comparison.new_findings, "No new findings."),
    (tabs[1], comparison.resolved_findings, "No findings were resolved."),
    (tabs[2], comparison.unchanged_findings, "No findings carried over."),
):
    with tab:
        if refs:
            st.dataframe(_findings_frame(refs), hide_index=True, width="stretch")
        else:
            st.caption(empty)
with tabs[3]:
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Domain": domain_label(c.domain),
                    "Baseline": humanize(c.baseline_category) if c.baseline_category else "—",
                    "Current": humanize(c.current_category) if c.current_category else "—",
                    "Baseline score": c.baseline_weighted,
                    "Current score": c.current_weighted,
                    "Change": c.delta,
                }
                for c in comparison.domain_changes
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={"Change": st.column_config.NumberColumn(format="%+.1f")},
    )
