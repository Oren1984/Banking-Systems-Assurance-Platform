from __future__ import annotations

import argparse
import secrets
import sys
from typing import Dict, Optional, Sequence

from auth.auth_service import AuthService
from auth.authorizer import Authorizer
from auth.user_admin_service import UserAdminService
from auth.user_repository import UserRepository
from core.config import Settings, get_settings
from models.enums import Role

# OPTIONAL synthetic demo accounts — one per role — for walkthroughs and
# browser testing only. Refuses to do anything without an explicit --demo
# flag. Passwords are generated randomly on every run and printed exactly
# once; nothing is hardcoded, and nothing is created on application startup.
# Existing accounts with these names are left untouched (never reset).
#
#     python -m scripts.seed_demo_users --demo

DEMO_USERS = (
    ("demo.admin", "Demo Administrator", Role.ADMIN),
    ("demo.manager", "Demo Manager", Role.MANAGER),
    ("demo.employee", "Demo Employee", Role.EMPLOYEE),
)


def seed_demo_users(settings: Optional[Settings] = None) -> Dict[str, str]:
    """Returns {username: generated_password} for accounts created by this
    call (accounts that already existed are omitted)."""
    auth = AuthService(settings or get_settings())
    admin_service = UserAdminService(Authorizer(auth))
    created: Dict[str, str] = {}
    for username, display_name, role in DEMO_USERS:
        with auth.session() as session:
            if UserRepository(session).get_by_username(username) is not None:
                continue
        password = secrets.token_urlsafe(15)
        admin_service.bootstrap_user(username, display_name, role, password, actor="system:seed_demo_users")
        created[username] = password
    return created


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create synthetic demo users (one per role).")
    parser.add_argument("--demo", action="store_true", help="Required. Confirms these are throwaway demo accounts.")
    args = parser.parse_args(argv)
    if not args.demo:
        print("Refusing to create demo users without --demo.", file=sys.stderr)
        return 2
    created = seed_demo_users()
    if not created:
        print("All demo users already exist; nothing created (existing passwords were not changed).")
        return 0
    print("WARNING: synthetic demo accounts for local demonstration only. Deactivate them before any shared use.")
    for username, password in created.items():
        print(f"  {username:<15} {password}")
    print("These passwords are shown once and are not stored anywhere in plain text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
