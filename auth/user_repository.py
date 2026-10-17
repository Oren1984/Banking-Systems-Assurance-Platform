from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from models.enums import Role
from storage.db.models.user import User

# Persistence for platform users. Mirrors storage/db/repositories.py's
# repository style (constructor takes a Session; the caller owns the
# transaction). Intentionally exposes no delete method — see
# storage/db/models/user.py.


def normalize_username(username: str) -> str:
    return username.strip().lower()


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        return self._session.query(User).filter(User.username == normalize_username(username)).one_or_none()

    def list_all(self) -> List[User]:
        return list(self._session.query(User).order_by(User.username).all())

    def count_active_admins(self) -> int:
        return self._session.query(User).filter(User.role == Role.ADMIN.value, User.is_active.is_(True)).count()


__all__ = ["UserRepository", "normalize_username"]
