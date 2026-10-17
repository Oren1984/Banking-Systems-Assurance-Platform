from __future__ import annotations

import html
from typing import List, Optional

import streamlit as st

from auth.principal import Principal
from storage.db.session import check_database_connectivity
from ui.app_context import AppContext, active_scan_id, end_session, run_action, set_active_scan
from ui.components.badges import badge, role_badge

# Page chrome shared by every authenticated page: header (identity, role,
# sign-out, live system status), the sidebar's active-assessment picker,
# and consistent empty states.

FOOTER = "Designed and developed by Oren Salami"


@st.cache_data(ttl=15, show_spinner=False)
def _database_reachable(database_url: Optional[str]) -> bool:
    # Cached so the probe does not run on every rerun.
    return check_database_connectivity(database_url)


def status_badges(ctx: AppContext) -> List[str]:
    s = ctx.settings
    if not s.database_url:
        db = badge("Database: not configured", "red")
    elif _database_reachable(s.database_url):
        db = badge("Database: connected", "green")
    else:
        db = badge("Database: unreachable", "red")
    return [
        badge("Read-only", "blue"),
        badge("Local-only" if s.local_only_mode else "Local-only: off", "green" if s.local_only_mode else "orange"),
        badge(
            "External AI providers: disabled" if not s.external_providers_enabled else "External AI providers: enabled",
            "gray" if not s.external_providers_enabled else "orange",
        ),
        badge(f"Vector backend: {s.vector_backend}", "gray"),
        db,
    ]


def _sign_out(ctx: AppContext, principal: Principal) -> None:
    try:
        ctx.auth.logout(principal)
    finally:
        end_session("You have signed out.")


def render_header(ctx: AppContext, principal: Principal) -> None:
    left, right = st.columns([5, 3], vertical_alignment="center")
    with left:
        st.markdown('<span class="bsap-brand">Banking Systems Assurance Platform</span>', unsafe_allow_html=True)
        st.markdown(" ".join(status_badges(ctx)))
    with right:
        user_col, btn_col = st.columns([3, 2], vertical_alignment="center")
        # display_name is admin-entered free text: HTML-escape it because this
        # line is rendered with unsafe_allow_html (for the muted username).
        user_col.markdown(
            f"**{html.escape(principal.display_name)}** &nbsp; {role_badge(principal.role.value)}  \n"
            f'<span class="bsap-muted">@{html.escape(principal.username)}</span>',
            unsafe_allow_html=True,
        )
        btn_col.button(
            "Sign out", key="header_sign_out", icon=":material/logout:", on_click=_sign_out, args=(ctx, principal), width="content"
        )
    st.divider()


def render_sidebar(ctx: AppContext, principal: Principal) -> None:
    with st.sidebar:
        st.markdown('<span class="bsap-brand">🛡️ Assurance Platform</span>', unsafe_allow_html=True)
        st.caption("Read-only assessment and governance")
        ok, scans = run_action("Loading assessments", ctx.assessments.list_recent_scans, principal, 50)
        scans = scans or []
        if scans:
            labels = {s.scan_id: scan_label(s) for s in scans}
            ids = list(labels)
            current = active_scan_id()
            if current not in labels:
                current = ids[0]
                set_active_scan(current)
            # Keyed on the current selection so a page that changes the active
            # assessment (e.g. after a run) is reflected here on the next rerun.
            choice = st.selectbox(
                "Active assessment",
                ids,
                index=ids.index(current),
                format_func=lambda i: labels[i],
                key=f"sidebar_scan_picker_{current}",
                help="Pages such as Dashboard, Findings and Review Queue show this assessment.",
            )
            if choice != current:
                set_active_scan(choice)
                st.rerun()
        else:
            st.caption("No assessments yet.")


def render_sidebar_footer() -> None:
    with st.sidebar:
        st.divider()
        st.caption(FOOTER)


def scan_label(scan) -> str:
    source = scan.source_path.replace("\\", "/").rstrip("/").split("/")[-1] or scan.source_path
    created = scan.created_at[:16].replace("T", " ") if scan.created_at else "?"
    return f"{created} · {source} · {scan.total_findings} findings"


def empty_state(title: str, hint: str, link_page: Optional[str] = None, link_label: Optional[str] = None) -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.caption(hint)
        if link_page and link_label:
            st.page_link(link_page, label=link_label, icon=":material/arrow_forward:")


def require_active_assessment(ctx: AppContext, principal: Principal):
    """Load the sidebar's active assessment, or render an empty state and
    stop the page."""
    scan_id = active_scan_id()
    if not scan_id:
        empty_state(
            "No assessment selected",
            "Run a Full Assessment, or pick an existing one from 'Active assessment' in the sidebar.",
            "views/assessments.py",
            "Go to Run & History",
        )
        st.stop()
    ok, result = run_action("Loading assessment", ctx.assessments.get_assessment, principal, scan_id)
    if not ok:
        st.stop()
    if result is None:
        set_active_scan(None)
        st.warning("The selected assessment no longer exists. Pick another one in the sidebar.")
        st.stop()
    return result


def page_title(title: str, subtitle: str) -> None:
    st.markdown(f"## {title}")
    st.caption(subtitle)
