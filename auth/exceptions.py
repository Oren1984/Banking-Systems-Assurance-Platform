from __future__ import annotations

from core.exceptions import PlatformError, ValidationError

# Authentication / authorization errors (auth/). Kept in their own module
# rather than appended to core/exceptions.py so the core error hierarchy
# stays untouched; every class still derives from core's PlatformError.

GENERIC_LOGIN_FAILURE = (
    "Sign-in failed. Check your username and password and try again. "
    "Repeated failed attempts temporarily lock an account."
)


class AuthenticationError(PlatformError):
    """Login failed. The message is always GENERIC_LOGIN_FAILURE — it never
    says whether the account exists, is locked, or is deactivated."""

    def __init__(self, message: str = GENERIC_LOGIN_FAILURE) -> None:
        super().__init__(message)


class SessionExpiredError(AuthenticationError):
    """The session was idle for longer than SESSION_IDLE_TIMEOUT_MINUTES."""

    def __init__(self) -> None:
        super().__init__("Your session expired after a period of inactivity. Please sign in again.")


class SessionInvalidatedError(AuthenticationError):
    """The account was deactivated, its role changed, or its password was
    reset/changed since this session signed in."""

    def __init__(self) -> None:
        super().__init__("Your session is no longer valid because your account changed. Please sign in again.")


class AuthorizationError(PlatformError):
    """The authenticated user's role does not grant the requested permission."""


class UserAdministrationError(ValidationError):
    """A user-management request was rejected (duplicate username, weak
    password, last-administrator protection, self-modification, ...)."""
