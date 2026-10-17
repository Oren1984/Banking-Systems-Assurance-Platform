from __future__ import annotations

from typing import Optional

import streamlit as st

from auth.permissions import Permission
from ui.app_context import get_context, refresh_session, show_flash
from ui.components.layout import render_header, render_sidebar, render_sidebar_footer
from ui.components.theme import apply_theme

# The authenticated multipage application. Run through either entrypoint —
#     streamlit run ui/app.py            (primary)
#     streamlit run ui/streamlit_app.py  (legacy command, same app)
# Both live in ui/, so the page paths below resolve identically.
#
# Every run: (1) re-validate the stored session (idle timeout, account
# status, session_version); (2) with no valid session, ONLY the sign-in page
# exists in navigation; (3) a session with a pending password change sees
# only the change-password page; (4) otherwise navigation is built from the
# signed-in role's permissions, so pages a role cannot use are not even
# routable. Each page then re-checks its permission server-side
# (ui/app_context.py::page_setup) and every action goes through the secured
# service layer (auth/secured_services.py).
#
# Pages live in ui/views/ (not ui/pages/) so Streamlit's automatic
# multipage discovery can never expose a page outside this gate.

P = Permission

# (section, script, title, material icon, required permission or None = any signed-in user)
PAGES = [
    ("Overview", "views/dashboard.py", "Dashboard", ":material/dashboard:", P.VIEW_ASSESSMENTS),
    ("Assessments", "views/assessments.py", "Run & History", ":material/play_circle:", P.VIEW_ASSESSMENTS),
    ("Assessments", "views/findings.py", "Findings", ":material/bug_report:", P.VIEW_ASSESSMENTS),
    ("Assessments", "views/controls.py", "Controls", ":material/rule:", P.VIEW_ASSESSMENTS),
    ("Assessments", "views/compare.py", "Compare", ":material/compare_arrows:", P.VIEW_ASSESSMENTS),
    ("Assessments", "views/quick_scan.py", "Quick Scan", ":material/bolt:", P.RUN_QUICK_SCAN),
    ("Assessments", "views/ai_assistant.py", "AI Assistant", ":material/smart_toy:", P.USE_AI_ASSISTANT),
    ("Governance", "views/review_queue.py", "Review Queue", ":material/fact_check:", P.VIEW_ASSESSMENTS),
    ("Governance", "views/reports.py", "Reports", ":material/download:", P.EXPORT_REPORTS),
    ("Governance", "views/audit_log.py", "Audit Log", ":material/history:", P.VIEW_AUDIT_LOG),
    ("Administration", "views/users.py", "Users", ":material/group:", P.MANAGE_USERS),
    ("Administration", "views/system.py", "System", ":material/settings:", P.VIEW_SYSTEM_INFO),
    ("Account", "views/account.py", "My Account", ":material/person:", None),
    ("Account", "views/help.py", "Help & About", ":material/help:", None),
]


def _allowed(ctx, principal, permission: Optional[Permission]) -> bool:
    return permission is None or ctx.can(principal, permission)


def run_app() -> None:
    st.set_page_config(page_title="Banking Systems Assurance Platform", page_icon="🛡️", layout="wide")
    apply_theme()
    ctx = get_context()
    if not ctx.settings.database_url:
        st.error(
            "DATABASE_URL is not configured. Sign-in, roles, and the audit trail require the "
            "platform database — see README.md (\"Run it\")."
        )
        st.stop()

    principal = refresh_session(ctx)
    if principal is None:
        st.navigation([st.Page("views/login.py", title="Sign in", icon=":material/login:")], position="hidden").run()
        return

    if principal.must_change_password:
        render_header(ctx, principal)
        st.navigation([st.Page("views/account.py", title="Change password")], position="hidden").run()
        return

    sections: dict = {}
    for section, script, title, icon, permission in PAGES:
        if _allowed(ctx, principal, permission):
            sections.setdefault(section, []).append(st.Page(script, title=title, icon=icon))
    nav = st.navigation(sections)
    render_sidebar(ctx, principal)
    render_header(ctx, principal)
    show_flash()
    nav.run()
    render_sidebar_footer()
