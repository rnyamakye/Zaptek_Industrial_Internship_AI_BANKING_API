"""Password hashing and JWT helpers. Owner: Rick.

Refresh tokens are stateless JWTs (no extra table, so the 10-entity schema is unchanged).
Trade-off: a refresh token cannot be revoked before it expires; suspended users are
still blocked because the user's status is re-checked on every refresh and every request.
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

ACCESS = "access"
REFRESH = "refresh"
MAX_PASSWORD_BYTES = 72  # bcrypt limit

# Used to spend equal time when the email is unknown (reduces user enumeration by timing).
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Password too long")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Always does one bcrypt check, even when there is no hash, to keep timing similar."""
    raw = password.encode("utf-8")[:MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(raw, (password_hash or _DUMMY_HASH).encode()) and password_hash is not None
    except ValueError:
        return False


def _create_token(user_id: int, role: str, token_type: str, expires: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(
        user_id, role, ACCESS, timedelta(minutes=get_settings().access_token_expire_minutes)
    )


def create_refresh_token(user_id: int, role: str) -> str:
    return _create_token(
        user_id, role, REFRESH, timedelta(days=get_settings().refresh_token_expire_days)
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Returns the payload or raises jwt.InvalidTokenError (expired, tampered, wrong type...)."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload
