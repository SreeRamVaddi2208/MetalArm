"""The character sheet: three stats derived from what the user actually did.

    Strength    best estimated 1RM on the trial lifts, relative to bodyweight
    Endurance   working-set volume over the last four weeks
    Discipline  how many of the last eight weeks hit the workout target

Each stat is 0-100 with the number behind it, so a bar and its caption need no
second request. A class (Powerlifter, Bodybuilder, Athlete) only decides which
stats are highlighted: it never touches points, XP, records or a leaderboard,
so nobody can pick a class to score better. That is the whole reason classes
are stored on the user and read only here.

The ceilings below are what "100" means. They are deliberately high but
reachable, and changing one re-scores everybody at once - no stored values.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import rank_trials
from app.core import workout_rules as rules
from app.core import workout_store as store
from app.core import workout_streaks as streaks
from app.models.enums import CharacterClass
from app.models.user import User
from app.models.workout import Exercise, PersonalRecord, SetEntry, WorkoutSession
from app.models.workout_enums import RecordType, SessionStatus

# Bench 1.5x + squat 2x + deadlift 2.5x bodyweight - a strong lifter, not a
# record holder.
STRENGTH_TOTAL_FOR_MAX = Decimal(6)
# Four weeks of hard training.
ENDURANCE_VOLUME_FOR_MAX = Decimal(40_000)
DISCIPLINE_WEEKS = 8
_LB = Decimal(str(rules.LB_TO_KG))

CLASS_LABELS: dict[str, str] = {
    CharacterClass.POWERLIFTER.value: "Powerlifter",
    CharacterClass.BODYBUILDER.value: "Bodybuilder",
    CharacterClass.ATHLETE.value: "Athlete",
}
# Which stats a class highlights. Presentation only.
CLASS_HIGHLIGHTS: dict[str, tuple[str, ...]] = {
    CharacterClass.POWERLIFTER.value: ("strength",),
    CharacterClass.BODYBUILDER.value: ("strength", "endurance"),
    CharacterClass.ATHLETE.value: ("endurance", "discipline"),
}


@dataclasses.dataclass(frozen=True)
class Stat:
    key: str
    label: str
    # 0-100.
    value: int
    # The number behind the score, in the user's unit where it is a weight.
    detail: str
    highlighted: bool = False


@dataclasses.dataclass(frozen=True)
class Sheet:
    character_class: str
    class_label: str
    stats: list[Stat]


def _score(part: Decimal, whole: Decimal) -> int:
    if whole <= 0:
        return 0
    return int(min(Decimal(100), (part / whole) * 100))


def _weight(kilograms: Decimal, unit: str) -> str:
    value = (kilograms / _LB) if unit == "lb" else kilograms
    return f"{value:,.0f} {unit}"


def best_trial_1rms(db: Session, user_id) -> dict[str, Decimal]:
    """Best estimated 1RM on each trial lift, library exercises only."""
    rows = db.execute(
        select(Exercise.slug, func.max(PersonalRecord.value))
        .join(PersonalRecord, PersonalRecord.exercise_id == Exercise.id)
        .where(
            PersonalRecord.user_id == user_id,
            PersonalRecord.record_type == RecordType.EST_1RM.value,
            Exercise.slug.in_([trial.slug for trial in rank_trials.TRIALS]),
            Exercise.created_by_user_id.is_(None),
        )
        .group_by(Exercise.slug)
    ).all()
    return {slug: best for slug, best in rows}


def recent_volume_kg(db: Session, user_id, *, since: dt.datetime) -> Decimal:
    """Working-set volume in completed sessions since `since`."""
    return db.execute(
        select(func.coalesce(func.sum(SetEntry.weight_kg * SetEntry.reps), 0))
        .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
        .where(
            SetEntry.user_id == user_id,
            WorkoutSession.status == SessionStatus.COMPLETED.value,
            WorkoutSession.started_at >= since,
            SetEntry.is_warmup.is_(False),
            SetEntry.reps.is_not(None),
        )
    ).scalar_one()


def weeks_on_target(db: Session, user: User, *, now: dt.datetime) -> int:
    """How many of the last DISCIPLINE_WEEKS weeks hit the workout target."""
    weeks = store.qualified_weeks(db, user.id)
    hit = 0
    for back in range(DISCIPLINE_WEEKS):
        key = streaks.week_key(now - dt.timedelta(weeks=back), user.timezone)
        if weeks.get(key, 0) >= rules.STREAK_SESSIONS_PER_WEEK:
            hit += 1
    return hit


def sheet(db: Session, user: User, *, now: dt.datetime | None = None) -> Sheet:
    now = now or dt.datetime.now(dt.timezone.utc)
    unit = user.weight_unit

    # --- Strength ---------------------------------------------------------
    bodyweight = rank_trials.latest_bodyweight_kg(db, user.id)
    bests = best_trial_1rms(db, user.id)
    if bodyweight and bodyweight > 0 and bests:
        total = sum(bests.values(), Decimal(0)) / bodyweight
        strength = Stat(
            key="strength",
            label="Strength",
            value=_score(total, STRENGTH_TOTAL_FOR_MAX),
            detail=f"{total:.1f}x bodyweight across bench, squat and deadlift",
        )
    elif not bodyweight:
        strength = Stat("strength", "Strength", 0, "Log a bodyweight to score strength")
    else:
        strength = Stat("strength", "Strength", 0, "Log a bench, squat or deadlift")

    # --- Endurance --------------------------------------------------------
    volume = recent_volume_kg(db, user.id, since=now - dt.timedelta(weeks=4))
    endurance = Stat(
        key="endurance",
        label="Endurance",
        value=_score(Decimal(volume), ENDURANCE_VOLUME_FOR_MAX),
        detail=f"{_weight(Decimal(volume), unit)} lifted in four weeks",
    )

    # --- Discipline -------------------------------------------------------
    hit = weeks_on_target(db, user, now=now)
    discipline = Stat(
        key="discipline",
        label="Discipline",
        value=_score(Decimal(hit), Decimal(DISCIPLINE_WEEKS)),
        detail=f"{hit} of the last {DISCIPLINE_WEEKS} weeks on target",
    )

    chosen = user.character_class or ""
    highlighted = CLASS_HIGHLIGHTS.get(chosen, ())
    stats = [
        dataclasses.replace(stat, highlighted=stat.key in highlighted)
        for stat in (strength, endurance, discipline)
    ]
    return Sheet(
        character_class=chosen,
        class_label=CLASS_LABELS.get(chosen, ""),
        stats=stats,
    )
