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
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.api.routes import social as social_routes
from app.core import activity, social
from app.core import duels as engine
from app.core import workout_streaks as streaks
from app.core.periods import resolve_timezone
from app.core.progression import apply_completion, lock_progress
from app.models.duel import (
    FAIR_METRICS,
    ActivityEvent,
    ActivityType,
    Duel,
    DuelMetric,
    DuelStatus,
)
from app.models.party import PartyMembership
from app.models.user import User
from app.models.workout import PointsLedgerEntry
from app.models.workout_enums import LedgerSource
from app.schemas.social import UserCard
from app.schemas.duel import (
    ActivityOut,
    BreakdownLine,
    DuelCreate,
    DuelListOut,
    DuelMode,
    DuelModesOut,
    DuelOut,
    DuelSide,
    FeedOut,
)

router = APIRouter(tags=["duels"])

RIVAL_NAME = "Your rival"

# The mode picker's copy, and the detail screen's "what counts" line.
MODES: dict[str, tuple[str, str, str]] = {
    DuelMetric.CONSISTENCY.value: (
        "Consistency",
        "Who shows up more - load doesn't matter",
        "One point per day with a workout of 3+ working sets. Ties go to total working sets.",
    ),
    DuelMetric.PROGRESS.value: (
        "Progress",
        "Who improves more vs. their own best",
        "% gained on each lift's estimated 1RM over your best from the 4 weeks before, up to +10% per lift.",
    ),
    DuelMetric.RELATIVE_VOLUME.value: (
        "Volume vs. your average",
        "Who does more than they usually do",
        "This duel's working volume as a % of your own average over the 4 weeks before.",
    ),
    DuelMetric.VOLUME.value: ("Volume", "Most kilograms lifted", "Kilograms lifted in working sets."),
    DuelMetric.SETS.value: ("Sets", "Most working sets", "Working sets logged."),
    DuelMetric.SESSIONS.value: ("Sessions", "Most workouts finished", "Workouts finished."),
}
_LIVE = (DuelStatus.PENDING.value, DuelStatus.ACTIVE.value)
_CLOSED = (DuelStatus.DECLINED.value, DuelStatus.EXPIRED.value, DuelStatus.CANCELLED.value)
_DUEL_REWARDS = (
    LedgerSource.DUEL_WON.value,
    LedgerSource.DUEL_DRAW.value,
    LedgerSource.DUEL_PARTICIPATION.value,
)


def _user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def _name(db: Session, user_id: uuid.UUID | None) -> str:
    person = _user(db, user_id) if user_id else None
    return person.display_name if person else RIVAL_NAME


def _live_count(db: Session, user_id: uuid.UUID, *, active_only: bool = False) -> int:
    statuses = (DuelStatus.ACTIVE.value,) if active_only else _LIVE
    return int(
        db.scalar(
            select(func.count(Duel.id)).where(
                (Duel.challenger_id == user_id) | (Duel.opponent_id == user_id),
                Duel.status.in_(statuses),
                Duel.is_ai_opponent.is_(False),
                Duel.metric.in_(FAIR_METRICS),
            )
        )
        or 0
    )


def _mine(db: Session, duel_id: uuid.UUID, user: User) -> Duel:
    duel = db.get(Duel, duel_id)
    if duel is None or user.id not in {duel.challenger_id, duel.opponent_id}:
        # Not "forbidden": a duel you are not in should not be distinguishable
        # from one that does not exist.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Duel not found")
    return duel


def _rewards_this_week(db: Session, person: User, now: dt.datetime) -> int:
    """Duel rewards already paid to `person` this ISO week, their timezone."""
    week = streaks.week_key(now, person.timezone)
    monday = dt.date.fromisocalendar(*map(int, week.replace("-W", " ").split()), 1)
    start = dt.datetime.combine(monday, dt.time.min, tzinfo=resolve_timezone(person.timezone))
    return int(
        db.scalar(
            select(func.count(PointsLedgerEntry.id)).where(
                PointsLedgerEntry.user_id == person.id,
                PointsLedgerEntry.source_type.in_(_DUEL_REWARDS),
                PointsLedgerEntry.created_at >= start,
            )
        )
        or 0
    )


def _pay(
    db: Session,
    duel: Duel,
    user_id: uuid.UUID,
    source: LedgerSource,
    points: int,
    now: dt.datetime,
    *,
    capped: bool,
) -> int:
    """Pay one side of a settled duel, once. Returns the points awarded.

    `capped`: the fair modes' rewards stop at REWARDS_PER_WEEK. The original
    modes pay their win as they always have."""
    person = _user(db, user_id)
    if person is None:
        return 0
    progress = lock_progress(db, user_id)
    if capped and _rewards_this_week(db, person, now) >= engine.REWARDS_PER_WEEK:
        return 0
    label = MODES.get(duel.metric, (duel.metric,))[0].lower()
    reason = {
        LedgerSource.DUEL_WON: f"Won a {label} duel",
        LedgerSource.DUEL_DRAW: f"Drew a {label} duel",
        LedgerSource.DUEL_PARTICIPATION: f"Fought a {label} duel",
    }[source]
    entry = PointsLedgerEntry(
        user_id=user_id,
        source_type=source.value,
        source_id=duel.id if source is LedgerSource.DUEL_WON else engine.reward_key(duel, user_id),
        points=points,
        reason=reason,
    )
    db.add(entry)
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        # Already paid for this duel - another request judged it first.
        return 0
    apply_completion(progress, xp=0, points=points, completed_at=now, tz_name=person.timezone)
    return points


def _award_win(db: Session, duel: Duel, winner_id: uuid.UUID, now: dt.datetime) -> int:
    """Pay the winner, once. Returns the points actually awarded."""
    return _pay(
        db, duel, winner_id, LedgerSource.DUEL_WON, engine.WIN_POINTS, now,
        capped=duel.metric in FAIR_METRICS,
    )


def _judge(db: Session, duel: Duel, now: dt.datetime) -> int:
    """Close a duel whose window has passed, or expire a challenge nobody
    answered. Returns points awarded to the winner, if any."""
    if engine.is_stale(duel, now):
        duel.status = DuelStatus.EXPIRED.value
        db.commit()
        db.refresh(duel)
        return 0
    if not engine.is_over(duel, now):
        return 0
    winner_id = engine.decide(db, duel, now)
    duel.status = DuelStatus.COMPLETED.value
    duel.resolved_at = now
    duel.winner_id = winner_id
    awarded = 0
    if duel.metric in FAIR_METRICS and duel.opponent_id is not None:
        sides = (duel.challenger_id, duel.opponent_id)
        if winner_id is None:
            for side in sides:
                _pay(db, duel, side, LedgerSource.DUEL_DRAW, engine.DRAW_POINTS, now, capped=True)
        else:
            loser = sides[1] if winner_id == sides[0] else sides[0]
            if engine.trained_in_window(db, duel, loser):
                _pay(
                    db, duel, loser, LedgerSource.DUEL_PARTICIPATION,
                    engine.PARTICIPATION_POINTS, now, capped=True,
                )
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


def _lines(detail) -> list[BreakdownLine]:
    return [BreakdownLine(label=l.label, value=l.value) for l in detail.breakdown] if detail else []


def _reward(db: Session, duel: Duel, viewer: User | None) -> tuple[int | None, str | None]:
    if viewer is None or duel.status != DuelStatus.COMPLETED.value:
        return None, None
    row = db.execute(
        select(PointsLedgerEntry.points, PointsLedgerEntry.source_type).where(
            PointsLedgerEntry.user_id == viewer.id,
            PointsLedgerEntry.source_type.in_(_DUEL_REWARDS),
            PointsLedgerEntry.source_id.in_([duel.id, engine.reward_key(duel, viewer.id)]),
        )
    ).first()
    return (row.points, row.source_type) if row else (None, None)


def _render(
    db: Session, duel: Duel, now: dt.datetime, *, awarded: int | None = None,
    viewer: User | None = None,
) -> DuelOut:
    at = min(now, duel.window_end)
    # A duel that never ran has no score worth summing.
    standing = (
        engine.Standing(0.0, 0.0, None) if duel.status in _CLOSED else engine.standing(db, duel, at)
    )
    reward_points, reward_type = _reward(db, duel, viewer)
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
            breakdown=_lines(standing.challenger_detail),
            tiebreak=standing.challenger_detail.tiebreak
            if duel.metric == DuelMetric.CONSISTENCY.value and standing.challenger_detail
            else None,
        ),
        opponent=DuelSide(
            user_id=duel.opponent_id,
            display_name=RIVAL_NAME if duel.is_ai_opponent else _name(db, duel.opponent_id),
            score=standing.opponent,
            is_rival=duel.is_ai_opponent,
            breakdown=_lines(standing.opponent_detail),
            tiebreak=standing.opponent_detail.tiebreak
            if duel.metric == DuelMetric.CONSISTENCY.value and standing.opponent_detail
            else None,
        ),
        winner_id=duel.winner_id,
        is_draw=duel.status == DuelStatus.COMPLETED.value and duel.winner_id is None,
        resolved_at=duel.resolved_at,
        points_awarded=awarded or None,
        reward_points=reward_points,
        reward_type=reward_type,
        rules=MODES.get(duel.metric, ("", "", ""))[2],
        expires_at=duel.created_at + engine.ACCEPT_WITHIN
        if duel.status == DuelStatus.PENDING.value
        else None,
    )


def _opponent_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Who may be challenged: friends (mutual follows) and party mates."""
    return social.friend_ids(db, user_id) | social.party_mates(db, user_id)


@router.get("/duels/opponents", response_model=list[UserCard])
def duel_opponents(current_user: CurrentUser, db: DbSession) -> list[UserCard]:
    """Everyone the caller can challenge, by name. A short list (friends and
    party mates), so not paged."""
    ids = _opponent_ids(db, current_user.id)
    users = list(db.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True))
                            .order_by(User.display_name))) if ids else []
    return social_routes.cards(db, current_user, users)


@router.post("/duels", response_model=DuelOut, status_code=status.HTTP_201_CREATED)
def create_duel(payload: DuelCreate, current_user: CurrentUser, db: DbSession) -> DuelOut:
    """Challenge a friend (a mutual follow), a party member, or the rival.

    Only people you know: an open challenge to any account would be a way to
    find out whether an account exists, and a stranger's challenge is noise
    rather than a game.
    """
    now = dt.datetime.now(dt.timezone.utc)
    length = dt.timedelta(days=payload.days)
    metric = payload.metric.value

    if metric in FAIR_METRICS and _live_count(db, current_user.id) >= engine.MAX_LIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have {engine.MAX_LIVE} duels going - finish one first",
        )

    if payload.against_rival:
        if metric in FAIR_METRICS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The rival races volume, sets or sessions - fair modes need a real opponent",
            )
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
        if payload.opponent_id not in _opponent_ids(db, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You can only challenge a friend (you follow each other) or a party member",
            )
        opponent = _user(db, payload.opponent_id)  # type: ignore[arg-type]
        for side in (current_user, opponent):
            reason = engine.ineligible(db, side, metric, now) if side else None
            if reason:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reason
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
    db.flush()
    if duel.opponent_id is not None:
        social.notify(db, duel.opponent_id, "duel_challenge", actor_id=current_user.id,
                      target_type="duel", target_id=duel.id, detail=MODES[metric][0])
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
        rendered = _render(
            db, duel, now, awarded=awarded if duel.winner_id == current_user.id else None,
            viewer=current_user,
        )
        if duel.status == DuelStatus.ACTIVE.value:
            out.active.append(rendered)
        elif duel.status == DuelStatus.PENDING.value:
            out.pending.append(rendered)
        elif duel.status == DuelStatus.COMPLETED.value:
            out.completed.append(rendered)
        else:
            out.closed.append(rendered)
    return out


@router.get("/duels/modes", response_model=DuelModesOut)
def duel_modes(
    current_user: CurrentUser,
    db: DbSession,
    opponent_id: uuid.UUID | None = Query(default=None),
) -> DuelModesOut:
    """Every mode, with whether a duel against `opponent_id` could use it and
    why not. Only fair modes need history; the rest are always open."""
    now = dt.datetime.now(dt.timezone.utc)
    opponent = _user(db, opponent_id) if opponent_id else None
    out = []
    for metric in (
        DuelMetric.CONSISTENCY, DuelMetric.PROGRESS, DuelMetric.RELATIVE_VOLUME,
        DuelMetric.VOLUME, DuelMetric.SETS, DuelMetric.SESSIONS,
    ):
        title, fairness, _ = MODES[metric.value]
        reason = engine.ineligible(db, current_user, metric.value, now)
        if reason is None and opponent is not None:
            reason = engine.ineligible(db, opponent, metric.value, now)
        out.append(
            DuelMode(metric=metric.value, title=title, fairness=fairness,
                     eligible=reason is None, reason=reason)
        )
    return DuelModesOut(modes=out)


@router.get("/duels/{duel_id}", response_model=DuelOut)
def get_duel(duel_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> DuelOut:
    now = dt.datetime.now(dt.timezone.utc)
    duel = _mine(db, duel_id, current_user)
    awarded = _judge(db, duel, now)
    return _render(
        db, duel, now, awarded=awarded if duel.winner_id == current_user.id else None,
        viewer=current_user,
    )


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
    if engine.is_stale(duel, now):
        _judge(db, duel, now)
        raise HTTPException(status_code=409, detail="This challenge has expired")
    if (
        duel.metric in FAIR_METRICS
        and _live_count(db, current_user.id, active_only=True) >= engine.MAX_LIVE
    ):
        raise HTTPException(
            status_code=409,
            detail=f"You already have {engine.MAX_LIVE} duels going - finish one first",
        )
    length = duel.window_end - duel.window_start
    duel.window_start = now
    duel.window_end = now + length
    duel.status = DuelStatus.ACTIVE.value
    # The fair modes measure from where each side stands as the window opens.
    engine.snapshot_baselines(db, duel, now)
    db.commit()
    db.refresh(duel)
    return _render(db, duel, now, viewer=current_user)


@router.post("/duels/{duel_id}/cancel", response_model=DuelOut)
def cancel_duel(duel_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> DuelOut:
    """Withdraw a challenge you sent, before it is accepted."""
    now = dt.datetime.now(dt.timezone.utc)
    duel = _mine(db, duel_id, current_user)
    if duel.challenger_id != current_user.id:
        raise HTTPException(status_code=409, detail="Only the challenger can cancel")
    if duel.status != DuelStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=f"This duel is {duel.status}")
    duel.status = DuelStatus.CANCELLED.value
    db.commit()
    db.refresh(duel)
    return _render(db, duel, now, viewer=current_user)


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
