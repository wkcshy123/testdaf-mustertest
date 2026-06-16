"""Password hashing and session-cookie helpers.

Uses the standard-library ``hashlib.scrypt`` to avoid pulling in extra
dependencies, keeping the local-first, dependency-light stance of the
project consistent with the rest of the platforms.
"""

from __future__ import annotations

import hashlib
import hmac
import os

# scrypt parameters. n is the CPU/memory cost (2^14), r the block size,
# p the parallelization factor. These are sane modern defaults for a
# local, low-throughput system.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

# Format stored on disk: "$scrypt$n$r$p$salt_hex$hash_hex".
_PREFIX = "$scrypt"


def hash_password(raw: str) -> str:
    """Return a self-describing scrypt hash string for ``raw``."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        raw.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return f"{_PREFIX}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(raw: str, stored: str) -> bool:
    """Return True if ``raw`` matches the previously hashed ``stored``."""
    try:
        _, marker, n, r, p, salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    if marker != "scrypt":
        return False
    digest = hashlib.scrypt(
        raw.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=int(n),
        r=int(r),
        p=int(p),
        dklen=len(bytes.fromhex(hash_hex)),
    )
    return hmac.compare_digest(digest.hex(), hash_hex)
