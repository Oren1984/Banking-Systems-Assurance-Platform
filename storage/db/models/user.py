from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Authentication — platform user accounts (auth/). Added by
# alembic/versions/0004_auth_users.py; no existing table is altered.
#
# NEVER DELETED: there is no delete method for this table anywhere in the
# codebase (auth/user_repository.py exposes deactivate, not delete). The
# audit trail records `actor` as the username, so a user referenced by
# history must keep existing for that history to stay attributable.
#
# `password_hash` holds only a salted scrypt digest in the self-describing
# format produced by auth/password_hasher.py — never a plaintext password.
#
# `session_version` is the server-side session invalidation counter: a UI
# session remembers the version it logged in with, and every protected
# action compares it against this column. Deactivation, role change, and
# password reset/change all increment it, so a stale session (old role,
# old password, deactivated account) is rejected on its next action.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.Role

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
