"""Duels: challenge someone (or a pace), and the activity feed.

Judging is lazy, like a league week (app/core/leagues.py): every read of a
duel whose window has closed judges it, awards the winner, and writes the feed
entry - inside the same transaction, holding the level_progress lock, so two
simultaneous reads cannot both award. The ledger's partial UNIQUE on
(source_type, source_id) is the backstop underneath that.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import activity, duels as engine
from app.core.progression import apply_completion, lock_progress
from app.models.duel import ActivityEvent, ActivityType, Duel, DuelMetric, DuelStatus
from app.models.party import PartyMembership
from app.models.user import User
from app.models.workout import PointsLedgerEntry
from app.models.workout_enums import LedgerSource
from app.schemas.duel import (
    ActivityOut,
    DuelCreate,
    DuelListOut,
    DuelOut,
    DuelSide,
    FeedOut,
)

router = APIRouter(tags=["duels"])

RIVAL_NAME = "Your rival"


def _user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def _name(db: Session, user_id: uuid.UUID | None) -> str:
    person = _user(db, user_id) if user_id else None
    return person.display_name if person else RIVAL_NAME


def _mine(db: Session, duel_id: uuid.UUID, user: User) -> Duel:
    duel = db.get(Duel, duel_id)
    if duel is None or user.id not in {duel.challenger_id, duel.opponent_id}:
        # Not "forbidden": a duel you are not in should not be distinguishable
        # from one that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duel not found")
    return duel


def _award_win(db: Session, duel: Duel, winner_id: uuid.UUID, now: dt.datetime) -> int:
    """Pay the winner, once. Returns the points actually awarded."""
    winner = _user(db, winner_id)
    if winner is None:
        return 0
    progress = lock_progress(db, winner_id)
    entry = PointsLedgerEntry(
        user_id=winner_id,
        source_type=LedgerSource.DUEL_WON.value,
        source_id=duel.id,
        points=engine.WIN_POINTS,
        reason=f"Won a {duel.metric} duel",
    )
    db.add(entry)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        # Already paid for this duel - another request judged it first.
        return 0
    apply_completion(
        progress, xp=0, points=engine.WIN_POINTS, completed_at=now, tz_name=winner.timezone
    )
    return engine.WIN_POINTS


def _judge(db: Session, duel: Duel, now: dt.datetime) -> int:
    """Close a duel whose window has passed. Returns points awarded, if any."""
    if not engine.is_over(duel, now):
        return 0
    winner_id = engine.decide(db, duel, now)
    duel.status = DuelStatus.COMPLETED.value
    duel.resolved_at = now
    duel.winner_id = winner_id
    awarded = 0
    if winner_id is not None:
        awarded = _award_win(db, duel, winner_id, now)
        activity.record(
            db,
            user_id=winner_id,
            event_type=ActivityType.DUEL_WON,
            headline=f"Won a {duel.metric} duel",
            source_id=duel.id,
            at=now,
        )
    db.commit()
    db.refresh(duel)
    return awarded


def _render(db: Session, duel: Duel, now: dt.datetime, *, awarded: int | None = None) -> DuelOut:
    at = min(now, duel.window_end)
    standing = engine.standing(db, duel, at)
    return DuelOut(
        id=duel.id,
        metric=duel.metric,
        status=duel.status,
        window_start=duel.window_start,
        window_end=duel.window_end,
        challenger=DuelSide(
            user_id=duel.challenger_id,
            display_name=_name(db, duel.challenger_id),
            score=standing.challenger,
        ),
        opponent=DuelSide(
            user_id=duel.opponent_id,
            display_name=RIVAL_NAME if duel.is_ai_opponent else _name(db, duel.opponent_id),
            score=standing.opponent,
            is_rival=duel.is_ai_opponent,
        ),
        winner_id=duel.winner_id,
        is_draw=duel.status == DuelStatus.COMPLETED.value and duel.winner_id is None,
        resolved_at=duel.resolved_at,
        points_awarded=awarded or None,
    )


@router.post("/duels", response_model=DuelOut, status_code=status.HTTP_201_CREATED)
def create_duel(payload: DuelCreate, current_user: CurrentUser, db: DbSession) -> DuelOut:
    """Challenge a party member, or the rival.

    Only people you share a party with: an open challenge to any account would
    be a way to find out whether an account exists, and a stranger's challenge
    is noise rather than a game.
    """
    now = dt.datetime.now(dt.timezone.utc)
    length = dt.timedelta(days=payload.days)

    if payload.against_rival:
        duel = Duel(
            challenger_id=current_user.id,
            opponent_id=None,
            is_ai_opponent=True,
            metric=payload.metric.value,
            window_start=now,
            window_end=now + length,
            # A rival needs no acceptance, so it starts straight away.
            status=DuelStatus.ACTIVE.value,
            rival_target=engine.as_decimal(
                engine.rival_target(db, current_user.id, payload.metric.value, length, now)
            ),
        )
    else:
        if payload.opponent_id == current_user.id:
            raise HTTPException(status_code=422, detail="You cannot duel yourself")
        mine = set(activity.parties_of(db, current_user.id))
        theirs = set(
            db.scalars(
                select(PartyMembership.party_id).where(
                    PartyMembership.user_id == payload.opponent_id
                )
            )
        )
        if not mine & theirs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You can only challenge someone in your party",
            )
        duel = Duel(
            challenger_id=current_user.id,
            opponent_id=payload.opponent_id,
            is_ai_opponent=False,
            metric=payload.metric.value,
            window_start=now,
            window_end=now + length,
            status=DuelStatus.PENDING.value,
        )
    db.add(duel)
    db.commit()
    db.refresh(duel)
    return _render(db, duel, now)


@router.get("/duels", response_model=DuelListOut)
def list_duels(current_user: CurrentUser, db: DbSession) -> DuelListOut:
    """Every duel the caller is in, judging any whose window has closed."""
    now = dt.datetime.now(dt.timezone.utc)
    rows = list(
        db.scalars(
            select(Duel)
            .where((Duel.challenger_id == current_user.id) | (Duel.opponent_id == current_user.id))
            .order_by(Duel.window_end.desc())
        )
    )
    out = DuelListOut(active=[], pending=[], completed=[])
    for duel in rows:
        awarded = _judge(db, duel, now)
        rendered = _render(db, duel, now, awarded=awarded if duel.winner_id == current_user.id else None)
        if duel.status == DuelStatus.ACTIVE.value:
            out.active.append(rendered)
        elif duel.status == DuelStatus.PENDING.value:
            out.pending.append(rendered)
        elif duel.status == DuelStatus.COMPLETED.value:
            out.completed.append(rendered)
    return out


@router.get("/duels/{duel_id}", response_model=DuelOut)
def get_duel(duel_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> DuelOut:
    now = dt.datetime.now(dt.timezone.utc)
    duel = _mine(db, duel_id, current_user)
    awarded = _judge(db, duel, now)
    return _render(db, duel, now, awarded=awarded if duel.winner_id == current_user.id else None)


@router.post("/duels/{duel_id}/accept", response_model=DuelOut)
def accept_duel(duel_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> DuelOut:
    """Take up a challenge. The window starts NOW, not when it was sent.

    Otherwise a challenge left sitting for six days would hand the challenger
    almost the whole window to themselves.
    """
    now = dt.datetime.now(dt.timezone.utc)
    duel = _mine(db, duel_id, current_user)
    if duel.opponent_id != current_user.id:
        raise HTTPException(status_code=409, detail="Only the person challenged can accept")
    if duel.status != DuelStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"This duel is {duel.status}")
    length = duel.window_end - duel.window_start
    duel.window_start = now
    duel.window_end = now + length
    duel.status = DuelStatus.ACTIVE.value
    db.commit()
    db.refresh(duel)
    return _render(db, duel, now)


@router.post("/duels/{duel_id}/decline", response_model=DuelOut)
def decline_duel(duel_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> DuelOut:
    """Turn one down - or withdraw one you sent, before it is accepted."""
    now = dt.datetime.now(dt.timezone.utc)
    duel = _mine(db, duel_id, current_user)
    if duel.status != DuelStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"This duel is {duel.status}")
    duel.status = DuelStatus.DECLINED.value
    db.commit()
    db.refresh(duel)
    return _render(db, duel, now)


@router.get("/feed", response_model=FeedOut)
def get_feed(
    current_user: CurrentUser,
    db: DbSession,
    party_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    before: dt.datetime | None = Query(default=None),
) -> FeedOut:
    """What the caller and their parties have been up to, newest first."""
    if party_id is not None:
        member = db.scalar(
            select(PartyMembership)
            .where(PartyMembership.party_id == party_id)
            .where(PartyMembership.user_id == current_user.id)
        )
        if member is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

    rows = activity.feed(db, current_user.id, party_id=party_id, limit=limit, before=before)
    names = {
        person.id: person.display_name
        for person in db.scalars(
            select(User).where(User.id.in_({row.user_id for row in rows} or {uuid.uuid4()}))
        )
    }
    entries = [
        ActivityOut(
            id=row.id,
            user_id=row.user_id,
            display_name=names.get(row.user_id, "Someone"),
            event_type=row.event_type,
            headline=row.headline,
            party_id=row.party_id,
            source_id=row.source_id,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return FeedOut(
        entries=entries,
        next_before=entries[-1].created_at if len(entries) == limit else None,
    )
