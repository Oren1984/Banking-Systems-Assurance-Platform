from __future__ import annotations

import streamlit as st

from auth.permissions import Permission
from models.enums import HumanReviewStatus
from ui.app_context import page_setup, run_action
from ui.components.badges import decision_badge, humanize, severity_badge, severity_rank
from ui.components.charts import domain_scores_chart, severity_chart
from ui.components.layout import page_title, require_active_assessment
from ui.services.comparison_service import effective_scores

ctx, principal = page_setup(Permission.VIEW_ASSESSMENTS)
page_title("Dashboard", "Risk posture of the active assessment at a glance.")
result = require_active_assessment(ctx, principal)

findings = result.findings
scores = effective_scores(result.scores)
pending = [f for f in findings if f.human_review_status == HumanReviewStatus.PENDING.value]
critical_high = [f for f in findings if str(f.severity).lower() in ("critical", "high")]
risky_domains = [d for d, s in scores.items() if s.decision_category in ("critical_risk", "high_risk")]
_, finalization = run_action("Finalization check", ctx.assessments.check_finalization, principal, result.scan_id)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Findings", len(findings))
c2.metric("Critical / high", len(critical_high))
c3.metric("Pending review", len(pending))
c4.metric("High-risk domains", f"{len(risky_domains)} of {len(scores)}")
if finalization is not None:
    c5.metric(
        "Finalization",
        "Ready" if finalization.can_finalize else "Blocked",
        help="Blocked while a high/critical-risk domain still has findings pending human review.",
    )

left, right = st.columns([3, 2], gap="large")
with left:
    with st.container(border=True):
        st.markdown("#### Domain scores")
        st.caption("Effective score per banking domain (human overrides applied).")
        domain_scores_chart(scores)
with right:
    with st.container(border=True):
        st.markdown("#### Severity distribution")
        severity_chart(f.severity for f in findings)
    with st.container(border=True):
        st.markdown("#### Assessment")
        scan = result.scan_row
        st.markdown(
            f"**Source:** `{scan.source_path}`  \n"
            f"**Run at:** {str(scan.created_at)[:19]} UTC  \n"
            f"**Status:** {humanize(scan.status)} · **Files scanned:** {scan.files_scanned}  \n"
            f"**Source integrity:** {'verified — nothing was modified' if scan.integrity_verified else 'NOT verified — see warnings'}"
        )

left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True):
        st.markdown("#### Pending reviews")
        if not pending:
            st.caption("Every finding in this assessment has been reviewed.")
        for f in sorted(pending, key=lambda f: severity_rank(f.severity))[:6]:
            st.markdown(f"{severity_badge(f.severity)} **{f.rule_id}** · `{f.source_relative_path}:{f.line_start}`")
        if pending:
            if ctx.can(principal, Permission.REVIEW_FINDINGS):
                st.page_link("views/review_queue.py", label=f"Review {len(pending)} pending finding(s)", icon=":material/fact_check:")
            else:
                st.caption("Findings are reviewed by a Manager.")
        if finalization is not None and not finalization.can_finalize:
            for blocker in finalization.blockers[:4]:
                st.caption(f"Blocks finalization: {blocker.reason}")
with right:
    with st.container(border=True):
        scope = "Platform activity" if ctx.can(principal, Permission.VIEW_AUDIT_LOG) else "Your recent activity"
        st.markdown(f"#### {scope}")
        _, events = run_action("Loading activity", ctx.assessments.get_recent_activity, principal, 8)
        if not events:
            st.caption("No activity recorded yet.")
        for e in events or []:
            st.markdown(f"`{str(e.created_at)[:16]}` **{e.actor}** — {humanize(e.event_type)}")

with st.expander("Domains needing attention"):
    risky = sorted(scores.values(), key=lambda s: (s.weighted_score is None, s.weighted_score or 0))
    for s in risky:
        if s.decision_category in ("acceptable", "acceptable_with_observations"):
            continue
        st.markdown(f"{decision_badge(s.decision_category)} **{s.domain}** — {s.findings_count} finding(s)")
