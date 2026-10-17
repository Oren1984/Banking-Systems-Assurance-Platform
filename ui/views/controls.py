from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from ui.app_context import page_setup, run_action
from ui.components.badges import domain_label, humanize
from ui.components.charts import count_chart
from ui.components.layout import page_title, require_active_assessment

ctx, principal = page_setup(Permission.VIEW_ASSESSMENTS)
page_title("Control Evaluations", "How each banking-domain control evaluated against the active assessment's evidence.")
result = require_active_assessment(ctx, principal)
evaluations = result.control_evaluations
if not evaluations:
    st.info("No control evaluations were recorded for this assessment.")
    st.stop()

_, catalog = run_action("Loading control catalog", ctx.assessments.get_control_catalog, principal)
catalog = catalog or {}

left, right = st.columns([1, 2], gap="large")
with left:
    with st.container(border=True):
        st.markdown("#### Status distribution")
        count_chart(dict(Counter(ce.status for ce in evaluations)), "Status")
with right:
    domains = sorted({ce.domain for ce in evaluations})
    domain_filter = st.multiselect("Domain", domains, format_func=domain_label)
    statuses = sorted({ce.status for ce in evaluations})
    status_filter = st.multiselect("Status", statuses, format_func=humanize)
    rows = [
        {
            "Domain": domain_label(ce.domain),
            "Control": catalog.get(ce.control_id, (ce.control_id or "N/A", ""))[0],
            "Title": catalog.get(ce.control_id, ("", ""))[1],
            "Status": humanize(ce.status),
            "Findings": len(ce.finding_ids or []),
        }
        for ce in sorted(evaluations, key=lambda c: (c.domain, c.status))
        if (not domain_filter or ce.domain in domain_filter) and (not status_filter or ce.status in status_filter)
    ]
    st.caption(f"{len(rows)} of {len(evaluations)} control results")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
