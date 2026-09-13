"""Password hashing and JWT issuance/verification.

passlib is deliberately absent - see the note in requirements.txt. We call
bcrypt directly and PyJWT directly, both of which are maintained and work on
Python 3.14.
"""

import datetime as dt
import uuid
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

# bcrypt hashes at most 72 BYTES and bcrypt>=4 raises ValueError beyond that
# rather than truncating silently. Requests are rejected at the schema layer
# (see schemas/auth.py) so this module never has to decide whether to truncate
# a user's password - silently dropping bytes would make two different
# passwords open the same account.
MAX_PASSWORD_BYTES = 72

# A real hash of a throwaway value, used to burn the same CPU time on a failed
# login as on a successful one. Without it, "unknown email" returns measurably
# faster than "wrong password" and the endpoint becomes a user-enumeration
# oracle. Computed once at import.
_DUMMY_HASH = bcrypt.hashpw(b"metalarm-timing-equalizer", bcrypt.gensalt())


def hash_password(plain: str) -> str:
    """bcrypt hash, salt included in the output string."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time comparison. Never raises on malformed input - a corrupt
    stored hash must read as 'wrong password', not as a 500."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def burn_password_time() -> None:
    """Spend a bcrypt verification's worth of time on a nonexistent user."""
    bcrypt.checkpw(b"metalarm-timing-equalizer", _DUMMY_HASH)


ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def _encode_token(
    user_id: uuid.UUID, token_version: int, token_type: str, expires_in: int
) -> tuple[str, int]:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        # The JWT spec requires `sub` to be a string; PyJWT rejects anything
        # else on decode.
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(seconds=expires_in),
        # Unique per token so individual tokens can be revoked later (Redis
        # denylist) without invalidating every session.
        "jti": str(uuid.uuid4()),
        # Checked on every use: a long-lived refresh token must never be
        # accepted where an access token is expected.
        "typ": token_type,
        # users.token_version at mint time. Bumping the column (sign out
        # everywhere) invalidates every token already issued.
        "tv": token_version,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_in


def create_access_token(user_id: uuid.UUID, token_version: int = 0) -> tuple[str, int]:
    """Return (token, expires_in_seconds) for a short-lived API token."""
    return _encode_token(
        user_id, token_version, ACCESS_TOKEN_TYPE, settings.access_token_expire_minutes * 60
    )


def create_refresh_token(user_id: uuid.UUID, token_version: int = 0) -> tuple[str, int]:
    """Return (token, expires_in_seconds) for a long-lived token that can only
    be exchanged at /auth/refresh. Lets the mobile app stay signed in without
    keeping the password."""
    return _encode_token(
        user_id, token_version, REFRESH_TOKEN_TYPE, settings.refresh_token_expire_days * 86400
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify an access or refresh token; callers check `typ`.
    Raises jwt.InvalidTokenError (or a subclass such as ExpiredSignatureError)
    on any failure.

    `algorithms` is pinned to the single configured algorithm: accepting a list
    the attacker can choose from is how alg-confusion attacks work.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub"]},
    )


def normalize_email(email: str) -> str:
    """The single place email normalization happens.

    users.email_normalized carries the UNIQUE constraint, so every write path
    must produce it the same way or case-variant duplicates slip through.
    """
    return email.strip().lower()
