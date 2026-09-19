"""Shared FastAPI dependencies."""

import uuid
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.user import User

# tokenUrl is what /docs' Authorize button posts to. It must match the form
# endpoint's real path or interactive auth silently fails.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def session_is_live(db: Session, user_id: uuid.UUID, session_id: Any) -> bool:
    """True when `session_id` names an unrevoked session of this user."""
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return False
    session = db.get(AuthSession, sid)
    return session is not None and session.user_id == user_id and session.revoked_at is None


def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    """Resolve the bearer token to a live user.

    Every failure returns the same opaque 401. Distinguishing "malformed
    token" from "expired" from "user deleted" would tell an attacker which
    user IDs exist; the one exception is expiry, which the client legitimately
    needs in order to know to re-authenticate.
    """
    if not token:
        raise _CREDENTIALS_ERROR

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from None
    except jwt.InvalidTokenError:
        raise _CREDENTIALS_ERROR from None

    # A refresh token is only good at /auth/refresh; accepting it here would
    # turn a 30-day credential into a 30-day API key.
    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise _CREDENTIALS_ERROR

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise _CREDENTIALS_ERROR from None

    user = db.get(User, user_id)
    # A token outliving its user (deleted account) must not authenticate, and
    # a deactivated user must not either. Nor may one minted before the user
    # signed out everywhere (token_version bumped since).
    if user is None or not user.is_active or payload.get("tv", 0) != user.token_version:
        raise _CREDENTIALS_ERROR

    # Signing out of one device revokes its session, and with it that device's
    # access token immediately. Tokens issued before sessions existed carry no
    # `sid` and are still accepted until they expire.
    if "sid" in payload and not session_is_live(db, user.id, payload["sid"]):
        raise _CREDENTIALS_ERROR

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_session_id(
    _user: CurrentUser,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> uuid.UUID | None:
    """The sign-in session behind this request's access token.

    Depends on CurrentUser, so the token is already verified (and its session
    live) by the time this reads it. None for a token from before device
    sessions existed.
    """
    sid = decode_token(token or "").get("sid")
    return uuid.UUID(str(sid)) if sid is not None else None


CurrentSessionID = Annotated[uuid.UUID | None, Depends(get_current_session_id)]
