"""Rank trials: strength standards that gate the top ranks.

Level and streak alone gate E to C. B, A and S also need a trial - a heaviest
set on a main lift at a multiple of the user's bodyweight:

    B  Barbell Bench Press  1.0 x bodyweight
    A  Back Squat           1.5 x bodyweight
    S  Deadlift             2.0 x bodyweight

so a rank means real strength, not only time spent. Trials are cumulative:
holding A needs the B and A trials, holding S all three (leveling.rank_for).
Only library lifts count - matched by slug, and never a user's own exercise -
and bodyweight is the latest logged `weight` body measurement; with none
logged, no trial can pass yet.

Passed trials are stored on LevelProgress.trials_passed (e.g. "BA") and
re-judged whenever an input changes: a set logged, edited or deleted, a
workout finished or discarded, a bodyweight logged or deleted. Rank
derivation reads that column, so every surface showing a rank agrees
without extra queries.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import leveling
from app.core.periods import local_date
from app.models.enums import Rank
from app.models.user import LevelProgress, User
from app.models.workout import BodyMeasurement, Exercise, PersonalRecord
from app.models.workout_enums import MeasurementMetric, RecordType

LB_TO_KG = Decimal("0.45359237")


@dataclasses.dataclass(frozen=True)
class Trial:
    rank: Rank
    slug: str
    lift: str
    multiplier: Decimal

    @property
    def description(self) -> str:
        return f"{self.lift} at {self.multiplier.normalize():f}x bodyweight"


TRIALS = (
    Trial(Rank.B, "barbell-bench-press", "Barbell Bench Press", Decimal("1.0")),
    Trial(Rank.A, "back-squat", "Back Squat", Decimal("1.5")),
    Trial(Rank.S, "deadlift", "Deadlift", Decimal("2.0")),
)
TRIAL_FOR = {trial.rank: trial for trial in TRIALS}


@dataclasses.dataclass(frozen=True)
class TrialStatus:
    rank: str
    lift: str
    description: str
    multiplier: Decimal
    # None until a bodyweight is logged.
    target_kg: Decimal | None
    best_kg: Decimal | None
    passed: bool


def latest_bodyweight_kg(db: Session, user_id: uuid.UUID) -> Decimal | None:
    row = db.execute(
        select(BodyMeasurement.value, BodyMeasurement.unit)
        .where(
            BodyMeasurement.user_id == user_id,
            BodyMeasurement.metric == MeasurementMetric.WEIGHT.value,
        )
        .order_by(BodyMeasurement.recorded_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    value, unit = row
    return (value * LB_TO_KG).quantize(Decimal("0.01")) if unit == "lb" else value


def best_lifts_kg(db: Session, user_id: uuid.UUID) -> dict[str, Decimal]:
    """Heaviest set ever on each trial lift, library exercises only."""
    db.flush()
    rows = db.execute(
        select(Exercise.slug, func.max(PersonalRecord.value))
        .join(PersonalRecord, PersonalRecord.exercise_id == Exercise.id)
        .where(
            PersonalRecord.user_id == user_id,
            PersonalRecord.record_type == RecordType.MAX_WEIGHT.value,
            Exercise.slug.in_([trial.slug for trial in TRIALS]),
            Exercise.created_by_user_id.is_(None),
        )
        .group_by(Exercise.slug)
    ).all()
    return {slug: best for slug, best in rows}


def statuses(db: Session, user_id: uuid.UUID) -> list[TrialStatus]:
    bodyweight = latest_bodyweight_kg(db, user_id)
    bests = best_lifts_kg(db, user_id)
    out = []
    for trial in TRIALS:
        target = (bodyweight * trial.multiplier).quantize(Decimal("0.01")) if bodyweight else None
        best = bests.get(trial.slug)
        out.append(
            TrialStatus(
                rank=trial.rank.value,
                lift=trial.lift,
                description=trial.description,
                multiplier=trial.multiplier,
                target_kg=target,
                best_kg=best,
                passed=target is not None and best is not None and best >= target,
            )
        )
    return out


def passed_letters(db: Session, user_id: uuid.UUID) -> str:
    return "".join(status.rank for status in statuses(db, user_id) if status.passed)


def next_trial(level: int, streak: int, trials: str) -> Trial | None:
    """The trial standing between the user and the next rank up, if any."""
    requirement = leveling.next_rank_requirement(level, streak, trials)
    if requirement is None:
        return None
    target = requirement[0]
    for rank in leveling.trials_needed(target):
        if rank.value not in trials:
            return TRIAL_FOR[rank]
    return None


def refresh(
    db: Session,
    progress: LevelProgress,
    user: User,
    delta=None,
    now: dt.datetime | None = None,
):
    """Re-judge the trials after an input changed; store them and re-derive the
    stored rank. With a ProgressionDelta from this request, the rank a trial
    just unlocked (or cost) is reported as its rank_after - rank_before stays
    what it was, so the client celebrates a trial the moment it is passed."""
    letters = passed_letters(db, user.id)
    if letters == progress.trials_passed:
        return delta
    progress.trials_passed = letters
    today = local_date(now or dt.datetime.now(dt.timezone.utc), user.timezone)
    streak = leveling.effective_streak(progress.current_streak, progress.last_completed_on, today)
    progress.rank = leveling.rank_for(progress.current_level, streak, letters)
    if delta is None:
        return None
    return dataclasses.replace(delta, rank_after=progress.rank.value)
