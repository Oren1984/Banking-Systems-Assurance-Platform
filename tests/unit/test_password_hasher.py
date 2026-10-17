from __future__ import annotations

from auth.password_hasher import PasswordHasher


def _fast() -> PasswordHasher:
    return PasswordHasher(n=2**10)


def test_hash_is_salted_scrypt_and_never_contains_the_password():
    hasher = _fast()
    encoded = hasher.hash("Correct-Horse-Battery-9")
    scheme, n, r, p, salt, digest = encoded.split("$")
    assert scheme == "scrypt"
    assert (n, r, p) == ("1024", "8", "1")
    assert "Correct-Horse-Battery-9" not in encoded
    assert salt and digest


def test_same_password_gets_a_different_salt_every_time():
    hasher = _fast()
    a, b = hasher.hash("same-password-123"), hasher.hash("same-password-123")
    assert a != b
    assert hasher.verify("same-password-123", a)
    assert hasher.verify("same-password-123", b)


def test_wrong_password_is_rejected():
    hasher = _fast()
    encoded = hasher.hash("Correct-Horse-Battery-9")
    assert not hasher.verify("correct-horse-battery-9", encoded)
    assert not hasher.verify("", encoded)


def test_malformed_or_foreign_hashes_fail_closed_without_raising():
    hasher = _fast()
    for bad in ["", "plaintext", "bcrypt$1$2$3$4$5", "scrypt$x$8$1$AAAA$BBBB", "scrypt$1024$8$1$!!!$###"]:
        assert hasher.verify("anything", bad) is False


def test_verification_uses_the_parameters_stored_in_the_hash():
    # A hash made with other parameters stays verifiable, so the cost can be
    # raised later without invalidating existing accounts.
    old = PasswordHasher(n=2**11).hash("rotating-password-1")
    assert _fast().verify("rotating-password-1", old)


def test_production_default_cost_meets_owasp_scrypt_minimum():
    assert PasswordHasher()._n == 2**17
    assert PasswordHasher()._r == 8
