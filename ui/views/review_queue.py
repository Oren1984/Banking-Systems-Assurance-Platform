from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from models.enums import DecisionCategory, HumanReviewStatus
from ui.app_context import flash, page_setup, run_action
from ui.components.badges import decision_badge, domain_label, humanize, severity_badge, severity_rank
from ui.components.layout import page_title, require_active_assessment
from ui.services.comparison_service import effective_scores

# Governance: finalization status, finding review, score override, and the
# assessment's audit trail (parity with the legacy "Governance" tab).
# Everyone who can view assessments sees status and the pending queue; the
# decision forms render only for roles holding REVIEW_FINDINGS /
# OVERRIDE_SCORES (MANAGER), and the secured service enforces the same
# rule server-side. The reviewer recorded is always the signed-in user —
# there is no identity field to type into.

ctx, principal = page_setup(Permission.VIEW_ASSESSMENTS)
page_title("Review Queue", "Human-in-the-loop governance for the active assessment.")
result = require_active_assessment(ctx, principal)
scan_id = result.scan_id
can_review = ctx.can(principal, Permission.REVIEW_FINDINGS)
can_override = ctx.can(principal, Permission.OVERRIDE_SCORES)

ok, check = run_action("Finalization check", ctx.assessments.check_finalization, principal, scan_id)
with st.container(border=True):
    st.markdown("#### Finalization status")
    if ok and check.can_finalize:
        st.success("This assessment CAN be finalized — no high/critical-risk domain has a pending review.")
    elif ok:
        st.error("This assessment CANNOT be finalized yet:")
        for blocker in check.blockers:
            st.write(f"- {blocker.reason}")

if not (can_review or can_override):
    st.info(
        "You have read-only access to governance. Finding reviews and score overrides are made by a Manager"
        + (" — administrators manage accounts but do not make governance decisions." if principal.role.value == "admin" else ".")
    )

pending = sorted(
    [f for f in result.findings if f.human_review_status == HumanReviewStatus.PENDING.value],
    key=lambda f: (severity_rank(f.severity), f.rule_id),
)

tab_names = ["Review findings", "Override a domain score"]
if ctx.can(principal, Permission.VIEW_AUDIT_LOG):
    tab_names.append("Audit trail")
tabs = st.tabs(tab_names)

with tabs[0]:
    st.write(f"{len(pending)} of {len(result.findings)} findings are pending review.")
    if not pending:
        st.success("Nothing left to review.")
    elif not can_review:
        st.dataframe(
            pd.DataFrame(
                [{"Severity": f.severity.upper(), "Rule": f.rule_id, "File": f.source_relative_path, "Line": f.line_start} for f in pending]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        options = {f.id: f for f in pending}
        finding_id = st.selectbox(
            "Pending finding",
            list(options),
            format_func=lambda i: f"[{options[i].severity.upper()}] {options[i].rule_id} — {options[i].source_relative_path}:{options[i].line_start}",
            key="review_finding_choice",
        )
        f = options[finding_id]
        with st.container(border=True):
            st.markdown(f"{severity_badge(f.severity)} **{f.title}**")
            st.code(f.masked_evidence, language=None)
            st.caption(f"Recommended action (advisory): {f.recommended_action}")
        with st.form("review_form", clear_on_submit=True):
            decision = st.segmented_control(
                "Decision",
                [HumanReviewStatus.APPROVED.value, HumanReviewStatus.REJECTED.value, HumanReviewStatus.OVERRIDDEN.value],
                format_func=humanize,
                default=HumanReviewStatus.APPROVED.value,
                key="review_decision",
            )
            reason = st.text_area("Reviewer comment / reason (required for 'overridden')", key="review_reason")
            st.caption(f"Recorded in the append-only audit trail as **{principal.username}**.")
            submitted = st.form_submit_button("Submit review", type="primary")
        if submitted:
            if not decision:
                st.error("Choose a decision.")
            else:
                ok, _ = run_action(
                    "Recording review",
                    ctx.assessments.review_finding,
                    principal,
                    finding_id,
                    HumanReviewStatus(decision),
                    reason or None,
                )
                if ok:
                    flash(f"Review recorded ({humanize(decision)}) — written to the append-only audit trail.")
                    st.rerun()

with tabs[1]:
    current = effective_scores(result.scores)
    if not current:
        st.caption("No domain scores to override.")
    elif not can_override:
        for domain, s in sorted(current.items()):
            st.markdown(f"{decision_badge(s.decision_category)} **{domain_label(domain)}** — weighted {s.weighted_score}")
    else:
        st.caption("An override adds a new score row; the original is preserved and stays in the score history.")
        score_ids = {s.id: s for s in current.values()}
        score_id = st.selectbox(
            "Domain score",
            list(score_ids),
            format_func=lambda i: f"{domain_label(score_ids[i].domain)} — {humanize(score_ids[i].decision_category)} (weighted={score_ids[i].weighted_score})",
            key="override_score_choice",
        )
        with st.form("override_form", clear_on_submit=True):
            new_category = st.selectbox("New decision category", [c.value for c in DecisionCategory], format_func=humanize)
            justification = st.text_area("Justification (required)")
            confirmed = st.checkbox(f"I confirm this override, recorded under my name ({principal.username}).")
            submitted = st.form_submit_button("Submit override", type="primary")
        if submitted:
            chosen = score_ids[score_id]
            if not justification.strip():
                st.error("A justification is required to override a score.")
            elif not confirmed:
                st.error("Confirm the override before submitting.")
            else:
                ok, _ = run_action(
                    "Recording override",
                    ctx.assessments.override_score,
                    principal,
                    chosen.id,
                    scan_id,
                    chosen.domain,
                    DecisionCategory(new_category),
                    justification,
                )
                if ok:
                    flash("Override recorded as a new score row (the original is preserved, never mutated).")
                    st.rerun()

if len(tabs) > 2:
    with tabs[2]:
        ok, events = run_action("Loading audit trail", ctx.assessments.get_audit_trail, principal, scan_id)
        if ok:
            st.caption("Actors are authenticated platform users; 'system' marks automated pipeline steps.")
            st.dataframe(
                pd.DataFrame(
                    [
                        {"Time (UTC)": str(e.created_at)[:19], "Event": humanize(e.event_type), "Actor": e.actor, "Summary": e.summary}
                        for e in events
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
