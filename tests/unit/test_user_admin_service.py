from __future__ import annotations

import pytest

from auth.exceptions import AuthenticationError, AuthorizationError, SessionInvalidatedError, UserAdministrationError
from auth.user_admin_service import UserAdminService
from auth.user_repository import UserRepository
from models.enums import AuthEventType, Role
from storage.db.models.audit_event import AuditEvent
from storage.db.models.user import User
from tests.auth_support import TEST_PASSWORD, build_auth_env


@pytest.fixture()
def env(tmp_path):
    return build_auth_env(tmp_path)


def _id(env, username):
    with env.auth.session() as s:
        return s.query(User).filter(User.username == username).one().id


def _last_event(env, event_type):
    with env.auth.session() as s:
        return (
            s.query(AuditEvent)
            .filter(AuditEvent.event_type == event_type.value)
            .order_by(AuditEvent.created_at.desc())
            .first()
        )


def test_admin_creates_user_with_temporary_password(env):
    admin = env.principals[Role.ADMIN]
    view = env.admin_service.create_user(admin, "New.Analyst", "New Analyst", Role.EMPLOYEE, "Initial-Pass-2026")
    assert view.username == "new.analyst"
    assert view.must_change_password is True
    assert not hasattr(view, "password_hash")
    event = _last_event(env, AuthEventType.USER_CREATED)
    assert event.actor == "test.admin"
    assert event.payload == {"target_user": "new.analyst", "role": "employee"}
    assert env.login("new.analyst", "Initial-Pass-2026").must_change_password


@pytest.mark.parametrize(
    "username,password,message",
    [
        ("test.manager", "Long-Enough-Pass-1", "already exists"),
        ("ab", "Long-Enough-Pass-1", "Username must be"),
        ("bad user", "Long-Enough-Pass-1", "Username must be"),
        ("valid.name", "short", "at least 12"),
        ("valid.name", "valid.name-plus-more", "must not contain the username"),
        ("valid.name", "aaaaaaaaaaaaaaaa", "too simple"),
    ],
)
def test_create_user_validation(env, username, password, message):
    with pytest.raises(UserAdministrationError, match=message):
        env.admin_service.create_user(env.principals[Role.ADMIN], username, "Name", Role.EMPLOYEE, password)


@pytest.mark.parametrize("role", [Role.MANAGER, Role.EMPLOYEE])
def test_only_admin_can_manage_users(env, role):
    p = env.principals[role]
    target = _id(env, "test.employee")
    with pytest.raises(AuthorizationError):
        env.admin_service.list_users(p)
    with pytest.raises(AuthorizationError):
        env.admin_service.create_user(p, "x.user", "X", Role.ADMIN, "Long-Enough-Pass-1")
    with pytest.raises(AuthorizationError):
        env.admin_service.change_role(p, target, Role.MANAGER)
    with pytest.raises(AuthorizationError):
        env.admin_service.set_active(p, target, False)
    with pytest.raises(AuthorizationError):
        env.admin_service.reset_password(p, target, "Long-Enough-Pass-1")
    denied = _last_event(env, AuthEventType.ACCESS_DENIED)
    assert denied.actor == p.username
    assert denied.payload["permission"] == "manage_users"


def test_role_change_invalidates_existing_sessions(env):
    emp_session = env.principals[Role.EMPLOYEE]
    env.admin_service.change_role(env.principals[Role.ADMIN], _id(env, "test.employee"), Role.MANAGER)
    with pytest.raises(SessionInvalidatedError):
        env.assessments.list_recent_scans(emp_session)
    # Signing in again picks up the new role.
    assert env.login("test.employee").role == Role.MANAGER
    event = _last_event(env, AuthEventType.USER_ROLE_CHANGED)
    assert event.payload == {"target_user": "test.employee", "old_role": "employee", "new_role": "manager"}


def test_deactivation_invalidates_sessions_and_blocks_login(env):
    mgr_session = env.principals[Role.MANAGER]
    env.admin_service.set_active(env.principals[Role.ADMIN], _id(env, "test.manager"), False)
    with pytest.raises(SessionInvalidatedError):
        env.assessments.list_recent_scans(mgr_session)
    with pytest.raises(AuthenticationError):
        env.login("test.manager")
    env.admin_service.set_active(env.principals[Role.ADMIN], _id(env, "test.manager"), True)
    assert env.login("test.manager").role == Role.MANAGER


def test_password_reset_invalidates_sessions_and_requires_change(env):
    emp_session = env.principals[Role.EMPLOYEE]
    view = env.admin_service.reset_password(env.principals[Role.ADMIN], _id(env, "test.employee"), "Temporary-Pass-4321")
    assert view.must_change_password
    with pytest.raises(SessionInvalidatedError):
        env.auth.validate_session(emp_session)
    with pytest.raises(AuthenticationError):
        env.login("test.employee", TEST_PASSWORD)
    assert env.login("test.employee", "Temporary-Pass-4321").must_change_password


def test_password_reset_clears_lockout(env):
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            env.login("test.employee", "wrong-password-xyz")
    env.admin_service.reset_password(env.principals[Role.ADMIN], _id(env, "test.employee"), "Temporary-Pass-4321")
    env.login("test.employee", "Temporary-Pass-4321")


def test_admin_cannot_modify_own_account(env):
    admin = env.principals[Role.ADMIN]
    own = _id(env, "test.admin")
    with pytest.raises(UserAdministrationError, match="own role"):
        env.admin_service.change_role(admin, own, Role.MANAGER)
    with pytest.raises(UserAdministrationError, match="own account"):
        env.admin_service.set_active(admin, own, False)
    with pytest.raises(UserAdministrationError):
        env.admin_service.reset_password(admin, own, "Another-Long-Pass-1")


def test_one_admin_may_demote_or_deactivate_another_while_one_remains(env):
    admin = env.principals[Role.ADMIN]
    env.admin_service.bootstrap_user("second.admin", "Second", Role.ADMIN, "Second-Admin-Pass-1", actor="system:test")
    env.admin_service.change_role(admin, _id(env, "second.admin"), Role.EMPLOYEE)
    env.admin_service.change_role(admin, _id(env, "second.admin"), Role.ADMIN)
    env.admin_service.set_active(admin, _id(env, "second.admin"), False)
    with env.auth.session() as s:
        assert UserRepository(s).count_active_admins() == 1


def test_last_active_admin_guard(env):
    # Through the public API the acting admin is itself an active admin and
    # cannot target itself, so "last admin" is already prevented by the
    # self-modification rule above. This guard is the second, independent
    # line of defence (e.g. against two admins demoting each other
    # concurrently) and is exercised directly.
    with env.auth.session() as s:
        repo = UserRepository(s)
        assert repo.count_active_admins() == 1
        with pytest.raises(UserAdministrationError, match="without an active administrator"):
            UserAdminService._ensure_another_active_admin(repo)
    env.admin_service.bootstrap_user("second.admin", "Second", Role.ADMIN, "Second-Admin-Pass-1", actor="system:test")
    with env.auth.session() as s:
        UserAdminService._ensure_another_active_admin(UserRepository(s))


def test_inactive_admins_do_not_count_as_remaining_admins(env):
    admin = env.principals[Role.ADMIN]
    env.admin_service.bootstrap_user("second.admin", "Second", Role.ADMIN, "Second-Admin-Pass-1", actor="system:test")
    env.admin_service.set_active(admin, _id(env, "second.admin"), False)
    with env.auth.session() as s:
        with pytest.raises(UserAdministrationError):
            UserAdminService._ensure_another_active_admin(UserRepository(s))


def test_users_are_never_deleted():
    assert not any("delete" in name for name in dir(UserRepository))
    assert not any("delete" in name for name in dir(UserAdminService))


def test_bootstrap_is_reserved_for_cli_actors(env):
    with pytest.raises(UserAdministrationError):
        env.admin_service.bootstrap_user("sneaky", "Sneaky", Role.ADMIN, "Sneaky-Admin-Pass-1", actor="test.employee")
