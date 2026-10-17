from __future__ import annotations

import pandas as pd
import streamlit as st

from auth.permissions import Permission
from models.enums import Role
from ui.app_context import flash, page_setup, run_action
from ui.components.layout import page_title

# User administration (ADMIN only). All rules — no self-modification, no
# removing the last active admin, session invalidation, password policy —
# are enforced in auth/user_admin_service.py; this page only collects input.

ctx, principal = page_setup(Permission.MANAGE_USERS)
page_title("Users", "Create accounts, assign roles, and control access. Accounts are deactivated, never deleted.")

ok, users = run_action("Loading users", ctx.users.list_users, principal)
if not ok:
    st.stop()

st.dataframe(
    pd.DataFrame(
        [
            {
                "Username": u.username,
                "Name": u.display_name,
                "Role": u.role.value.title(),
                "Active": u.is_active,
                "Locked": u.is_locked,
                "Must change password": u.must_change_password,
                "Last sign-in (UTC)": str(u.last_login_at)[:16] if u.last_login_at else "never",
            }
            for u in users
        ]
    ),
    hide_index=True,
    width="stretch",
)

ROLE_HELP = (
    "Employee: run and view assessments, AI Assistant. "
    "Manager: + review findings, override scores, export, audit log. "
    "Admin: manage users, export, audit log, system info — no governance decisions."
)
min_len = ctx.settings.password_min_length

tab_create, tab_manage = st.tabs(["Create user", "Manage user"])
with tab_create:
    with st.form("create_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        username = c1.text_input("Username", help="3–64 characters: lowercase letters, digits, '.', '_' or '-'.")
        display_name = c2.text_input("Display name")
        role = st.selectbox("Role", [r.value for r in Role], format_func=str.title, index=2, help=ROLE_HELP)
        c3, c4 = st.columns(2)
        password = c3.text_input("Temporary password", type="password", help=f"At least {min_len} characters.")
        confirm = c4.text_input("Repeat temporary password", type="password")
        st.caption("The user must choose a new password at first sign-in.")
        submitted = st.form_submit_button("Create user", type="primary")
    if submitted:
        if password != confirm:
            st.error("The passwords do not match.")
        else:
            ok, created = run_action("Creating user", ctx.users.create_user, principal, username, display_name, Role(role), password)
            if ok:
                flash(f"User '{created.username}' created with role {created.role.value}.")
                st.rerun()

with tab_manage:
    others = [u for u in users if u.user_id != principal.user_id]
    if not others:
        st.caption("There are no other accounts yet.")
        st.stop()
    by_id = {u.user_id: u for u in others}
    target_id = st.selectbox(
        "Account",
        list(by_id),
        format_func=lambda i: f"{by_id[i].username} — {by_id[i].role.value} ({'active' if by_id[i].is_active else 'inactive'})",
    )
    target = by_id[target_id]
    st.caption("You cannot change your own role or status here. Changes sign the affected user out of any open session.")

    col_role, col_status = st.columns(2)
    with col_role:
        with st.container(border=True):
            st.markdown("**Role**")
            roles = [r.value for r in Role]
            new_role = st.selectbox("New role", roles, index=roles.index(target.role.value), format_func=str.title, key=f"role_{target.user_id}", help=ROLE_HELP)
            if st.button("Update role", disabled=new_role == target.role.value, key=f"role_btn_{target.user_id}"):
                ok, updated = run_action("Changing role", ctx.users.change_role, principal, target.user_id, Role(new_role))
                if ok:
                    flash(f"{updated.username} is now {updated.role.value}.")
                    st.rerun()
    with col_status:
        with st.container(border=True):
            st.markdown("**Access**")
            action = "Deactivate" if target.is_active else "Activate"
            confirm_status = st.checkbox(f"Confirm: {action.lower()} {target.username}", key=f"status_confirm_{target.user_id}")
            if st.button(action, disabled=not confirm_status, key=f"status_btn_{target.user_id}"):
                ok, updated = run_action(f"{action} user", ctx.users.set_active, principal, target.user_id, not target.is_active)
                if ok:
                    flash(f"{updated.username} {'activated' if updated.is_active else 'deactivated'}.")
                    st.rerun()

    with st.form(f"reset_form_{target.user_id}", clear_on_submit=True):
        st.markdown("**Reset password**")
        c1, c2 = st.columns(2)
        temp = c1.text_input("Temporary password", type="password", help=f"At least {min_len} characters.")
        temp_confirm = c2.text_input("Repeat temporary password", type="password")
        st.caption("Also clears a lockout. The user must choose a new password at next sign-in.")
        reset = st.form_submit_button("Reset password")
    if reset:
        if temp != temp_confirm:
            st.error("The passwords do not match.")
        else:
            ok, updated = run_action("Resetting password", ctx.users.reset_password, principal, target.user_id, temp)
            if ok:
                flash(f"Temporary password set for {updated.username}.")
                st.rerun()
