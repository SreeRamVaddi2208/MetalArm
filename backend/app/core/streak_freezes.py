"""Streak freezes: a held token that covers one week that fell short.

The weekly streak (workout_streaks.py) already forgives rest DAYS - it only
asks for STREAK_SESSIONS_PER_WEEK sessions a week. A freeze forgives a rest
WEEK: deload, illness, travel. Without one, a single short week after months
of training resets the count to zero, which is exactly when people quit.

**Settled lazily, a closed week at a time.** MetalArm has no cron (see
app/core/leagues.py), so freezes are worked out the next time anyone looks at
the streak. Only weeks that have ENDED are settled, because only then is it
known whether they fell short - and only then are their sessions final, so an
earn never has to be taken back because a set was deleted afterwards.

**Automatic, no activation.** A short week that would break a live streak is
covered if a freeze is held. There is nothing to remember to tap.

**Only weeks after the user first met the feature.** `users.freeze_settled_
through` starts at the week before the first settle, so a long history does
not retroactively earn freezes and spend them on gaps from a year ago.

Everything is an append-only StreakFreezeEvent; the balance is their sum.
`settle()` is pure, and the store half below only loads its inputs and writes
what it returns.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Mapping, Set

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import workout_rules as rules
from app.core import workout_store as store
from app.core import workout_streaks as streaks
from app.models.quest_board import (
    AssignmentStatus,
    FreezeReason,
    QuestAssignment,
    QuestPeriod,
    StreakFreezeEvent,
)
from app.models.user import User

# A user back after a long absence: settling weeks one at a time is cheap, but
# not free, and two years of empty weeks would all just break the streak.
MAX_WEEKS_PER_SETTLE = 104


@dataclasses.dataclass(frozen=True)
class FreezeEvent:
    week: str
    delta: int
    reason: FreezeReason


def settle(
    weeks: list[str],
    *,
    sessions_per_week: Mapping[str, int],
    covered: Set[str],
    earned: Set[tuple[str, FreezeReason]],
    balance: int,
    quests_done_weeks: Set[str],
    target: int = rules.STREAK_SESSIONS_PER_WEEK,
    every: int = rules.FREEZE_EARN_EVERY_WEEKS,
    cap: int = rules.FREEZE_CAP,
) -> list[FreezeEvent]:
    """The events closing `weeks` produces, in order.

    `weeks` are closed ISO weeks, oldest first, none settled before. Per week:
    a short week that would break a live streak spends a freeze if one is
    held; a counting week that lands the run on a multiple of `every` earns
    one; finishing the week's quests earns one. Earning at the cap earns
    nothing - the freeze is not banked for later.
    """
    covered = set(covered)
    out: list[FreezeEvent] = []

    def earn(week: str, reason: FreezeReason) -> None:
        nonlocal balance
        if balance >= cap or (week, reason) in earned:
            return
        balance += 1
        out.append(FreezeEvent(week, 1, reason))

    for week in weeks:
        if sessions_per_week.get(week, 0) >= target:
            run = streaks.run_ending(sessions_per_week, week, covered, target)
            if run > 0 and run % every == 0:
                earn(week, FreezeReason.STREAK_MILESTONE)
        elif (
            week not in covered
            and balance > 0
            and streaks.run_ending(sessions_per_week, streaks.previous_week(week), covered, target)
            > 0
        ):
            balance -= 1
            covered.add(week)
            out.append(FreezeEvent(week, -1, FreezeReason.MISSED_WEEK_COVERED))
        if week in quests_done_weeks:
            earn(week, FreezeReason.WEEKLY_QUESTS_COMPLETE)
    return out


def weeks_to_next(streak_weeks: int, every: int = rules.FREEZE_EARN_EVERY_WEEKS) -> int:
    """Counting weeks still needed before the streak milestone that earns one."""
    return every - streak_weeks % every


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FreezeState:
    balance: int
    covered: frozenset[str]


def state(db: Session, user_id) -> FreezeState:
    db.flush()
    rows = db.execute(
        select(StreakFreezeEvent.week_key, StreakFreezeEvent.delta).where(
            StreakFreezeEvent.user_id == user_id
        )
    ).all()
    return FreezeState(
        balance=sum(r.delta for r in rows),
        covered=frozenset(r.week_key for r in rows if r.delta < 0),
    )


def _quests_done_weeks(db: Session, user_id, weeks: list[str]) -> set[str]:
    rows = db.execute(
        select(QuestAssignment.period_key, func.count(QuestAssignment.id))
        .where(
            QuestAssignment.user_id == user_id,
            QuestAssignment.period == QuestPeriod.WEEKLY.value,
            QuestAssignment.period_key.in_(weeks),
            QuestAssignment.status == AssignmentStatus.COMPLETED.value,
        )
        .group_by(QuestAssignment.period_key)
    ).all()
    return {key for key, done in rows if done >= rules.WEEKLY_QUESTS}


def settle_user(db: Session, user: User, now: dt.datetime) -> FreezeState:
    """Settle every week that has closed since the last settle, then return
    the user's freeze state. Does not commit.

    Callers hold the level_progress lock, which serialises settles for one
    user; uq_streak_freeze_once is the guarantee underneath it, and ON
    CONFLICT DO NOTHING keeps a lost race from failing the request.
    """
    current = streaks.week_key(now, user.timezone)
    last_closed = streaks.previous_week(current)
    if user.freeze_settled_through is None:
        user.freeze_settled_through = last_closed
        return state(db, user.id)
    if user.freeze_settled_through >= last_closed:
        # ISO week keys sort as strings: zero-padded week, four-digit year.
        return state(db, user.id)

    weeks: list[str] = []
    key = streaks.next_week(user.freeze_settled_through)
    while key <= last_closed:
        weeks.append(key)
        key = streaks.next_week(key)
    weeks = weeks[-MAX_WEEKS_PER_SETTLE:]

    before = state(db, user.id)
    earned = {
        (row.week_key, FreezeReason(row.reason))
        for row in db.execute(
            select(StreakFreezeEvent.week_key, StreakFreezeEvent.reason).where(
                StreakFreezeEvent.user_id == user.id, StreakFreezeEvent.delta > 0
            )
        )
    }
    events = settle(
        weeks,
        sessions_per_week=store.qualified_weeks(db, user.id),
        covered=before.covered,
        earned=earned,
        balance=before.balance,
        quests_done_weeks=_quests_done_weeks(db, user.id, weeks),
    )
    if events:
        db.execute(
            insert(StreakFreezeEvent)
            .values(
                [
                    {
                        "user_id": user.id,
                        "delta": e.delta,
                        "reason": e.reason.value,
                        "week_key": e.week,
                    }
                    for e in events
                ]
            )
            .on_conflict_do_nothing(constraint="uq_streak_freeze_once")
        )
    user.freeze_settled_through = last_closed
    return state(db, user.id)


def covered_since(db: Session, user: User, since: dt.datetime | None) -> list[str]:
    """Weeks a freeze covered that the user has not been told about yet."""
    query = select(StreakFreezeEvent.week_key).where(
        StreakFreezeEvent.user_id == user.id, StreakFreezeEvent.delta < 0
    )
    if since is not None:
        query = query.where(StreakFreezeEvent.created_at > since)
    return sorted(db.scalars(query))


def current_streak(
    db: Session, user: User, now: dt.datetime
) -> tuple[streaks.WeeklyStreak, FreezeState]:
    """The weekly streak as of `now`, with closed weeks' freezes settled
    first. Writes freeze events, so the caller holds the level_progress lock
    and commits."""
    freezes = settle_user(db, user, now)
    return (
        streaks.weekly_streak(
            store.qualified_weeks(db, user.id),
            streaks.week_key(now, user.timezone),
            covered=freezes.covered,
        ),
        freezes,
    )
