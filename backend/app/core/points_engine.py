"""Points engine for the gym workout module.

Pure functions from facts about a workout to the awards it earns. Nothing here
touches the database, the clock, or a request: the route layer assembles the
context (how many set points this session already has, which records a set
broke, how the week stands) and persists whatever this returns as points-ledger
rows. That split is what lets every rule be unit-tested at its exact edge.

Points are only ever computed here, from raw workout data. No request schema
accepts a point value, so a client cannot claim an award.

All numbers come from workout_rules.py.
"""

import dataclasses
import math
from decimal import Decimal

from app.core import workout_rules as rules
from app.core.personal_records import PrEvent
from app.models.workout_enums import LedgerSource, RecordType

# Record types whose improvement earns the PR bonus, strongest signal first -
# when one set beats several, the first listed is the one reported as paid.
#
# max_reps_at_weight and max_volume are recorded and celebrated but do not pay
# out on weighted exercises: a few more reps at a light weight, or one extra set
# for more volume, would be a PR every session for no real gain. A bodyweight
# rep PR (weight 0) is the exception - there it is the only record there is.
_BONUS_PRIORITY: tuple[RecordType, ...] = (
    RecordType.MAX_WEIGHT,
    RecordType.EST_1RM,
    RecordType.MAX_REPS_AT_WEIGHT,
)

# The smallest improvement, as a fraction of the old record, that earns the
# bonus. The record itself is still set for any improvement; this only stops
# 100 kg -> 100.25 kg -> 100.5 kg micro-steps each paying 50 points.
PR_BONUS_MIN_IMPROVEMENT = Decimal("0.01")


@dataclasses.dataclass(frozen=True)
class Award:
    source_type: LedgerSource
    points: int
    reason: str


def bonus_eligible(event: PrEvent) -> bool:
    """Whether a record-setting event is worth the PR bonus."""
    if event.is_baseline or event.previous is None or event.previous <= 0:
        return False
    if event.record_type is RecordType.MAX_REPS_AT_WEIGHT:
        if event.weight_kg is None or event.weight_kg != 0:
            return False
    elif event.record_type not in _BONUS_PRIORITY:
        return False
    improvement = (event.value - event.previous) / event.previous
    return improvement >= PR_BONUS_MIN_IMPROVEMENT


def pick_bonus_record(events: tuple[PrEvent, ...] | list[PrEvent]) -> PrEvent | None:
    """Of the records one set broke, the one a PR bonus is paid for.

    Exposed so a summary built later from stored rows marks the same record the
    award was actually made for.
    """
    eligible = [e for e in events if bonus_eligible(e)]
    if not eligible:
        return None
    return min(eligible, key=lambda e: _BONUS_PRIORITY.index(e.record_type))


# ---------------------------------------------------------------------------
# Logging a set
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SetContext:
    is_warmup: bool
    # Net set points this session already holds (reversals subtracted), so a
    # deleted set gives its room under the cap back.
    session_set_points: int
    # Net PR bonuses already paid this session.
    session_pr_bonuses: int
    # Whether this exercise already earned a PR bonus this session.
    exercise_has_pr_bonus: bool
    pr_events: tuple[PrEvent, ...] = ()


@dataclasses.dataclass(frozen=True)
class SetOutcome:
    awards: tuple[Award, ...]
    set_cap_reached: bool
    # The record the PR bonus was paid for, if one was.
    bonus_record: PrEvent | None

    @property
    def total(self) -> int:
        return sum(a.points for a in self.awards)


def award_for_set(ctx: SetContext) -> SetOutcome:
    awards: list[Award] = []

    if ctx.is_warmup:
        set_points = rules.WARMUP_SET_POINTS
    else:
        room = max(0, rules.SET_POINTS_CAP_PER_SESSION - ctx.session_set_points)
        set_points = min(rules.SET_POINTS, room)
    if set_points > 0:
        awards.append(Award(LedgerSource.SET_LOGGED, set_points, "Set logged"))

    cap_reached = (
        ctx.session_set_points + set_points >= rules.SET_POINTS_CAP_PER_SESSION
    )

    bonus_record: PrEvent | None = None
    if (
        not ctx.exercise_has_pr_bonus
        and ctx.session_pr_bonuses < rules.PR_BONUSES_PER_SESSION
    ):
        bonus_record = pick_bonus_record(ctx.pr_events)
        if bonus_record is not None:
            awards.append(
                Award(
                    LedgerSource.PR_ACHIEVED,
                    rules.PR_BONUS,
                    f"New PR: {bonus_record.record_type.value}",
                )
            )

    return SetOutcome(
        awards=tuple(awards), set_cap_reached=cap_reached, bonus_record=bonus_record
    )


# ---------------------------------------------------------------------------
# Finishing a session
# ---------------------------------------------------------------------------


def session_qualifies(duration_minutes: float, working_sets: int) -> bool:
    """Whether a finished session counts as a real workout.

    A non-qualifying session still completes and keeps its set points, but
    earns no session bonus and does not count toward the weekly streak - so
    three start/finish taps cannot keep a streak alive.
    """
    return (
        working_sets >= rules.SESSION_MIN_WORKING_SETS
        and duration_minutes >= rules.SESSION_MIN_MINUTES
    )


def session_bonus(duration_minutes: float, working_sets: int) -> int:
    if not session_qualifies(duration_minutes, working_sets):
        return 0
    minutes = min(duration_minutes, rules.MAX_SESSION_HOURS * 60)
    multiplier = (
        1
        + rules.SESSION_DURATION_WEIGHT
        * min(minutes / rules.SESSION_DURATION_FULL_MINUTES, 1)
        + rules.SESSION_SETS_WEIGHT * min(working_sets / rules.SESSION_SETS_FULL, 1)
    )
    # Round half UP explicitly: Python's round() is banker's rounding, which
    # would pay 37.5 as 38 but 36.5 as 36.
    return math.floor(rules.SESSION_BONUS * multiplier + 0.5)


def streak_bonus(streak_weeks: int) -> int:
    if streak_weeks <= 0:
        return 0
    return min(rules.STREAK_BONUS_PER_WEEK * streak_weeks, rules.STREAK_BONUS_CAP)


@dataclasses.dataclass(frozen=True)
class CompletionContext:
    duration_minutes: float
    working_sets: int
    # Qualifying completed sessions in the current week, INCLUDING this one if
    # it qualifies.
    week_sessions: int
    # The weekly streak length once this session is counted.
    streak_weeks: int
    streak_bonus_paid_this_week: bool


def award_for_completion(ctx: CompletionContext) -> tuple[Award, ...]:
    awards: list[Award] = []

    bonus = session_bonus(ctx.duration_minutes, ctx.working_sets)
    if bonus > 0:
        awards.append(
            Award(LedgerSource.SESSION_COMPLETED, bonus, "Workout completed")
        )

    # Paid by the session that brings the week to target - and only by a
    # qualifying one, since a non-qualifying session did not count toward it.
    if (
        bonus > 0
        and ctx.week_sessions >= rules.STREAK_SESSIONS_PER_WEEK
        and not ctx.streak_bonus_paid_this_week
    ):
        amount = streak_bonus(ctx.streak_weeks)
        if amount > 0:
            awards.append(
                Award(
                    LedgerSource.STREAK_BONUS,
                    amount,
                    f"{ctx.streak_weeks}-week streak",
                )
            )

    return tuple(awards)
