"""Shared FastAPI dependencies."""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
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
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from None
    except jwt.InvalidTokenError:
        raise _CREDENTIALS_ERROR from None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise _CREDENTIALS_ERROR from None

    user = db.get(User, user_id)
    # A token outliving its user (deleted account) must not authenticate, and
    # a deactivated user must not either.
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
