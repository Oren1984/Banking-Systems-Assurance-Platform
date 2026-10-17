from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, TextIO

from auth.auth_service import AuthService
from auth.authorizer import Authorizer
from auth.user_admin_service import UserAdminService
from auth.user_repository import UserRepository
from core.config import Settings, get_settings
from core.exceptions import PlatformError
from models.enums import Role

# Create a platform administrator from the command line — the only way to
# create the FIRST account (there is no default administrator and no
# default password anywhere in this codebase). Shell access to the host is
# the trust boundary here; it is also the recovery path if every
# administrator is locked out. Every run is recorded in the audit trail
# (actor "system:create_admin").
#
# Two ways to supply the password — never as a command-line argument, where
# it would land in shell history and process listings:
#
# 1. Interactive (default): entered twice via getpass.
#        python -m scripts.create_admin --username alice --display-name "Alice Admin"
#
# 2. From a local credentials file (KEY=VALUE lines, see
#    admin.credentials.example). The file is git- and docker-ignored, so it
#    never enters the repository or the image; for Docker, pipe it in on
#    stdin with "-":
#        python -m scripts.create_admin --credentials-file admin.credentials
#        docker compose -f deployment/docker-compose.yml exec -T app \
#            python -m scripts.create_admin --credentials-file - < admin.credentials
#    Re-running is safe: an existing account is left unchanged.


def parse_credentials(stream: TextIO) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw in stream:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip().upper()] = value.strip().strip('"').strip("'")
    return values


def create_admin(
    username: str,
    display_name: str,
    settings: Optional[Settings] = None,
    read_password: Callable[[str], str] = getpass.getpass,
) -> int:
    password = read_password("New administrator password: ")
    if password != read_password("Repeat password: "):
        print("Passwords do not match. No account was created.", file=sys.stderr)
        return 1
    return _create(username, display_name, password, settings)


def create_admin_from_file(stream: TextIO, settings: Optional[Settings] = None) -> int:
    values = parse_credentials(stream)
    username, password = values.get("ADMIN_USERNAME", ""), values.get("ADMIN_PASSWORD", "")
    if not username or not password:
        print("The credentials file must define ADMIN_USERNAME and ADMIN_PASSWORD.", file=sys.stderr)
        return 1
    settings = settings or get_settings()
    with AuthService(settings).session() as session:
        if UserRepository(session).get_by_username(username) is not None:
            print(f"User '{username.strip().lower()}' already exists; it was not modified.")
            return 0
    return _create(username, values.get("ADMIN_DISPLAY_NAME", ""), password, settings)


def _create(username: str, display_name: str, password: str, settings: Optional[Settings]) -> int:
    admin_service = UserAdminService(Authorizer(AuthService(settings or get_settings())))
    try:
        user = admin_service.bootstrap_user(
            username, display_name or username, Role.ADMIN, password, actor="system:create_admin"
        )
    except PlatformError as exc:
        print(f"Could not create administrator: {exc}", file=sys.stderr)
        return 1
    print(f"Administrator '{user.username}' created. Sign in at the platform login screen.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create a platform administrator account.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--username", help="Interactive mode: the password is prompted for.")
    source.add_argument(
        "--credentials-file",
        help="Path to a KEY=VALUE file with ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_DISPLAY_NAME ('-' = stdin).",
    )
    parser.add_argument("--display-name", default="")
    args = parser.parse_args(argv)
    if args.credentials_file:
        if args.credentials_file == "-":
            return create_admin_from_file(sys.stdin)
        with Path(args.credentials_file).open(encoding="utf-8") as handle:
            return create_admin_from_file(handle)
    return create_admin(args.username, args.display_name)


if __name__ == "__main__":
    sys.exit(main())
