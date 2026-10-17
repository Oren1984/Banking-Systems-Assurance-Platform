from __future__ import annotations

import argparse
import getpass
import sys
from typing import Callable, Optional, Sequence

from auth.auth_service import AuthService
from auth.authorizer import Authorizer
from auth.user_admin_service import UserAdminService
from core.config import Settings, get_settings
from core.exceptions import PlatformError
from models.enums import Role

# Create a platform administrator from the command line — the only way to
# create the FIRST account (there is no default administrator and no
# default password anywhere in this codebase). The password is always read
# interactively (getpass, entered twice); it is never accepted as a
# command-line argument, where it would land in shell history and process
# listings. Also serves as the recovery path if every administrator is
# locked out: shell access to the host is the trust boundary here.
#
#     python -m scripts.create_admin --username alice --display-name "Alice Admin"
#     docker compose -f deployment/docker-compose.yml exec app python -m scripts.create_admin --username alice
#
# Every run is recorded in the audit trail (actor "system:create_admin").


def create_admin(
    username: str,
    display_name: str,
    settings: Optional[Settings] = None,
    read_password: Callable[[str], str] = getpass.getpass,
) -> int:
    settings = settings or get_settings()
    password = read_password("New administrator password: ")
    if password != read_password("Repeat password: "):
        print("Passwords do not match. No account was created.", file=sys.stderr)
        return 1
    admin_service = UserAdminService(Authorizer(AuthService(settings)))
    try:
        user = admin_service.bootstrap_user(username, display_name or username, Role.ADMIN, password, actor="system:create_admin")
    except PlatformError as exc:
        print(f"Could not create administrator: {exc}", file=sys.stderr)
        return 1
    print(f"Administrator '{user.username}' created. Sign in at the platform login screen.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a platform administrator account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default="")
    args = parser.parse_args(argv)
    return create_admin(args.username, args.display_name)


if __name__ == "__main__":
    sys.exit(main())
