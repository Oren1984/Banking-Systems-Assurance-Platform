from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

import streamlit as st

from auth.auth_service import AuthService
from auth.authorizer import Authorizer
from auth.exceptions import AuthenticationError, AuthorizationError, UserAdministrationError
from auth.permissions import Permission
from auth.principal import Principal
from auth.secured_services import SecuredAgentService, SecuredAssessmentService
from auth.user_admin_service import UserAdminService
from core.config import Settings, get_settings
from core.exceptions import GovernanceError
from core.logging import get_logger
from governance.report_sanitizer import sanitize_report
from ui.services.comparison_service import IncompatibleScansError

_logger = get_logger(__name__)

# Shared wiring for the authenticated UI (ui/app.py and ui/views/*).
#
# - AppContext holds the secured services. Pages never import
#   ui/services/* directly for actions; they go through these wrappers, which
#   enforce permissions server-side (auth/secured_services.py).
# - The signed-in Principal lives in st.session_state, which Streamlit keeps
#   server-side per browser session. It holds no password or secret.
# - page_setup() is the per-page guard; run_action() is the single place UI
#   actions translate service errors into user-facing messages.

PRINCIPAL_KEY = "principal"
NOTICE_KEY = "auth_notice"
SCAN_KEY = "current_scan_id"
FLASH_KEY = "flash_message"

# Errors whose messages are written for end users and safe to display.
_USER_FACING_ERRORS = (AuthorizationError, UserAdministrationError, IncompatibleScansError, GovernanceError)


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    auth: AuthService
    authz: Authorizer
    assessments: SecuredAssessmentService
    agent: SecuredAgentService
    users: UserAdminService

    def can(self, principal: Optional[Principal], permission: Permission) -> bool:
        return self.authz.can(principal, permission)


@st.cache_resource(show_spinner=False)
def _build_context(database_url: Optional[str], idle_timeout: int, password_min_length: int) -> AppContext:
    # Keyed on the settings that shape the services, so a changed
    # environment (or a different test database) gets its own instance.
    settings = get_settings()
    auth = AuthService(settings)
    authz = Authorizer(auth)
    return AppContext(
        settings=settings,
        auth=auth,
        authz=authz,
        assessments=SecuredAssessmentService(authz),
        agent=SecuredAgentService(authz),
        users=UserAdminService(authz),
    )


def get_context() -> AppContext:
    s = get_settings()
    return _build_context(s.database_url, s.session_idle_timeout_minutes, s.password_min_length)


def current_principal() -> Optional[Principal]:
    return st.session_state.get(PRINCIPAL_KEY)


def start_session(principal: Principal) -> None:
    st.session_state.clear()
    st.session_state[PRINCIPAL_KEY] = principal


def end_session(notice: Optional[str] = None) -> None:
    st.session_state.clear()
    if notice:
        st.session_state[NOTICE_KEY] = notice


def refresh_session(ctx: AppContext) -> Optional[Principal]:
    """Re-validate the stored session on every rerun (idle timeout, account
    status, session_version). Ends the session on failure."""
    principal = current_principal()
    if principal is None:
        return None
    try:
        principal = ctx.auth.validate_session(principal)
    except AuthenticationError as exc:
        end_session(str(exc))
        return None
    st.session_state[PRINCIPAL_KEY] = principal
    return principal


def operation_failed_message(action: str, exc: Exception) -> str:
    """Log the full (sanitized) exception and return a generic message —
    raw exception text can include internal paths or DB details."""
    _logger.error("ui_operation_failed", action=action, error_type=type(exc).__name__, error=sanitize_report(str(exc)))
    return f"{action} — see application logs for details."


def run_action(action: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Tuple[bool, Any]:
    """Run a secured service call. Returns (ok, result). Shows an error for
    failures; an expired/invalidated session ends the session and reruns
    to the sign-in screen."""
    try:
        return True, fn(*args, **kwargs)
    except AuthenticationError as exc:
        end_session(str(exc))
        st.rerun()
    except AuthorizationError as exc:
        st.error(str(exc))
    except _USER_FACING_ERRORS as exc:
        st.error(f"{action} — {exc}")
    except Exception as exc:  # noqa: BLE001 — surface any failure to the operator, not a crash
        st.error(operation_failed_message(f"{action} failed", exc))
    return False, None


def page_setup(permission: Optional[Permission]) -> Tuple[AppContext, Principal]:
    """Per-page guard. Navigation already hides pages a role cannot use;
    this is the server-side check behind it (audited on denial).
    permission=None means "any signed-in user" (account, help)."""
    ctx = get_context()
    principal = current_principal()
    if principal is None:
        st.stop()
    if permission is None:
        ok, refreshed = run_action("Session check", ctx.auth.validate_session, principal)
    else:
        ok, refreshed = run_action(
            "Access check", ctx.authz.require, principal, permission, f"open this page ({permission.value})"
        )
    if not ok:
        st.stop()
    st.session_state[PRINCIPAL_KEY] = refreshed
    return ctx, refreshed


def active_scan_id() -> Optional[str]:
    return st.session_state.get(SCAN_KEY)


def set_active_scan(scan_id: Optional[str]) -> None:
    st.session_state[SCAN_KEY] = scan_id


def flash(message: str) -> None:
    """Success message that survives the st.rerun() following an action."""
    st.session_state[FLASH_KEY] = message


def show_flash() -> None:
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)
