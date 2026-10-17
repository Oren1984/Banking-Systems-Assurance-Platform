from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from auth.auth_service import AuthService, as_utc, record_auth_event, validate_new_password
from auth.authorizer import Authorizer
from auth.exceptions import UserAdministrationError
from auth.permissions import Permission
from auth.principal import Principal
from auth.user_repository import UserRepository, normalize_username
from models.enums import AuthEventType, Role
from storage.db.models.user import User

# User administration (ADMIN only, enforced through Authorizer.require).
#
# Invariants enforced here, independent of the UI:
# - users are never deleted — deactivation only (audit history stays
#   attributable);
# - an administrator cannot change their own role or deactivate themselves;
# - no action may leave the platform without at least one active ADMIN;
# - deactivation, role change, and password reset each bump the user's
#   session_version, so that user's existing sessions are rejected on their
#   next action (auth/auth_service.py::validate_session);
# - an admin-set password is temporary: must_change_password is set, and
#   the user can do nothing else until they change it.
#
# `bootstrap_user` is the only path that creates a user without an
# authenticated principal; it is called solely by scripts/create_admin.py
# and scripts/seed_demo_users.py (operator shell access to the host is the
# trust boundary there).

_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


@dataclass(frozen=True)
class UserView:
    """What the UI is allowed to see about an account — no password hash,
    no session_version."""

    user_id: str
    username: str
    display_name: str
    role: Role
    is_active: bool
    is_locked: bool
    must_change_password: bool
    last_login_at: Optional[datetime]
    created_at: Optional[datetime]


class UserAdminService:
    def __init__(self, authorizer: Authorizer) -> None:
        self._authz = authorizer
        self._auth: AuthService = authorizer.auth_service

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def list_users(self, principal: Principal) -> List[UserView]:
        self._authz.require(principal, Permission.MANAGE_USERS, "view user accounts")
        with self._auth.session() as session:
            return [self._view(u) for u in UserRepository(session).list_all()]

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def create_user(
        self,
        principal: Principal,
        username: str,
        display_name: str,
        role: Role,
        initial_password: str,
        must_change_password: bool = True,
    ) -> UserView:
        principal = self._authz.require(principal, Permission.MANAGE_USERS, "create user accounts")
        with self._auth.session() as session:
            user = self._create(session, username, display_name, role, initial_password, must_change_password)
            record_auth_event(
                session,
                AuthEventType.USER_CREATED,
                principal.username,
                f"Created user '{user.username}' with role '{user.role}'",
                {"target_user": user.username, "role": user.role},
            )
            return self._view(user)

    def change_role(self, principal: Principal, user_id: str, new_role: Role) -> UserView:
        principal = self._authz.require(principal, Permission.MANAGE_USERS, "change user roles")
        with self._auth.session() as session:
            repo = UserRepository(session)
            user = self._target(repo, principal, user_id, "change your own role")
            old_role = user.role
            if old_role == new_role.value:
                return self._view(user)
            if old_role == Role.ADMIN.value and user.is_active:
                self._ensure_another_active_admin(repo)
            user.role = new_role.value
            user.session_version += 1
            record_auth_event(
                session,
                AuthEventType.USER_ROLE_CHANGED,
                principal.username,
                f"Changed role of '{user.username}' from '{old_role}' to '{new_role.value}'",
                {"target_user": user.username, "old_role": old_role, "new_role": new_role.value},
            )
            return self._view(user)

    def set_active(self, principal: Principal, user_id: str, active: bool) -> UserView:
        principal = self._authz.require(principal, Permission.MANAGE_USERS, "activate or deactivate users")
        with self._auth.session() as session:
            repo = UserRepository(session)
            user = self._target(repo, principal, user_id, "deactivate or reactivate your own account")
            if user.is_active == active:
                return self._view(user)
            if not active and user.role == Role.ADMIN.value:
                self._ensure_another_active_admin(repo)
            user.is_active = active
            user.session_version += 1
            if active:
                user.failed_attempts = 0
                user.locked_until = None
            record_auth_event(
                session,
                AuthEventType.USER_ACTIVATED if active else AuthEventType.USER_DEACTIVATED,
                principal.username,
                f"{'Activated' if active else 'Deactivated'} user '{user.username}'",
                {"target_user": user.username},
            )
            return self._view(user)

    def reset_password(self, principal: Principal, user_id: str, temporary_password: str) -> UserView:
        principal = self._authz.require(principal, Permission.MANAGE_USERS, "reset user passwords")
        with self._auth.session() as session:
            repo = UserRepository(session)
            user = self._target(repo, principal, user_id, "reset your own password here (use My Account)")
            validate_new_password(temporary_password, user.username, self._auth.settings.password_min_length)
            user.password_hash = self._auth.hasher.hash(temporary_password)
            user.must_change_password = True
            user.failed_attempts = 0
            user.locked_until = None
            user.session_version += 1
            record_auth_event(
                session,
                AuthEventType.USER_PASSWORD_RESET,
                principal.username,
                f"Reset password for '{user.username}' (temporary; change required at next sign-in)",
                {"target_user": user.username},
            )
            return self._view(user)

    def bootstrap_user(self, username: str, display_name: str, role: Role, password: str, actor: str) -> UserView:
        """Command-line account creation (scripts/create_admin.py,
        scripts/seed_demo_users.py). Same validation as create_user; the
        audit actor is the script, prefixed "system:"."""
        if not actor.startswith("system:"):
            raise UserAdministrationError("bootstrap_user is reserved for command-line scripts.")
        with self._auth.session() as session:
            user = self._create(session, username, display_name, role, password, must_change_password=False)
            record_auth_event(
                session,
                AuthEventType.USER_CREATED,
                actor,
                f"Created user '{user.username}' with role '{user.role}' from the command line",
                {"target_user": user.username, "role": user.role},
            )
            return self._view(user)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _create(
        self, session: Session, username: str, display_name: str, role: Role, password: str, must_change_password: bool
    ) -> User:
        username = normalize_username(username)
        if not _USERNAME_RE.match(username):
            raise UserAdministrationError(
                "Username must be 3-64 characters: lowercase letters, digits, '.', '_' or '-', starting with a letter or digit."
            )
        display_name = (display_name or "").strip()
        if not display_name or len(display_name) > 128:
            raise UserAdministrationError("Display name is required (at most 128 characters).")
        repo = UserRepository(session)
        if repo.get_by_username(username) is not None:
            raise UserAdministrationError(f"A user named '{username}' already exists.")
        validate_new_password(password, username, self._auth.settings.password_min_length)
        return repo.add(
            User(
                username=username,
                display_name=display_name,
                password_hash=self._auth.hasher.hash(password),
                role=Role(role).value,
                is_active=True,
                must_change_password=must_change_password,
                failed_attempts=0,
                session_version=1,
            )
        )

    @staticmethod
    def _target(repo: UserRepository, principal: Principal, user_id: str, self_action: str) -> User:
        user = repo.get_by_id(user_id)
        if user is None:
            raise UserAdministrationError("User not found.")
        if user.id == principal.user_id:
            raise UserAdministrationError(f"You cannot {self_action}.")
        return user

    @staticmethod
    def _ensure_another_active_admin(repo: UserRepository) -> None:
        if repo.count_active_admins() <= 1:
            raise UserAdministrationError(
                "This would leave the platform without an active administrator. "
                "Create or activate another administrator first."
            )

    def _view(self, user: User) -> UserView:
        locked_until = as_utc(user.locked_until)
        return UserView(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=Role(user.role),
            is_active=user.is_active,
            is_locked=locked_until is not None and self._auth.now() < locked_until,
            must_change_password=user.must_change_password,
            last_login_at=as_utc(user.last_login_at),
            created_at=as_utc(user.created_at),
        )


__all__ = ["UserAdminService", "UserView"]
