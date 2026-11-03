"""Passwords and access tokens.

Passwords are hashed with Argon2id (the argon2-cffi defaults). Access tokens are signed JWTs
(HS256) that carry the user id, the organisation id and a token version. The version is stored on
the user, so changing the password or "sign out everywhere" invalidates every token issued before.

JWT_SECRET            signing secret, at least 32 characters; required to sign in or require auth
JWT_EXPIRE_MINUTES    how long a token is valid (default 480)
"""
import os
import time
import uuid
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128
MIN_SECRET_LENGTH = 32
ALGORITHM = "HS256"

_hasher = PasswordHasher()
_dummy_hash: Optional[str] = None


class AuthError(Exception):
    """A token is missing, malformed, expired or no longer valid"""


class AuthNotConfigured(Exception):
    """JWT_SECRET is missing or too short"""


def validate_password_strength(password: str, email: str = "") -> Optional[str]:
    """A reason the password is not acceptable, or None"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if email and password.lower() == email.lower():
        return "Password must not be the same as the email address."
    if len(set(password)) < 4:
        return "Password is too repetitive."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    """Check a password. With no stored hash (unknown account) it still does the same work,
    so response time does not reveal whether an email is registered."""
    global _dummy_hash
    if not password_hash:
        if _dummy_hash is None:
            _dummy_hash = _hasher.hash("not-a-real-password")
        try:
            _hasher.verify(_dummy_hash, password)
        except (VerificationError, InvalidHashError):
            pass
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def _secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        raise AuthNotConfigured(f"JWT_SECRET must be set to at least {MIN_SECRET_LENGTH} characters.")
    return secret


def token_lifetime_seconds() -> int:
    return int(float(os.getenv("JWT_EXPIRE_MINUTES", "480")) * 60)


def create_access_token(user_id: str, org_id: str, token_version: int) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "org": org_id,
        "tv": token_version,
        "iat": now,
        "exp": now + token_lifetime_seconds(),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "org", "tv", "exp"]})
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Your session has expired. Sign in again.") from e
    except jwt.PyJWTError as e:
        raise AuthError("Invalid sign-in token.") from e
