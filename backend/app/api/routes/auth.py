"""Signup, login, token refresh, sign-out, account deletion, and the
authenticated identity endpoint."""

import datetime as dt
import logging
import uuid
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, get_current_user, oauth2_scheme, session_is_live
from app.api.routes.parties import release_membership
from app.core import leaderboard, leveling, rate_limit
from app.core.periods import local_now
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    burn_password_time,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.models.auth_session import AuthSession
from app.models.party import Party, PartyMembership
from app.models.user import LevelProgress, User
from app.schemas.auth import (
    DeleteAccountRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.user import MeOut, MeUpdate, ProgressOut

logger = logging.getLogger("metalarm.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    # Deliberately identical for "no such email" and "wrong password". A
    # distinct message would turn this endpoint into an account-existence
    # oracle; see also burn_password_time() below.
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)

_INVALID_REFRESH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Refresh token is invalid or expired - sign in again",
    headers={"WWW-Authenticate": "Bearer"},
)


def _serialize_me(user: User) -> MeOut:
    """Assemble the identity payload.

    Rank and streak are DERIVED here rather than read from the cached columns.
    A user who lapses while away never issues a request, so nothing updates
    those columns - reading them raw would show a dormant user an S rank and a
    streak they no longer hold.
    """
    progress = user.progress
    today = local_now(user.timezone).date()

    streak = leveling.effective_streak(
        progress.current_streak, progress.last_completed_on, today
    )
    rank = leveling.rank_for(progress.current_level, streak)
    earned_by_level = leveling.rank_by_level(progress.current_level)
    next_up = leveling.next_rank_requirement(progress.current_level, streak)
    into, needed = leveling.progress_into_level(progress.total_xp)

    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        timezone=user.timezone,
        created_at=user.created_at,
        weight_unit=user.weight_unit,
        progress=ProgressOut(
            total_xp=progress.total_xp,
            current_level=progress.current_level,
            points_balance=progress.points_balance,
            longest_streak=progress.longest_streak,
            last_completed_on=progress.last_completed_on,
            xp_into_level=into,
            xp_for_next_level=needed,
            current_streak=streak,
            streak_is_active=leveling.streak_is_active(
                progress.last_completed_on, today
            ),
            rank=rank.value,
            rank_by_level=earned_by_level.value,
            next_rank=next_up[0].value if next_up else None,
            next_rank_level=next_up[1] if next_up else None,
            next_rank_streak=next_up[2] if next_up else None,
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


def _limit_login(request: Request, email: str) -> None:
    rate_limit.enforce(rate_limit.LOGIN_PER_IP, rate_limit.client_ip(request))
    rate_limit.enforce(rate_limit.LOGIN_PER_EMAIL, normalize_email(email))


def _start_session(db: DbSession, user: User) -> AuthSession:
    """One row per signed-in device; its id rides in every token it gets."""
    session = AuthSession(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _issue_tokens(user: User, session_id: uuid.UUID) -> TokenResponse:
    access, expires_in = create_access_token(user.id, user.token_version, session_id)
    refresh, refresh_expires_in = create_refresh_token(user.id, user.token_version, session_id)
    return TokenResponse(
        access_token=access,
        expires_in=expires_in,
        refresh_token=refresh,
        refresh_expires_in=refresh_expires_in,
    )


@router.post("/signup", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, db: DbSession) -> MeOut:
    """Create an account and its progression row.

    Both rows are written in one transaction: a User without LevelProgress
    would break every progression read path, and there is no valid state in
    which one exists without the other.
    """
    rate_limit.enforce(rate_limit.SIGNUP_PER_IP, rate_limit.client_ip(request))
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
        rank=leveling.rank_for(1, 0),
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
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    """JSON login - the endpoint the Reflex frontend and the iOS app use."""
    _limit_login(request, payload.email)
    user = _authenticate(db, payload.email, payload.password)
    return _issue_tokens(user, _start_session(db, user).id)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: DbSession,
) -> TokenResponse:
    """OAuth2 password-flow login, form-encoded.

    Exists so /docs' Authorize button works for manual testing. Identical
    semantics to /login; OAuth2 mandates the field be named `username`, which
    here carries the email.
    """
    _limit_login(request, form.username)
    user = _authenticate(db, form.username, form.password)
    return _issue_tokens(user, _start_session(db, user).id)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> TokenResponse:
    """Swap a refresh token for a new access + refresh pair on the same device
    session. Fails once that device has signed out, or once the user has signed
    out everywhere (token_version bumped)."""
    rate_limit.enforce(rate_limit.REFRESH_PER_IP, rate_limit.client_ip(request))
    claims = _refresh_claims(payload.refresh_token)
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active or claims.get("tv", 0) != user.token_version:
        raise _INVALID_REFRESH

    # A token from before device sessions has no session to keep it alive (and
    # none that sign-out could revoke), so it must sign in again.
    if "sid" not in claims or not session_is_live(db, user.id, claims["sid"]):
        raise _INVALID_REFRESH

    return _issue_tokens(user, uuid.UUID(str(claims["sid"])))


def _refresh_claims(token: str) -> dict:
    """Decode a refresh token; any failure, or an access token, is a 401."""
    try:
        claims = decode_token(token)
        uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise _INVALID_REFRESH from None
    # An access token must not be able to mint new tokens.
    if claims.get("typ") != REFRESH_TOKEN_TYPE:
        raise _INVALID_REFRESH
    return claims


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    payload: LogoutRequest | None = None,
) -> None:
    """Sign out of this device only: its access and refresh tokens stop
    working, every other device stays signed in.

    Send the refresh token in the body - it is still valid after the access
    token has expired. A bearer access token alone also works.
    """
    if payload is not None:
        claims = _refresh_claims(payload.refresh_token)
        user = db.get(User, uuid.UUID(claims["sub"]))
        if user is None or claims.get("tv", 0) != user.token_version:
            return  # already signed out everywhere, or the account is gone
    else:
        user = get_current_user(db, token)
        claims = decode_token(token or "")

    session_id = claims.get("sid")
    if session_id is None:
        # A token from before device sessions has no session to revoke, so end
        # it the only way left: every token issued so far stops working.
        user.token_version += 1
        db.commit()
        logger.info("user %s signed out a pre-session token; all tokens revoked", user.id)
        return
    try:
        session = db.get(AuthSession, uuid.UUID(str(session_id)))
    except ValueError:
        return
    if session is not None and session.user_id == user.id and session.revoked_at is None:
        session.revoked_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
        logger.info("user %s signed out session %s", user.id, session.id)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_everywhere(current_user: CurrentUser, db: DbSession) -> None:
    """Sign out on every device: every access and refresh token issued so far
    stops working."""
    current_user.token_version += 1
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == current_user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=dt.datetime.now(dt.timezone.utc))
    )
    db.commit()
    logger.info("user %s signed out everywhere", current_user.id)


@router.get("/me", response_model=MeOut)
def read_me(current_user: CurrentUser) -> MeOut:
    """The signed-in user plus progression - what the Stat Panel renders."""
    return _serialize_me(current_user)


@router.patch("/me", response_model=MeOut)
def update_me(payload: MeUpdate, current_user: CurrentUser, db: DbSession) -> MeOut:
    """Update account preferences - currently the workout weight unit.

    Stored on the account rather than in the browser, so the choice follows
    the user across devices.
    """
    if payload.weight_unit is not None:
        current_user.weight_unit = payload.weight_unit.value
    db.commit()
    db.refresh(current_user)
    return _serialize_me(current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DeleteAccountRequest, current_user: CurrentUser, db: DbSession
) -> None:
    """Permanently delete the account and everything it owns.

    Required by the App Store for any app that offers account creation. Every
    user-owned table (device sessions included) cascades on users.id. Parties
    are handled first: one the user owns goes to its longest-serving member
    instead of being deleted with its owner.
    """
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password is incorrect")

    memberships = db.execute(
        select(PartyMembership).where(PartyMembership.user_id == current_user.id)
    ).scalars().all()
    party_ids = []
    for membership in memberships:
        party = db.get(Party, membership.party_id)
        if party is not None:
            release_membership(db, party, membership)
            party_ids.append(party.id)

    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    # Cached party boards would otherwise still list the deleted user.
    for party_id in party_ids:
        leaderboard.drop(party_id)
    logger.info("user %s deleted their account", user_id)
