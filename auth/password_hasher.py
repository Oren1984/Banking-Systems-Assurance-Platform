from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os

# Salted scrypt password hashing (standard library only — no new
# dependency). Stored format is self-describing so parameters can be
# raised later without breaking existing hashes:
#
#     scrypt$<n>$<r>$<p>$<salt_b64>$<digest_b64>
#
# Defaults follow the OWASP Password Storage Cheat Sheet's scrypt minimum
# (N=2^17, r=8, p=1). Tests construct a cheaper hasher explicitly; the
# production default is never lowered by configuration.

_SCHEME = "scrypt"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


class PasswordHasher:
    def __init__(self, n: int = 2**17, r: int = 8, p: int = 1, salt_bytes: int = 16, dklen: int = 32) -> None:
        self._n, self._r, self._p = n, r, p
        self._salt_bytes = salt_bytes
        self._dklen = dklen

    @staticmethod
    def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
        return hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen, maxmem=256 * 1024 * 1024
        )

    def hash(self, password: str) -> str:
        salt = os.urandom(self._salt_bytes)
        digest = self._derive(password, salt, self._n, self._r, self._p, self._dklen)
        return f"{_SCHEME}${self._n}${self._r}${self._p}${_b64(salt)}${_b64(digest)}"

    def verify(self, password: str, encoded: str) -> bool:
        """Constant-time comparison. Returns False (never raises) for a
        malformed stored value, so a corrupt row cannot crash login."""
        try:
            scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$")
            if scheme != _SCHEME:
                return False
            expected = base64.b64decode(digest_b64, validate=True)
            salt = base64.b64decode(salt_b64, validate=True)
            actual = self._derive(password, salt, int(n), int(r), int(p), len(expected))
        except (ValueError, TypeError, binascii.Error):
            return False
        return hmac.compare_digest(actual, expected)


__all__ = ["PasswordHasher"]
