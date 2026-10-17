from __future__ import annotations

import inspect
import io
from pathlib import Path

import pytest

import scripts.create_admin as create_admin_mod
import scripts.seed_demo_users as seed_mod
from auth.auth_service import AuthService
from auth.db import open_session
from auth.password_hasher import PasswordHasher
from core.config import Settings
from models.enums import Role
from storage.db.models.audit_event import AuditEvent
from storage.db.models.user import User


@pytest.fixture()
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{(tmp_path / 'scripts.db').as_posix()}")


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    # Production cost is deliberately slow; scripts build their own AuthService.
    original = AuthService.__init__

    def _init(self, settings, hasher=None, clock=None):
        kwargs = {"hasher": hasher or PasswordHasher(n=2**10)}
        if clock is not None:
            kwargs["clock"] = clock
        original(self, settings, **kwargs)

    monkeypatch.setattr(AuthService, "__init__", _init)


def _users(settings):
    with open_session(settings) as s:
        return {u.username: u for u in s.query(User).all()}


def test_create_admin_reads_password_interactively_twice(settings):
    prompts = []

    def fake_getpass(prompt):
        prompts.append(prompt)
        return "Operator-Chosen-Pass-1"

    assert create_admin_mod.create_admin("first.admin", "First Admin", settings, read_password=fake_getpass) == 0
    assert len(prompts) == 2
    user = _users(settings)["first.admin"]
    assert user.role == Role.ADMIN.value and user.is_active and not user.must_change_password
    assert "Operator-Chosen-Pass-1" not in user.password_hash
    with open_session(settings) as s:
        assert s.query(AuditEvent).filter(AuditEvent.actor == "system:create_admin").count() == 1


def test_create_admin_rejects_mismatch_and_weak_passwords(settings, capsys):
    answers = iter(["Operator-Chosen-Pass-1", "Different-Pass-2"])
    assert create_admin_mod.create_admin("first.admin", "", settings, read_password=lambda _: next(answers)) == 1
    assert create_admin_mod.create_admin("first.admin", "", settings, read_password=lambda _: "short") == 1
    assert _users(settings) == {}


def test_create_admin_from_credentials_file(settings):
    content = io.StringIO(
        "# comment line\nADMIN_USERNAME=File.Admin\nADMIN_DISPLAY_NAME=\"File Admin\"\nADMIN_PASSWORD=File-Based-Pass-2026\n"
    )
    assert create_admin_mod.create_admin_from_file(content, settings) == 0
    user = _users(settings)["file.admin"]
    assert user.role == "admin" and user.display_name == "File Admin" and not user.must_change_password
    assert "File-Based-Pass-2026" not in user.password_hash
    # Re-running is a no-op that leaves the existing account untouched.
    before = user.password_hash
    again = io.StringIO("ADMIN_USERNAME=file.admin\nADMIN_PASSWORD=Another-Pass-2026x\n")
    assert create_admin_mod.create_admin_from_file(again, settings) == 0
    assert _users(settings)["file.admin"].password_hash == before


def test_credentials_file_requires_username_and_password(settings):
    assert create_admin_mod.create_admin_from_file(io.StringIO("ADMIN_USERNAME=x.admin\n"), settings) == 1
    assert create_admin_mod.create_admin_from_file(io.StringIO("ADMIN_PASSWORD=x\n"), settings) == 1
    assert create_admin_mod.create_admin_from_file(io.StringIO("ADMIN_USERNAME=x.admin\nADMIN_PASSWORD=short\n"), settings) == 1
    assert _users(settings) == {}


def test_credentials_file_is_git_and_docker_ignored():
    root = Path(create_admin_mod.__file__).resolve().parents[1]
    for ignore_file in (".gitignore", ".dockerignore"):
        lines = [l.strip() for l in (root / ignore_file).read_text(encoding="utf-8").splitlines()]
        assert "admin.credentials" in lines, ignore_file
    assert (root / "admin.credentials.example").exists()


def test_create_admin_has_no_password_argument():
    parser_src = inspect.getsource(create_admin_mod.main)
    assert "--password" not in parser_src


def test_no_default_admin_exists_until_created(settings):
    assert _users(settings) == {}


def test_seed_demo_users_requires_explicit_demo_flag(capsys):
    assert seed_mod.main([]) == 2
    assert "--demo" in capsys.readouterr().err


def test_seed_demo_users_creates_one_per_role_with_random_passwords(settings):
    first = seed_mod.seed_demo_users(settings)
    assert set(first) == {"demo.admin", "demo.manager", "demo.employee"}
    assert len(set(first.values())) == 3
    users = _users(settings)
    assert {u.role for u in users.values()} == {"admin", "manager", "employee"}
    # Idempotent: a second run creates nothing and never resets passwords.
    hashes = {name: u.password_hash for name, u in users.items()}
    assert seed_mod.seed_demo_users(settings) == {}
    assert {name: u.password_hash for name, u in _users(settings).items()} == hashes


def test_scripts_contain_no_hardcoded_passwords():
    for path in (Path(create_admin_mod.__file__), Path(seed_mod.__file__)):
        src = path.read_text(encoding="utf-8").lower()
        assert "password=\"" not in src.replace(" ", "")
