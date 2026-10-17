from __future__ import annotations

import json

import pytest

from auth.exceptions import (
    GENERIC_LOGIN_FAILURE,
    AuthenticationError,
    AuthorizationError,
    SessionExpiredError,
    SessionInvalidatedError,
    UserAdministrationError,
)
from auth.permissions import Permission
from models.enums import AuthEventType, Role
from storage.db.models.audit_event import AuditEvent
from storage.db.models.user import User
from tests.auth_support import TEST_PASSWORD, build_auth_env


@pytest.fixture()
def env(tmp_path):
    return build_auth_env(tmp_path)


def _events(env, event_type=None):
    with env.auth.session() as s:
        q = s.query(AuditEvent)
        if event_type is not None:
            q = q.filter(AuditEvent.event_type == event_type.value)
        return list(q.order_by(AuditEvent.created_at).all())


def _user(env, username):
    with env.auth.session() as s:
        return s.query(User).filter(User.username == username).one()


def test_successful_login_returns_principal_and_records_event(env):
    p = env.login("test.manager")
    assert p.username == "test.manager"
    assert p.role == Role.MANAGER
    assert p.session_version == 1
    assert any(e.actor == "test.manager" for e in _events(env, AuthEventType.USER_LOGIN))
    assert _user(env, "test.manager").last_login_at is not None


def test_username_lookup_is_case_insensitive(env):
    assert env.login("  Test.Manager ").username == "test.manager"


@pytest.mark.parametrize(
    "username,password",
    [("no.such.user", TEST_PASSWORD), ("test.manager", "wrong-password-xyz"), ("", "")],
)
def test_failed_login_message_is_generic(env, username, password):
    with pytest.raises(AuthenticationError) as exc:
        env.login(username, password)
    assert str(exc.value) == GENERIC_LOGIN_FAILURE


def test_locked_and_inactive_accounts_get_the_same_generic_message(env):
    for _ in range(5):
        with pytest.raises(AuthenticationError):
            env.login("test.employee", "wrong-password-xyz")
    with pytest.raises(AuthenticationError) as locked:
        env.login("test.employee", TEST_PASSWORD)
    assert str(locked.value) == GENERIC_LOGIN_FAILURE

    admin = env.principals[Role.ADMIN]
    manager_id = _user(env, "test.manager").id
    env.admin_service.set_active(admin, manager_id, False)
    with pytest.raises(AuthenticationError) as inactive:
        env.login("test.manager", TEST_PASSWORD)
    assert str(inactive.value) == GENERIC_LOGIN_FAILURE


def test_five_failures_lock_the_account_for_fifteen_minutes(env):
    for i in range(4):
        with pytest.raises(AuthenticationError):
            env.login("test.employee", "wrong-password-xyz")
    assert _user(env, "test.employee").failed_attempts == 4
    assert _user(env, "test.employee").locked_until is None

    with pytest.raises(AuthenticationError):
        env.login("test.employee", "wrong-password-xyz")
    assert _user(env, "test.employee").locked_until is not None
    assert len(_events(env, AuthEventType.USER_LOCKED_OUT)) == 1

    # Correct password is still refused while locked.
    env.clock.advance(minutes=14, seconds=59)
    with pytest.raises(AuthenticationError):
        env.login("test.employee", TEST_PASSWORD)

    env.clock.advance(seconds=2)
    assert env.login("test.employee").username == "test.employee"
    assert _user(env, "test.employee").failed_attempts == 0
    assert _user(env, "test.employee").locked_until is None


def test_successful_login_resets_failed_attempt_counter(env):
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            env.login("test.employee", "wrong-password-xyz")
    env.login("test.employee")
    assert _user(env, "test.employee").failed_attempts == 0


def test_failed_login_audit_never_contains_the_attempted_password(env):
    secret_attempt = "Sup3r-Secret-Attempt-Value"
    with pytest.raises(AuthenticationError):
        env.login("test.manager", secret_attempt)
    with pytest.raises(AuthenticationError):
        env.login("someone.else", secret_attempt)
    events = _events(env, AuthEventType.USER_LOGIN_FAILED)
    assert [e.actor for e in events] == ["test.manager", "anonymous"]
    assert [e.payload["reason"] for e in events] == ["invalid_password", "unknown_account"]
    dump = json.dumps([(e.summary, e.payload) for e in _events(env)])
    assert secret_attempt not in dump
    assert TEST_PASSWORD not in dump
    assert "scrypt$" not in dump


def test_idle_timeout_expires_the_session(env):
    p = env.login("test.employee")
    env.clock.advance(minutes=29)
    p = env.auth.validate_session(p)  # activity refreshes the idle window
    env.clock.advance(minutes=29)
    p = env.auth.validate_session(p)
    env.clock.advance(minutes=31)
    with pytest.raises(SessionExpiredError):
        env.auth.validate_session(p)
    assert _events(env, AuthEventType.SESSION_EXPIRED)[-1].actor == "test.employee"


def test_idle_timeout_is_configurable(tmp_path):
    env = build_auth_env(tmp_path, idle_timeout_minutes=5)
    p = env.login("test.employee")
    env.clock.advance(minutes=6)
    with pytest.raises(SessionExpiredError):
        env.auth.validate_session(p)


def test_expired_session_also_blocks_direct_service_calls(env):
    p = env.login("test.manager")
    env.clock.advance(minutes=31)
    with pytest.raises(SessionExpiredError):
        env.assessments.list_recent_scans(p)


def test_logout_records_event(env):
    p = env.login("test.employee")
    env.auth.logout(p)
    assert _events(env, AuthEventType.USER_LOGOUT)[-1].actor == "test.employee"


def test_change_own_password(env):
    p = env.login("test.employee")
    with pytest.raises(UserAdministrationError):
        env.auth.change_own_password(p, "not-the-current-one", "Another-Long-Passphrase-1")
    with pytest.raises(UserAdministrationError):
        env.auth.change_own_password(p, TEST_PASSWORD, "short")
    new_p = env.auth.change_own_password(p, TEST_PASSWORD, "Another-Long-Passphrase-1")
    assert new_p.session_version == p.session_version + 1
    # Old session (old version) is no longer valid; the returned one is.
    with pytest.raises(SessionInvalidatedError):
        env.auth.validate_session(p)
    env.auth.validate_session(new_p)
    with pytest.raises(AuthenticationError):
        env.login("test.employee", TEST_PASSWORD)
    env.login("test.employee", "Another-Long-Passphrase-1")
    assert _events(env, AuthEventType.PASSWORD_CHANGED)[-1].actor == "test.employee"


def test_pending_password_change_blocks_everything_else(env):
    admin = env.principals[Role.ADMIN]
    emp = _user(env, "test.employee")
    env.admin_service.reset_password(admin, emp.id, "Temporary-Pass-4321")
    p = env.login("test.employee", "Temporary-Pass-4321")
    assert p.must_change_password
    assert not env.authz.can(p, Permission.VIEW_ASSESSMENTS)
    with pytest.raises(AuthorizationError):
        env.assessments.list_recent_scans(p)
    p = env.auth.change_own_password(p, "Temporary-Pass-4321", "Fresh-Long-Passphrase-7")
    assert not p.must_change_password
    assert env.assessments.list_recent_scans(p) == []
