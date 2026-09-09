"""Signup, login, and the authenticated identity endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core import leveling
from app.core.security import (
    burn_password_time,
    create_access_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.models.user import LevelProgress, User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.schemas.user import MeOut, ProgressOut

logger = logging.getLogger("levelforge.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    # Deliberately identical for "no such email" and "wrong password". A
    # distinct message would turn this endpoint into an account-existence
    # oracle; see also burn_password_time() below.
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _serialize_me(user: User) -> MeOut:
    """Assemble the identity payload, deriving XP-bar values from the curve."""
    progress = user.progress
    into, needed = leveling.progress_into_level(progress.total_xp)
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        timezone=user.timezone,
        created_at=user.created_at,
        progress=ProgressOut(
            total_xp=progress.total_xp,
            current_level=progress.current_level,
            rank=progress.rank.value,
            points_balance=progress.points_balance,
            current_streak=progress.current_streak,
            longest_streak=progress.longest_streak,
            last_completed_on=progress.last_completed_on,
            xp_into_level=into,
            xp_for_next_level=needed,
        ),
    )


def _authenticate(db: DbSession, email: str, password: str) -> User:
    user = db.execute(
        select(User).where(User.email_normalized == normalize_email(email))
    ).scalar_one_or_none()

    if user is None:
        # Spend the same time a real verification costs, so response latency
        # doesn't reveal whether the address is registered.
        burn_password_time()
        raise _INVALID_CREDENTIALS

    if not verify_password(password, user.password_hash):
        raise _INVALID_CREDENTIALS

    if not user.is_active:
        raise _INVALID_CREDENTIALS

    return user


@router.post("/signup", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession) -> MeOut:
    """Create an account and its progression row.

    Both rows are written in one transaction: a User without LevelProgress
    would break every progression read path, and there is no valid state in
    which one exists without the other.
    """
    user = User(
        email=payload.email,
        email_normalized=normalize_email(payload.email),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        timezone=payload.timezone,
    )
    user.progress = LevelProgress(
        total_xp=0,
        current_level=1,
        rank=leveling.rank_for_level(1),
        points_balance=0,
        current_streak=0,
        longest_streak=0,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # The UNIQUE index on email_normalized is the authority here, not a
        # prior SELECT - two simultaneous signups with the same address would
        # both pass a pre-check and only the constraint stops the second.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        ) from None

    db.refresh(user)
    logger.info("user signed up: %s", user.id)
    return _serialize_me(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """JSON login - the endpoint the Reflex frontend uses."""
    user = _authenticate(db, payload.email, payload.password)
    token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenResponse:
    """OAuth2 password-flow login, form-encoded.

    Exists so /docs' Authorize button works for manual testing. Identical
    semantics to /login; OAuth2 mandates the field be named `username`, which
    here carries the email.
    """
    user = _authenticate(db, form.username, form.password)
    token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=MeOut)
def read_me(current_user: CurrentUser) -> MeOut:
    """The signed-in user plus progression - what the Stat Panel renders."""
    return _serialize_me(current_user)
