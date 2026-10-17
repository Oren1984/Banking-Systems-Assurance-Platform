from __future__ import annotations

import streamlit as st

from auth.exceptions import AuthenticationError
from ui.app_context import NOTICE_KEY, get_context, operation_failed_message, start_session

# Sign-in screen — the only page that exists without a valid session.
# Failure messages are always the generic AuthenticationError text: never
# "unknown user", "locked", or "deactivated". The form clears on submit so
# the password does not linger in widget state.

ctx = get_context()
notice = st.session_state.pop(NOTICE_KEY, None)

_, middle, _ = st.columns([1, 1.4, 1])
with middle:
    st.write("")
    st.markdown("<h2 class='bsap-login-title'>🛡️ Banking Systems Assurance Platform</h2>", unsafe_allow_html=True)
    st.markdown("<div class='bsap-login-sub'>Read-only assessment &amp; governance — sign in to continue</div>", unsafe_allow_html=True)
    if notice:
        st.info(notice)
    with st.container(border=True):
        with st.form("login_form", clear_on_submit=True, border=False):
            username = st.text_input("Username", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            if not username.strip() or not password:
                st.error("Enter your username and password.")
            else:
                try:
                    principal = ctx.auth.login(username, password)
                except AuthenticationError as exc:
                    st.error(str(exc))
                except Exception as exc:  # noqa: BLE001 — never show raw errors on the sign-in page
                    st.error(operation_failed_message("Sign-in is temporarily unavailable", exc))
                else:
                    start_session(principal)
                    st.rerun()
    st.caption(
        "Accounts are created by an administrator — there is no self-registration. "
        f"Sessions end after {ctx.settings.session_idle_timeout_minutes} minutes of inactivity. "
        "This local deployment is reachable only from this computer."
    )
