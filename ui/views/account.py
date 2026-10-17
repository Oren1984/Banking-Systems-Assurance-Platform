from __future__ import annotations

import streamlit as st

from auth.permissions import ROLE_PERMISSIONS
from ui.app_context import PRINCIPAL_KEY, flash, page_setup, run_action
from ui.components.badges import humanize, role_badge
from ui.components.layout import page_title

# Own account: profile, permissions, and password change. Also the only
# page reachable while an admin-issued temporary password is pending.

ctx, principal = page_setup(None)
forced = principal.must_change_password
page_title("Change password" if forced else "My Account", "Your profile and sign-in credentials.")

if forced:
    st.warning("Your password was set by an administrator. Choose a new password to continue.")
else:
    with st.container(border=True):
        st.markdown(f"**{principal.display_name}** {role_badge(principal.role.value)}")
        st.caption(f"Username: {principal.username} · signed in at {str(principal.authenticated_at)[:16]} UTC")
        st.markdown("**What your role allows:** " + ", ".join(humanize(p.value) for p in sorted(ROLE_PERMISSIONS[principal.role], key=lambda p: p.value)))

with st.container(border=True):
    st.markdown("#### Change password")
    with st.form("change_password_form", clear_on_submit=True):
        current = st.text_input("Current password", type="password", autocomplete="current-password")
        new = st.text_input("New password", type="password", autocomplete="new-password", help=f"At least {ctx.settings.password_min_length} characters; must not contain your username.")
        repeat = st.text_input("Repeat new password", type="password", autocomplete="new-password")
        submitted = st.form_submit_button("Change password", type="primary")
    if submitted:
        if new != repeat:
            st.error("The new passwords do not match.")
        else:
            ok, updated = run_action("Changing password", ctx.auth.change_own_password, principal, current, new)
            if ok:
                st.session_state[PRINCIPAL_KEY] = updated
                flash("Password changed.")
                st.rerun()
