"""Weekly leagues: twenty lifters, one week, promotion and relegation.

A user is placed in a league of at most `LEAGUE_SIZE` in their division. When
the week ends, the top `PROMOTE` move up a division and the bottom `DEMOTE`
move down. Scoring is the points ledger - the same points the wallet sees -
summed over the ISO week in UTC, so everyone on one board is measured over
exactly the same window (a per-timezone week would let someone's Sunday count
twice against someone else's).

**No cron.** The membership for the current week is created lazily the first
time the user looks, and that is the moment last week's result is judged. A
user who never opens the app has no membership for the weeks they missed,
which is the honest answer: they were not in a league. It is the same shape as
the streak grace logic - derive on read, store only the placement.

Standings are never stored. They are recomputed from the ledger, so a league
can never drift out of step with the wallet, and a reversal lands on the board
the moment it lands on the balance. A week's total cannot read negative.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import raids
from app.models.league import LeagueMembership
from app.models.user import LevelProgress, User
from app.models.workout import PointsLedgerEntry

LEAGUE_SIZE = 20
PROMOTE = 5
DEMOTE = 5
DIVISIONS = ("Bronze", "Silver", "Gold", "Platinum", "Diamond")
TOP_DIVISION = len(DIVISIONS) - 1


def division_label(division: int) -> str:
    return DIVISIONS[max(0, min(TOP_DIVISION, division))]


def week_bounds(week_key: str) -> tuple[dt.datetime, dt.datetime]:
    start = raids.week_start(week_key)
    return start, start + dt.timedelta(days=7)


def previous_week(week_key: str) -> str:
    return raids.week_key(raids.week_start(week_key) - dt.timedelta(days=1))


@dataclasses.dataclass(frozen=True)
class Standing:
    position: int
    user: User
    progress: LevelProgress
    points: int
    is_me: bool


@dataclasses.dataclass(frozen=True)
class League:
    week_key: str
    division: int
    division_label: str
    group_no: int
    ends_at: dt.datetime
    # Where the user finished last week, when that is what placed them here.
    promoted_from: int | None
    promote_cutoff: int
    demote_cutoff: int
    standings: list[Standing]


def _points(
    db: Session, user_ids: list[uuid.UUID], start: dt.datetime, end: dt.datetime
) -> dict[uuid.UUID, int]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(
            PointsLedgerEntry.user_id,
            func.coalesce(func.sum(PointsLedgerEntry.points), 0),
        )
        .where(
            PointsLedgerEntry.user_id.in_(user_ids),
            PointsLedgerEntry.created_at >= start,
            PointsLedgerEntry.created_at < end,
        )
        .group_by(PointsLedgerEntry.user_id)
    ).all()
    # A reversal of an older award can outweigh this week's earnings; a board
    # position is not the place to show that.
    return {user_id: max(0, int(total)) for user_id, total in rows}


def _members(db: Session, week_key: str, division: int, group_no: int) -> list[LeagueMembership]:
    return list(
        db.scalars(
            select(LeagueMembership).where(
                LeagueMembership.week_key == week_key,
                LeagueMembership.division == division,
                LeagueMembership.group_no == group_no,
            )
        )
    )


def _ordered(
    members: list[LeagueMembership], points: dict[uuid.UUID, int]
) -> list[LeagueMembership]:
    # Ties break on the id so an order is stable between requests.
    return sorted(members, key=lambda m: (-points.get(m.user_id, 0), str(m.user_id)))


def judge(db: Session, membership: LeagueMembership) -> tuple[int, int]:
    """(division for next week, position finished) for a finished week."""
    members = _members(db, membership.week_key, membership.division, membership.group_no)
    start, end = week_bounds(membership.week_key)
    points = _points(db, [m.user_id for m in members], start, end)
    order = _ordered(members, points)
    position = next(
        index for index, m in enumerate(order, start=1) if m.user_id == membership.user_id
    )

    division = membership.division
    if position <= PROMOTE:
        division = min(TOP_DIVISION, division + 1)
    elif position > max(0, len(order) - DEMOTE):
        division = max(0, division - 1)
    return division, position


def _place(
    db: Session,
    user_id: uuid.UUID,
    week_key: str,
    division: int,
    promoted_from: int | None,
) -> LeagueMembership:
    """Put the user in the first league of their division with room."""
    counts = db.execute(
        select(LeagueMembership.group_no, func.count(LeagueMembership.id))
        .where(LeagueMembership.week_key == week_key, LeagueMembership.division == division)
        .group_by(LeagueMembership.group_no)
        .order_by(LeagueMembership.group_no)
    ).all()
    group_no = 0
    for number, filled in counts:
        if filled < LEAGUE_SIZE:
            group_no = number
            break
    else:
        group_no = (max(number for number, _ in counts) + 1) if counts else 0

    # Two requests from the same user can race here; the unique constraint
    # settles it and the row that landed is what we read back.
    db.execute(
        pg_insert(LeagueMembership)
        .values(
            user_id=user_id,
            week_key=week_key,
            division=division,
            group_no=group_no,
            promoted_from=promoted_from,
        )
        .on_conflict_do_nothing(constraint="uq_league_memberships_user_week")
    )
    db.flush()
    return db.execute(
        select(LeagueMembership).where(
            LeagueMembership.user_id == user_id, LeagueMembership.week_key == week_key
        )
    ).scalar_one()


def ensure_membership(db: Session, user: User, now: dt.datetime) -> LeagueMembership:
    """This week's placement, creating it (and judging last week) on demand."""
    week = raids.week_key(now)
    existing = db.execute(
        select(LeagueMembership).where(
            LeagueMembership.user_id == user.id, LeagueMembership.week_key == week
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    last = db.execute(
        select(LeagueMembership).where(
            LeagueMembership.user_id == user.id,
            LeagueMembership.week_key == previous_week(week),
        )
    ).scalar_one_or_none()
    if last is None:
        # A first league, or a return after a gap: start at the bottom.
        return _place(db, user.id, week, 0, None)
    division, position = judge(db, last)
    return _place(db, user.id, week, division, position)


def current(db: Session, user: User, now: dt.datetime | None = None) -> League:
    now = now or dt.datetime.now(dt.timezone.utc)
    membership = ensure_membership(db, user, now)
    members = _members(db, membership.week_key, membership.division, membership.group_no)
    start, end = week_bounds(membership.week_key)
    points = _points(db, [m.user_id for m in members], start, end)

    rows = {
        row.User.id: row
        for row in db.execute(
            select(User, LevelProgress)
            .join(LevelProgress, LevelProgress.user_id == User.id)
            .where(User.id.in_([m.user_id for m in members]))
        )
    }
    standings = [
        Standing(
            position=position,
            user=rows[m.user_id].User,
            progress=rows[m.user_id].LevelProgress,
            points=points.get(m.user_id, 0),
            is_me=m.user_id == user.id,
        )
        for position, m in enumerate(_ordered(members, points), start=1)
        if m.user_id in rows
    ]
    return League(
        week_key=membership.week_key,
        division=membership.division,
        division_label=division_label(membership.division),
        group_no=membership.group_no,
        ends_at=end,
        promoted_from=membership.promoted_from,
        promote_cutoff=PROMOTE,
        demote_cutoff=max(0, len(standings) - DEMOTE),
        standings=standings,
    )
