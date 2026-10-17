from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from auth.auth_service import AuthService
from auth.authorizer import Authorizer
from auth.password_hasher import PasswordHasher
from auth.principal import Principal
from auth.secured_services import SecuredAgentService, SecuredAssessmentService
from auth.user_admin_service import UserAdminService
from core.config import Settings
from models.enums import Role

# Shared builder for auth/RBAC tests: a throwaway SQLite database, a cheap
# scrypt cost (the production default is deliberately slow), and a clock
# tests can move forward to exercise lockout expiry and idle timeout.

REPO_ROOT = Path(__file__).resolve().parents[1]
MOCK_SYSTEM_PATH = REPO_ROOT / "mock_banking_system"
TEST_PASSWORD = "Correct-Horse-Battery-9"


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@dataclass
class AuthEnv:
    settings: Settings
    clock: FakeClock
    auth: AuthService
    authz: Authorizer
    admin_service: UserAdminService
    assessments: SecuredAssessmentService
    agent: SecuredAgentService
    principals: Dict[Role, Principal] = field(default_factory=dict)

    def login(self, username: str, password: str = TEST_PASSWORD) -> Principal:
        return self.auth.login(username, password)


def build_auth_env(tmp_path: Path, idle_timeout_minutes: int = 30) -> AuthEnv:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'auth_test.db').as_posix()}",
        allowed_scan_paths=[str(MOCK_SYSTEM_PATH)],
        session_idle_timeout_minutes=idle_timeout_minutes,
    )
    clock = FakeClock()
    auth = AuthService(settings, hasher=PasswordHasher(n=2**10), clock=clock)
    authz = Authorizer(auth)
    env = AuthEnv(
        settings=settings,
        clock=clock,
        auth=auth,
        authz=authz,
        admin_service=UserAdminService(authz),
        assessments=SecuredAssessmentService(authz),
        agent=SecuredAgentService(authz),
    )
    for role in Role:
        env.admin_service.bootstrap_user(f"test.{role.value}", f"Test {role.value.title()}", role, TEST_PASSWORD, actor="system:test")
        env.principals[role] = env.login(f"test.{role.value}")
    return env
