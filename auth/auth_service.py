from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from auth.db import open_session
from auth.exceptions import (
    AuthenticationError,
    SessionExpiredError,
    SessionInvalidatedError,
    UserAdministrationError,
)
from auth.password_hasher import PasswordHasher
from auth.principal import Principal
from auth.user_repository import UserRepository
from core.config import Settings
from governance.audit_trail import AuditEventInput
from models.enums import AuthEventType, Role
from storage.db.models.user import User
from storage.db.repositories import AuditRepository

# Authentication and session lifecycle. Every outcome that matters for
# accountability — successful and failed sign-in, lockout, logout, expiry,
# invalidation, password change — is written through the existing
# append-only, sanitized AuditRepository. Audit payloads carry reason codes
# and identifiers only: never a password, a hash, or a session secret.
#
# Failed sign-in is deliberately indistinguishable to the caller: unknown
# account, wrong password, locked, and deactivated all raise the same
# AuthenticationError with the same generic message, and an unknown
# account still pays the cost of one scrypt verification so response time
# does not reveal whether it exists.

ANONYMOUS_ACTOR = "anonymous"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes even for timezone-aware columns;
    PostgreSQL returns aware ones. Normalize so comparisons work on both."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def record_auth_event(
    session: Session,
    event_type: AuthEventType,
    actor: str,
    summary: str,
    payload: Optional[Dict[str, Any]] = None,
    scan_id: Optional[str] = None,
) -> None:
    # AuditEventInput is typed for AuditEventType, but build_audit_event()
    # only reads `.value` — AuthEventType values are stored the same way.
    AuditRepository(session).record(
        AuditEventInput(
            event_type=event_type,  # type: ignore[arg-type]
            actor=actor,
            summary=summary,
            scan_id=scan_id,
            payload=payload or {},
        )
    )


def validate_new_password(password: str, username: str, min_length: int) -> None:
    if len(password) < min_length:
        raise UserAdministrationError(f"Password must be at least {min_length} characters long.")
    if len(password) > 256:
        raise UserAdministrationError("Password must be at most 256 characters long.")
    if username and username.strip().lower() in password.lower():
        raise UserAdministrationError("Password must not contain the username.")
    if len(set(password)) < 4:
        raise UserAdministrationError("Password is too simple — use a longer phrase with varied characters.")


class AuthService:
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def __init__(
        self,
        settings: Settings,
        hasher: Optional[PasswordHasher] = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._settings = settings
        self._hasher = hasher or PasswordHasher()
        self._clock = clock
        # Verified against when the account does not exist, so the unknown-
        # account path costs the same as a wrong-password path.
        self._dummy_hash = self._hasher.hash("timing-equalization-placeholder")

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def hasher(self) -> PasswordHasher:
        return self._hasher

    @property
    def idle_timeout(self) -> timedelta:
        return timedelta(minutes=self._settings.session_idle_timeout_minutes)

    def now(self) -> datetime:
        return self._clock()

    def session(self) -> Session:
        return open_session(self._settings)

    # ------------------------------------------------------------------ #
    # Sign-in / sign-out
    # ------------------------------------------------------------------ #

    def login(self, username: str, password: str) -> Principal:
        now = self.now()
        with self.session() as session:
            user = UserRepository(session).get_by_username(username or "")
            if user is None:
                self._hasher.verify(password or "", self._dummy_hash)
                self._fail(session, None, "unknown_account")

            locked_until = as_utc(user.locked_until)
            if locked_until is not None and now < locked_until:
                self._hasher.verify(password or "", self._dummy_hash)
                self._fail(session, user, "account_locked")
            if not user.is_active:
                self._hasher.verify(password or "", self._dummy_hash)
                self._fail(session, user, "account_inactive")

            if not self._hasher.verify(password or "", user.password_hash):
                user.failed_attempts = (user.failed_attempts or 0) + 1
                if user.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                    user.locked_until = now + self.LOCKOUT_DURATION
                    user.failed_attempts = 0
                    record_auth_event(
                        session,
                        AuthEventType.USER_LOCKED_OUT,
                        user.username,
                        f"Account locked for {int(self.LOCKOUT_DURATION.total_seconds() // 60)} minutes "
                        f"after {self.MAX_FAILED_ATTEMPTS} failed sign-in attempts",
                        {"locked_until": user.locked_until.isoformat()},
                    )
                self._fail(session, user, "invalid_password")

            user.failed_attempts = 0
            user.locked_until = None
            user.last_login_at = now
            record_auth_event(session, AuthEventType.USER_LOGIN, user.username, "Signed in", {"role": user.role})
            return self._principal_for(user, now)

    def _fail(self, session: Session, user: Optional[User], reason: str) -> None:
        record_auth_event(
            session,
            AuthEventType.USER_LOGIN_FAILED,
            user.username if user is not None else ANONYMOUS_ACTOR,
            "Sign-in attempt failed",
            {"reason": reason},
        )
        raise AuthenticationError()

    def logout(self, principal: Principal) -> None:
        with self.session() as session:
            record_auth_event(session, AuthEventType.USER_LOGOUT, principal.username, "Signed out")

    # ------------------------------------------------------------------ #
    # Session validation — called on every page load AND every protected
    # service call (auth/secured_services.py), so a stale session cannot
    # keep acting after deactivation, role change, or password reset.
    # ------------------------------------------------------------------ #

    def validate_session(self, principal: Principal) -> Principal:
        now = self.now()
        with self.session() as session:
            if now - as_utc(principal.last_activity_at) > self.idle_timeout:
                record_auth_event(
                    session,
                    AuthEventType.SESSION_EXPIRED,
                    principal.username,
                    f"Session expired after {self._settings.session_idle_timeout_minutes} minutes of inactivity",
                )
                raise SessionExpiredError()
            user = UserRepository(session).get_by_id(principal.user_id)
            if user is None or not user.is_active or user.session_version != principal.session_version:
                record_auth_event(
                    session,
                    AuthEventType.SESSION_INVALIDATED,
                    principal.username,
                    "Session rejected: account changed since sign-in",
                    {"reason": "inactive" if user is not None and not user.is_active else "account_changed"},
                )
                raise SessionInvalidatedError()
            return replace(
                principal,
                display_name=user.display_name,
                role=Role(user.role),
                must_change_password=user.must_change_password,
                last_activity_at=now,
            )

    def change_own_password(self, principal: Principal, current_password: str, new_password: str) -> Principal:
        principal = self.validate_session(principal)
        with self.session() as session:
            user = UserRepository(session).get_by_id(principal.user_id)
            if user is None or not self._hasher.verify(current_password or "", user.password_hash):
                raise UserAdministrationError("Current password is incorrect.")
            if self._hasher.verify(new_password, user.password_hash):
                raise UserAdministrationError("The new password must differ from the current password.")
            validate_new_password(new_password, user.username, self._settings.password_min_length)
            user.password_hash = self._hasher.hash(new_password)
            user.must_change_password = False
            user.session_version += 1
            record_auth_event(session, AuthEventType.PASSWORD_CHANGED, user.username, "Changed own password")
            return self._principal_for(user, self.now(), authenticated_at=principal.authenticated_at)

    @staticmethod
    def _principal_for(user: User, now: datetime, authenticated_at: Optional[datetime] = None) -> Principal:
        return Principal(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=Role(user.role),
            session_version=user.session_version,
            authenticated_at=authenticated_at or now,
            last_activity_at=now,
            must_change_password=user.must_change_password,
        )


__all__ = [
    "ANONYMOUS_ACTOR",
    "AuthService",
    "as_utc",
    "record_auth_event",
    "utc_now",
    "validate_new_password",
]
