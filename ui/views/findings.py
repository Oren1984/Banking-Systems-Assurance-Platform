from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from ui.app_context import page_setup, run_action
from ui.components.badges import domain_label, humanize, review_badge, severity_badge, severity_rank
from ui.components.layout import page_title, require_active_assessment

ctx, principal = page_setup(Permission.VIEW_ASSESSMENTS)
page_title("Findings & Evidence", "Filter the active assessment's findings and inspect masked evidence and traceability.")
result = require_active_assessment(ctx, principal)
findings = sorted(result.findings, key=lambda f: (severity_rank(f.severity), f.rule_id, f.source_relative_path, f.line_start))

if not findings:
    st.success("This assessment produced no findings.")
    st.stop()

with st.container(border=True):
    r1c1, r1c2, r1c3 = st.columns(3)
    severity_filter = r1c1.multiselect("Severity", sorted({f.severity for f in findings}, key=severity_rank), format_func=str.upper)
    domain_filter = r1c2.multiselect(
        "Banking domain", sorted({d for f in findings for d in (f.banking_domains or [])}), format_func=domain_label
    )
    rule_filter = r1c3.multiselect("Rule", sorted({f.rule_id for f in findings}))
    r2c1, r2c2 = st.columns([1, 2])
    review_filter = r2c1.multiselect("Review status", sorted({f.human_review_status for f in findings}), format_func=humanize)
    path_filter = r2c2.text_input("File path contains")

filtered = [
    f
    for f in findings
    if (not severity_filter or f.severity in severity_filter)
    and (not domain_filter or set(f.banking_domains or []) & set(domain_filter))
    and (not rule_filter or f.rule_id in rule_filter)
    and (not review_filter or f.human_review_status in review_filter)
    and (not path_filter or path_filter.lower() in f.source_relative_path.lower())
]
st.caption(f"Showing {len(filtered)} of {len(findings)} findings")
if not filtered:
    st.info("No findings match these filters.")
    st.stop()

st.dataframe(
    pd.DataFrame(
        [
            {
                "Severity": f.severity.upper(),
                "Rule": f.rule_id,
                "Title": f.title,
                "File": f.source_relative_path,
                "Line": f.line_start,
                "Domains": ", ".join(domain_label(d) for d in (f.banking_domains or [])),
                "Review": humanize(f.human_review_status),
                "Confidence": f.confidence,
            }
            for f in filtered
        ]
    ),
    hide_index=True,
    width="stretch",
    column_config={"Line": st.column_config.NumberColumn(format="%d", width="small")},
)

st.markdown("#### Finding details")
options = {f.id: f for f in filtered}
selected = st.selectbox(
    "Finding",
    list(options),
    format_func=lambda i: f"[{options[i].severity.upper()}] {options[i].rule_id} — {options[i].source_relative_path}:{options[i].line_start}",
)
f = options[selected]
with st.container(border=True):
    st.markdown(f"{severity_badge(f.severity)} {review_badge(f.human_review_status)} &nbsp; **{f.title}**")
    st.caption(
        f"{f.rule_id} · `{f.source_relative_path}`, line {f.line_start} · confidence {f.confidence} · "
        f"domains: {', '.join(domain_label(d) for d in (f.banking_domains or [])) or 'none'}"
    )
    st.markdown("**Evidence (masked)**")
    st.code(f.masked_evidence, language=None)
    st.markdown(f"**Description:** {f.description}")
    st.markdown(f"**Impact:** {f.impact}")
    st.markdown(f"**Recommended action (advisory only):** {f.recommended_action}")
    if f.reviewed_by:
        st.caption(f"Reviewed by {f.reviewed_by} at {str(f.reviewed_at)[:19]} UTC")
    if st.button("Show full traceability", key=f"trace_{f.id}"):
        ok, trace = run_action("Traceability", ctx.assessments.trace_finding, principal, f.id)
        if ok and trace is not None:
            st.json(
                {
                    "control_ids": trace.control_ids,
                    "control_evaluation_statuses": trace.control_evaluation_statuses,
                    "evidence_ids": trace.evidence_ids,
                    "domain_scores": trace.domain_scores,
                    "recommendation_ids": trace.recommendation_ids,
                }
            )
