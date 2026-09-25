"""Head-to-head duels: scoring, the synthetic rival, and lazy judging.

Scores are never stored. Whoever asks, the two totals are summed from the sets
and sessions that fall inside the window - the same rule leagues and raids
follow, and for the same reason: a stored score can disagree with the sets
behind it, a summed one cannot. Deleting a set therefore takes its volume back
out of a running duel, which is the honest answer.

**The rival is a pace, not a person.** When someone has nobody to challenge
yet, the opponent is synthetic: a target generated at creation from the
challenger's OWN last few windows of the same length, never from anybody
else's data. It is stored (`duels.rival_target`) so the bar does not move
between reads, and the duel is flagged `is_ai_opponent` so no screen can
mistake it for a real lifter.

**Judging is lazy.** MetalArm has no cron (see app/core/leagues.py): a duel
whose window has closed is judged the first time anyone looks at it, and that
is when the winner's points and the feed entry are written. A duel nobody ever
opens is simply never judged, which costs nothing.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.duel import Duel, DuelMetric, DuelStatus
from app.models.workout import SetEntry, WorkoutSession
from app.models.workout_enums import SessionStatus

# What a win is worth. In the same range as a session bonus: a duel should be
# worth winning without being worth more than the training that won it.
WIN_POINTS = 40
# How many past windows the rival's pace is drawn from.
RIVAL_LOOKBACK = 4
# The rival aims a little above what the challenger has been managing, so the
# duel is a stretch rather than a formality. 1.0 would be "beat your average".
RIVAL_STRETCH = 1.08
# What the rival asks of someone with no history at all - a modest first week
# rather than zero, which would make the duel unlosable.
RIVAL_FLOOR = {DuelMetric.VOLUME: 2000.0, DuelMetric.SETS: 12.0, DuelMetric.SESSIONS: 2.0}


def _sessions_in(user_id: uuid.UUID, start: dt.datetime, end: dt.datetime) -> Select:
    """Completed sessions whose END falls in the window.

    Ended, not started: a workout belongs to the window it was finished in, so
    a session cannot count for a duel that closed while it was still running.
    """
    return (
        select(WorkoutSession.id)
        .where(WorkoutSession.user_id == user_id)
        .where(WorkoutSession.status == SessionStatus.COMPLETED.value)
        .where(WorkoutSession.ended_at >= start)
        .where(WorkoutSession.ended_at < end)
    )


def score(db: Session, user_id: uuid.UUID, metric: str, start: dt.datetime, end: dt.datetime) -> float:
    """What this user has put up on this metric inside the window."""
    sessions = _sessions_in(user_id, start, end)

    if metric == DuelMetric.SESSIONS.value:
        return float(db.scalar(select(func.count()).select_from(sessions.subquery())) or 0)

    # Working sets only: a warm-up is not a contribution.
    working = (
        select(SetEntry)
        .where(SetEntry.session_id.in_(sessions))
        .where(SetEntry.is_warmup.is_(False))
    )
    if metric == DuelMetric.SETS.value:
        return float(db.scalar(select(func.count()).select_from(working.subquery())) or 0)

    volume = db.scalar(
        select(func.coalesce(func.sum(SetEntry.weight_kg * func.coalesce(SetEntry.reps, 0)), 0))
        .where(SetEntry.session_id.in_(sessions))
        .where(SetEntry.is_warmup.is_(False))
    )
    return float(volume or 0)


def rival_target(db: Session, user_id: uuid.UUID, metric: str, length: dt.timedelta,
                 now: dt.datetime) -> float:
    """A pace for the synthetic opponent, from this user's own recent form.

    The best of their last few equal-length windows, stretched slightly. Best
    rather than average, because a rival that is beaten by an average week is
    not much of a rival - and because one washed-out week should not hand
    somebody a free win.
    """
    best = 0.0
    for back in range(1, RIVAL_LOOKBACK + 1):
        end = now - length * (back - 1)
        best = max(best, score(db, user_id, metric, end - length, end))
    if best <= 0:
        return RIVAL_FLOOR[DuelMetric(metric)]
    return round(best * RIVAL_STRETCH, 2)


def rival_progress(duel: Duel, now: dt.datetime) -> float:
    """Where the rival is 'up to' right now: its target, paced evenly.

    Honest by construction - it is a straight line to a number fixed when the
    duel was made, not a simulation pretending to train.
    """
    target = float(duel.rival_target or 0)
    total = (duel.window_end - duel.window_start).total_seconds()
    if total <= 0:
        return target
    done = (now - duel.window_start).total_seconds()
    return round(target * min(1.0, max(0.0, done / total)), 2)


@dataclasses.dataclass(frozen=True)
class Standing:
    """Who is ahead, as it stands."""

    challenger: float
    opponent: float
    leader_id: uuid.UUID | None  # None is a draw, or a rival in front


def standing(db: Session, duel: Duel, now: dt.datetime) -> Standing:
    mine = score(db, duel.challenger_id, duel.metric, duel.window_start,
                 min(now, duel.window_end))
    if duel.is_ai_opponent:
        theirs = float(duel.rival_target or 0) if now >= duel.window_end else rival_progress(duel, now)
    else:
        theirs = score(db, duel.opponent_id, duel.metric, duel.window_start,
                       min(now, duel.window_end))
    if mine > theirs:
        leader = duel.challenger_id
    elif theirs > mine:
        leader = duel.opponent_id  # None when the rival leads, which is correct
    else:
        leader = None
    return Standing(challenger=round(mine, 2), opponent=round(theirs, 2), leader_id=leader)


def is_over(duel: Duel, now: dt.datetime) -> bool:
    return duel.status == DuelStatus.ACTIVE.value and now >= duel.window_end


def decide(db: Session, duel: Duel, now: dt.datetime) -> uuid.UUID | None:
    """The winner of a closed duel, or None for a draw / a rival win.

    Caller persists; this only judges, so it can be tested without a write.
    """
    final = standing(db, duel, duel.window_end)
    if final.challenger > final.opponent:
        return duel.challenger_id
    if final.opponent > final.challenger:
        return duel.opponent_id
    return None


def as_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))
