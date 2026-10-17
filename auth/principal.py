from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from models.enums import Role

# The authenticated identity a UI session holds. Immutable: every session
# refresh (auth/auth_service.py::AuthService.validate_session) returns a
# new Principal rather than mutating the one stored in the UI. It carries
# no password, hash, or secret — only what authorization and attribution
# need. `session_version` is compared against users.session_version on
# every protected action (see storage/db/models/user.py).


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    role: Role
    session_version: int
    authenticated_at: datetime
    last_activity_at: datetime
    must_change_password: bool = False


__all__ = ["Principal"]
