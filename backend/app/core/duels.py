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

from app.core import duel_scoring as fair
from app.core.periods import local_date
from app.models.duel import (
    BASELINE_METRICS,
    FAIR_METRICS,
    BaselineType,
    Duel,
    DuelBaseline,
    DuelMetric,
    DuelStatus,
)
from app.models.user import User
from app.models.workout import Exercise, SetEntry, WorkoutSession
from app.models.workout_enums import SessionStatus

# What a win is worth. In the same range as a session bonus: a duel should be
# worth winning without being worth more than the training that won it.
WIN_POINTS = 40
# A fair duel that ends level pays both sides; a loser who trained is still
# paid for showing up. Below a win, so winning stays worth more.
DRAW_POINTS = 15
PARTICIPATION_POINTS = 10
# Duel rewards of any kind per user per ISO week. Past it a duel still counts,
# it just pays nothing - duels are for rivalry, not a points farm.
REWARDS_PER_WEEK = 3
# A fair-mode challenge not answered in this long expires.
ACCEPT_WITHIN = dt.timedelta(hours=48)
# Live (pending or active) fair-mode duels a person can be in at once. The
# original modes are uncapped, as they always were.
MAX_LIVE = 3
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

    if metric in FAIR_METRICS:
        raise ValueError(f"{metric} is scored per duel - use fair_score")
    if metric == DuelMetric.SESSIONS.value:
        return float(db.scalar(select(func.count()).select_from(sessions.subquery())) or 0)

    # Working sets only: a warm-up is not a contribution, and a flagged set
    # (app/core/plausibility.py) does not count against somebody else.
    working = (
        select(SetEntry)
        .where(SetEntry.session_id.in_(sessions))
        .where(SetEntry.is_warmup.is_(False))
        .where(SetEntry.is_flagged.is_(False))
    )
    if metric == DuelMetric.SETS.value:
        return float(db.scalar(select(func.count()).select_from(working.subquery())) or 0)

    volume = db.scalar(
        select(func.coalesce(func.sum(SetEntry.weight_kg * func.coalesce(SetEntry.reps, 0)), 0))
        .where(SetEntry.session_id.in_(sessions))
        .where(SetEntry.is_warmup.is_(False))
        .where(SetEntry.is_flagged.is_(False))
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
    # The fair modes' working: per day, per exercise, or volume vs usual.
    # Aggregates only - never the other side's raw sets.
    challenger_detail: fair.Score | None = None
    opponent_detail: fair.Score | None = None


def standing(db: Session, duel: Duel, now: dt.datetime) -> Standing:
    end = min(now, duel.window_end)
    if duel.metric in FAIR_METRICS:
        a = fair_score(db, duel, duel.challenger_id, end)
        b = fair_score(db, duel, duel.opponent_id, end)  # type: ignore[arg-type]
        verdict = fair.winner(a, b)
        leader = duel.challenger_id if verdict > 0 else duel.opponent_id if verdict < 0 else None
        return Standing(a.value, b.value, leader, a, b)

    mine = score(db, duel.challenger_id, duel.metric, duel.window_start, end)
    if duel.is_ai_opponent:
        theirs = float(duel.rival_target or 0) if now >= duel.window_end else rival_progress(duel, now)
    else:
        theirs = score(db, duel.opponent_id, duel.metric, duel.window_start, end)  # type: ignore[arg-type]
    if mine > theirs:
        leader = duel.challenger_id
    elif theirs > mine:
        leader = duel.opponent_id  # None when the rival leads, which is correct
    else:
        leader = None
    return Standing(challenger=round(mine, 2), opponent=round(theirs, 2), leader_id=leader)


def is_over(duel: Duel, now: dt.datetime) -> bool:
    return duel.status == DuelStatus.ACTIVE.value and now >= duel.window_end


def is_stale(duel: Duel, now: dt.datetime) -> bool:
    """A fair-mode challenge left unanswered past ACCEPT_WITHIN. The original
    modes keep their open-ended challenges, as they always had."""
    return (
        duel.metric in FAIR_METRICS
        and duel.status == DuelStatus.PENDING.value
        and now >= duel.created_at + ACCEPT_WITHIN
    )


def decide(db: Session, duel: Duel, now: dt.datetime) -> uuid.UUID | None:
    """The winner of a closed duel, or None for a draw / a rival win.

    Caller persists; this only judges, so it can be tested without a write.
    """
    final = standing(db, duel, duel.window_end)
    return final.leader_id


def as_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def reward_key(duel: Duel, user_id: uuid.UUID) -> uuid.UUID:
    """The ledger source_id for one side's draw or participation reward. Both
    sides of a draw are paid, so the duel id alone would collide on the
    once-only index; this is stable per (duel, person) instead."""
    return uuid.uuid5(duel.id, str(user_id))


# ---------------------------------------------------------------------------
# The fair modes: facts, baselines, eligibility
# ---------------------------------------------------------------------------


def window_facts(
    db: Session, user_id: uuid.UUID, start: dt.datetime, end: dt.datetime
) -> tuple[list[fair.WindowSession], list[fair.WindowSet]]:
    """Completed sessions finished in the window, and their working sets -
    warm-ups and flagged sets left out."""
    user = db.get(User, user_id)
    tz = user.timezone if user else "UTC"
    sessions = [
        fair.WindowSession(row.id, local_date(row.ended_at, tz), bool(row.qualified))
        for row in db.execute(
            select(WorkoutSession.id, WorkoutSession.ended_at, WorkoutSession.qualified).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == SessionStatus.COMPLETED.value,
                WorkoutSession.import_id.is_(None),
                WorkoutSession.ended_at >= start,
                WorkoutSession.ended_at < end,
            )
        )
    ]
    if not sessions:
        return [], []
    sets = [
        fair.WindowSet(row.session_id, row.exercise_id, row.weight_kg, row.reps)
        for row in db.execute(
            select(SetEntry.session_id, SetEntry.exercise_id, SetEntry.weight_kg, SetEntry.reps).where(
                SetEntry.session_id.in_([s.id for s in sessions]),
                SetEntry.is_warmup.is_(False),
                SetEntry.is_flagged.is_(False),
            )
        )
    ]
    return sessions, sets


def _baselines(db: Session, duel: Duel, user_id: uuid.UUID) -> list[DuelBaseline]:
    return list(
        db.scalars(
            select(DuelBaseline).where(DuelBaseline.duel_id == duel.id, DuelBaseline.user_id == user_id)
        )
    )


def fair_score(db: Session, duel: Duel, user_id: uuid.UUID, end: dt.datetime) -> fair.Score:
    sessions, sets = window_facts(db, user_id, duel.window_start, end)
    if duel.metric == DuelMetric.CONSISTENCY.value:
        return fair.consistency(sessions, sets)
    rows = _baselines(db, duel, user_id)
    if duel.metric == DuelMetric.PROGRESS.value:
        baselines = {
            r.exercise_id: Decimal(r.baseline_value) for r in rows if r.exercise_id is not None
        }
        names = dict(
            db.execute(select(Exercise.id, Exercise.name).where(Exercise.id.in_(list(baselines))))
            .tuples()
            .all()
        ) if baselines else {}
        return fair.progress(baselines, sets, names)
    avg = next((Decimal(r.baseline_value) for r in rows if r.exercise_id is None), Decimal(0))
    days = (duel.window_end - duel.window_start).total_seconds() / 86400
    return fair.relative_volume(avg, sets, days)


def _history(db: Session, user_id: uuid.UUID, now: dt.datetime) -> list[fair.WindowSet]:
    _, sets = window_facts(db, user_id, now - dt.timedelta(days=fair.BASELINE_DAYS), now)
    return sets


def baseline_values(
    db: Session, user_id: uuid.UUID, metric: str, now: dt.datetime
) -> tuple[dict[uuid.UUID, Decimal], Decimal]:
    """(best e1RM per exercise, average weekly volume) over the 28 days
    before `now`. Flagged sets do not set a baseline either - an inflated
    baseline is as unfair as an inflated score."""
    sets = _history(db, user_id, now)
    if metric == DuelMetric.PROGRESS.value:
        return fair.best_e1rm(sets), Decimal(0)
    volume = sum((s.weight_kg * s.reps for s in sets if s.reps), Decimal(0))
    return {}, fair.baseline_avg_weekly(volume)


def ineligible(db: Session, user: User, metric: str, now: dt.datetime) -> str | None:
    """Why `user` cannot take part in a duel on `metric`, or None if they can."""
    if metric not in BASELINE_METRICS:
        return None
    e1rms, weekly = baseline_values(db, user.id, metric, now)
    if metric == DuelMetric.PROGRESS.value and not e1rms:
        return f"{user.display_name} has no lifts in the last 4 weeks to measure progress from"
    if metric == DuelMetric.RELATIVE_VOLUME.value and weekly <= 0:
        return f"{user.display_name} has no workouts in the last 4 weeks to compare against"
    return None


def snapshot_baselines(db: Session, duel: Duel, now: dt.datetime) -> None:
    """Fix both sides' baselines as the window opens. Idempotent."""
    if duel.metric not in BASELINE_METRICS:
        return
    for user_id in (duel.challenger_id, duel.opponent_id):
        if user_id is None or _baselines(db, duel, user_id):
            continue
        e1rms, weekly = baseline_values(db, user_id, duel.metric, now)
        if duel.metric == DuelMetric.PROGRESS.value:
            db.add_all(
                DuelBaseline(
                    duel_id=duel.id,
                    user_id=user_id,
                    exercise_id=exercise_id,
                    baseline_type=BaselineType.E1RM.value,
                    baseline_value=as_decimal(float(value)),
                )
                for exercise_id, value in e1rms.items()
                if value > 0
            )
        elif weekly > 0:
            db.add(
                DuelBaseline(
                    duel_id=duel.id,
                    user_id=user_id,
                    exercise_id=None,
                    baseline_type=BaselineType.AVG_WEEKLY_VOLUME.value,
                    baseline_value=as_decimal(float(weekly)),
                )
            )
    db.flush()


def trained_in_window(db: Session, duel: Duel, user_id: uuid.UUID) -> bool:
    """At least one qualifying session in the window - what earns a losing
    side its participation reward."""
    sessions, sets = window_facts(db, user_id, duel.window_start, duel.window_end)
    return fair.consistency(sessions, sets).value >= 1
