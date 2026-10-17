from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.auth_service import AuthService
from auth.permissions import ROLE_PERMISSIONS, Permission
from models.enums import Role
from ui.app_context import page_setup
from ui.components.badges import humanize
from ui.components.layout import page_title, status_badges

ctx, principal = page_setup(Permission.VIEW_SYSTEM_INFO)
page_title("System", "Runtime configuration and security posture of this deployment (read-only).")
s = ctx.settings

st.markdown(" ".join(status_badges(ctx)))

left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True):
        st.markdown("#### Configuration")
        st.dataframe(
            pd.DataFrame(
                [
                    ("Application version", s.app_version),
                    ("Environment", s.environment),
                    ("Local-only mode", s.local_only_mode),
                    ("External providers enabled", s.external_providers_enabled),
                    ("Vector backend", s.vector_backend),
                    ("AI Assistant provider", f"{s.agent_provider} (feature {'on' if s.agent_enabled else 'off'})"),
                    ("Allowed scan paths", ", ".join(s.allowed_scan_paths) or "(none — scanning disabled)"),
                    ("Max file size scanned", f"{s.max_scan_file_size_bytes:,} bytes"),
                    ("Data retention (days)", s.data_retention_days if s.data_retention_days is not None else "not configured"),
                ],
                columns=["Setting", "Value"],
            ).astype(str),
            hide_index=True,
            width="stretch",
        )
with right:
    with st.container(border=True):
        st.markdown("#### Access control")
        st.markdown(
            f"- Passwords: salted scrypt (N=2¹⁷, r=8, p=1), minimum {s.password_min_length} characters\n"
            f"- Lockout: {AuthService.MAX_FAILED_ATTEMPTS} failed attempts → "
            f"{int(AuthService.LOCKOUT_DURATION.total_seconds() // 60)} minutes\n"
            f"- Idle session timeout: {s.session_idle_timeout_minutes} minutes\n"
            "- Sessions are invalidated on deactivation, role change, and password reset\n"
            "- Every denied action is recorded in the audit log\n"
            "- Network exposure: localhost only (Docker ports bound to 127.0.0.1). Configure HTTPS before "
            "allowing access from any other computer."
        )
    with st.container(border=True):
        st.markdown("#### Role permissions")
        perms = list(Permission)
        st.dataframe(
            pd.DataFrame(
                {role.value.title(): ["✓" if p in ROLE_PERMISSIONS[role] else "—" for p in perms] for role in Role},
                index=[humanize(p.value) for p in perms],
            ),
            width="stretch",
        )
