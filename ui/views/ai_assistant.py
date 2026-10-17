from __future__ import annotations

import streamlit as st

from auth.permissions import Permission
from ui.app_context import page_setup, run_action
from ui.components.badges import domain_label
from ui.components.layout import page_title, require_active_assessment

# Optional, advisory AI Assistant (parity with the legacy "AI Assistant
# (Optional)" tab). Every action needs an explicit click and is recorded in
# the audit trail under the signed-in user. The secured agent service has
# no method that changes a finding, score, or review — see
# auth/secured_services.py::SecuredAgentService.

ctx, principal = page_setup(Permission.USE_AI_ASSISTANT)
page_title("AI Assistant (Optional)", "Advisory explanations of existing assessment data. It never makes a decision.")
result = require_active_assessment(ctx, principal)
scan_id = result.scan_id

ok, status = run_action("Loading assistant status", ctx.agent.get_agent_status, principal)
if not ok:
    st.stop()
if status["is_local"]:
    st.info(
        f"**Mode: Local (no external AI provider)** — {status['reason']}. No data leaves this environment. "
        "Responses are deterministic, sanitized restatements of existing assessment data, not AI-generated prose."
    )
else:
    st.warning(
        f"**Mode: External — provider `{status['provider']}`.** Sanitized, size-limited evidence for the action "
        "you trigger **may leave the local environment** and be sent to this provider. Nothing is sent until you click."
    )
st.caption(
    "Output here is advisory and never a scanner finding, a score, or a governance decision — nothing on this page "
    f"changes findings, scores, control evaluations, or finalization status. Actions are recorded as **{principal.username}**."
)
if status["warnings"]:
    with st.expander("Configuration notes"):
        for w in status["warnings"]:
            st.write(f"- {w}")


def _render(response) -> None:
    if response is None:
        st.warning("Nothing to show for this selection.")
        return
    badge = "Local" if response.is_local else f"External — {response.provider_name}"
    if not response.success:
        st.error(f"Provider call failed (fell back to local): {response.error}")
    st.caption(f"[{badge}] {response.disclaimer}")
    st.write(response.content)


tab_explain, tab_domain, tab_ask, tab_exec = st.tabs(
    ["Explain a finding", "Summarize a domain", "Ask about the evidence", "Executive summary"]
)
with tab_explain:
    if result.findings:
        options = {f.id: f"[{f.severity.upper()}] {f.rule_id} — {f.source_relative_path}" for f in result.findings}
        choice = st.selectbox("Finding", list(options), format_func=options.get, key="agent_finding_choice")
        if st.button("Explain this finding", key="agent_explain_btn"):
            ok, response = run_action("Explain", ctx.agent.explain_finding, principal, scan_id, choice)
            if ok:
                _render(response)
    else:
        st.caption("No findings to explain.")
with tab_domain:
    domains = sorted({d for f in result.findings for d in (f.banking_domains or [])} | {s.domain for s in result.scores})
    if domains:
        domain_choice = st.selectbox("Domain", domains, format_func=domain_label, key="agent_domain_choice")
        if st.button("Summarize this domain", key="agent_summarize_btn"):
            ok, response = run_action("Summarize", ctx.agent.summarize_domain, principal, scan_id, domain_choice)
            if ok:
                _render(response)
with tab_ask:
    question = st.text_area("Question", key="agent_question")
    if st.button("Ask", key="agent_ask_btn", disabled=not question.strip()):
        ok, response = run_action("Question could not be processed", ctx.agent.answer_question, principal, scan_id, question)
        if ok:
            _render(response)
with tab_exec:
    if st.button("Generate executive summary", key="agent_exec_btn"):
        ok, response = run_action("Executive summary", ctx.agent.generate_executive_summary, principal, scan_id)
        if ok:
            _render(response)
