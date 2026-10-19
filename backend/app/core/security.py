"""
Password hashing & JWT helpers.

New passwords use bcrypt (adaptive, salted, deliberately slow).
Legacy `salt$sha256` hashes created by older versions still verify, and are
transparently upgraded to bcrypt on the next successful login (see
`needs_rehash` + the login handler).
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import bcrypt
from jose import jwt

from app.config import settings

_BCRYPT_ROUNDS = 12
# bcrypt only consumes the first 72 bytes; truncate explicitly to avoid ValueError.
_BCRYPT_MAX_BYTES = 72


def _legacy_hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    if not password:
        raise ValueError("password must not be empty")
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against either a bcrypt or a legacy salt$sha256 hash."""
    if not hashed_password:
        return False

    # bcrypt hashes start with $2a$ / $2b$ / $2y$
    if hashed_password.startswith("$2"):
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    # Legacy: salt$sha256
    if "$" in hashed_password:
        salt, expected = hashed_password.split("$", 1)
        return hmac.compare_digest(_legacy_hash(plain_password, salt), expected)

    # Legacy: unsalted sha256
    return hmac.compare_digest(
        hashlib.sha256(plain_password.encode("utf-8")).hexdigest(), hashed_password
    )


def needs_rehash(hashed_password: str) -> bool:
    """True when the stored hash is not bcrypt and should be upgraded."""
    return not hashed_password.startswith("$2")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
