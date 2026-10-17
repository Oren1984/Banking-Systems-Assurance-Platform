from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from ui.app_context import page_setup, run_action
from ui.components.badges import humanize
from ui.components.layout import page_title

ctx, principal = page_setup(Permission.VIEW_AUDIT_LOG)
page_title("Audit Log", "Platform-wide, append-only record of assessments, governance decisions, sign-ins, and account changes.")

limit = st.segmented_control("Show latest", [100, 500, 2000], default=500, format_func=lambda n: f"{n} events")
ok, events = run_action("Loading audit log", ctx.assessments.get_platform_audit_log, principal, limit or 500)
if not ok:
    st.stop()
if not events:
    st.info("No audit events recorded yet.")
    st.stop()

c1, c2, c3 = st.columns([2, 1, 1])
types = c1.multiselect("Event type", sorted({e.event_type for e in events}), format_func=humanize)
actor = c2.text_input("Actor contains")
scan = c3.text_input("Scan ID contains")

rows = [
    {
        "Time (UTC)": str(e.created_at)[:19],
        "Event": humanize(e.event_type),
        "Actor": e.actor,
        "Summary": e.summary,
        "Scan": e.scan_id or "",
        "Details": json.dumps(e.payload, default=str) if e.payload else "",
    }
    for e in events
    if (not types or e.event_type in types)
    and (not actor or actor.lower() in e.actor.lower())
    and (not scan or scan.lower() in (e.scan_id or "").lower())
]
st.caption(f"{len(rows)} of {len(events)} loaded events. Entries are never edited or deleted.")
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=560)
