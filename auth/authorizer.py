from __future__ import annotations

from typing import Optional

from auth.auth_service import AuthService, record_auth_event
from auth.exceptions import AuthorizationError
from auth.permissions import AccessPolicy, Permission
from auth.principal import Principal
from models.enums import AuthEventType

# The single enforcement point every secured service goes through:
#   1. re-validate the session against the database (idle timeout, account
#      still active, session_version unchanged) — auth/auth_service.py;
#   2. block everything while a password change is pending;
#   3. check the role -> permission table — auth/permissions.py;
#   4. on denial, write an ACCESS_DENIED audit event and raise.
# The UI may additionally hide controls via can(), but hiding is cosmetic;
# require() is what actually protects an action.


class Authorizer:
    def __init__(self, auth_service: AuthService, policy: Optional[AccessPolicy] = None) -> None:
        self._auth = auth_service
        self._policy = policy or AccessPolicy()

    @property
    def auth_service(self) -> AuthService:
        return self._auth

    def can(self, principal: Optional[Principal], permission: Permission) -> bool:
        """Cheap, database-free check for rendering decisions only."""
        if principal is None or principal.must_change_password:
            return False
        return self._policy.can(principal.role, permission)

    def require(self, principal: Principal, permission: Permission, action: str, scan_id: Optional[str] = None) -> Principal:
        principal = self._auth.validate_session(principal)
        reason = None
        if principal.must_change_password:
            reason = "password_change_required"
        elif not self._policy.can(principal.role, permission):
            reason = "role_not_permitted"
        if reason is None:
            return principal

        with self._auth.session() as session:
            # scan_id goes in the payload, not the FK column: a denied call
            # may name a scan id that does not exist.
            record_auth_event(
                session,
                AuthEventType.ACCESS_DENIED,
                principal.username,
                f"Access denied: {action}",
                {"permission": permission.value, "role": principal.role.value, "reason": reason, "scan_id": scan_id},
            )
        if reason == "password_change_required":
            raise AuthorizationError("You must change your password before continuing.")
        raise AuthorizationError(f"Your role ({principal.role.value}) is not permitted to {action}.")


__all__ = ["Authorizer"]
