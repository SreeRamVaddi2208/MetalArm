"""Points engine: every rule at its exact edge.

Pure logic, no database. These are the numbers users notice first when they are
wrong, so each cap and threshold is tested on both sides of the line. Expected
values are written against workout_rules constants, so retuning a number does
not break the test that pins its BEHAVIOUR.
"""

from decimal import Decimal

import pytest

from app.core import points_engine as pe
from app.core import workout_rules as rules
from app.core.personal_records import PrEvent
from app.models.workout_enums import LedgerSource, RecordType

CAP = rules.SET_POINTS_CAP_PER_SESSION


def pr(
    kind: RecordType = RecordType.MAX_WEIGHT,
    value: str = "105",
    previous: str | None = "100",
    weight: str | None = "105",
    baseline: bool = False,
) -> PrEvent:
    return PrEvent(
        kind,
        Decimal(value),
        Decimal(weight) if weight is not None else None,
        Decimal(previous) if previous is not None else None,
        baseline,
    )


def set_ctx(**overrides) -> pe.SetContext:
    values = dict(
        is_warmup=False,
        session_set_points=0,
        session_pr_bonuses=0,
        exercise_has_pr_bonus=False,
        pr_events=(),
    )
    values.update(overrides)
    return pe.SetContext(**values)


def sources(outcome: pe.SetOutcome) -> list[LedgerSource]:
    return [a.source_type for a in outcome.awards]


# --------------------------------------------------------------------------
# Set points and the per-session cap
# --------------------------------------------------------------------------


def test_a_working_set_earns_set_points() -> None:
    outcome = pe.award_for_set(set_ctx())
    assert outcome.total == rules.SET_POINTS
    assert sources(outcome) == [LedgerSource.SET_LOGGED]


def test_a_warmup_set_earns_nothing() -> None:
    """Otherwise warm-ups would be an uncapped route to the set cap."""
    assert pe.award_for_set(set_ctx(is_warmup=True)).awards == ()


def test_no_set_points_once_the_cap_is_reached() -> None:
    outcome = pe.award_for_set(set_ctx(session_set_points=CAP))
    assert outcome.total == 0
    assert outcome.awards == ()
    assert outcome.set_cap_reached is True


def test_the_set_that_crosses_the_cap_earns_only_the_remainder() -> None:
    outcome = pe.award_for_set(set_ctx(session_set_points=CAP - 1))
    assert outcome.total == min(rules.SET_POINTS, 1)
    assert outcome.set_cap_reached is True


def test_cap_is_not_reported_before_it_is_reached() -> None:
    assert pe.award_for_set(set_ctx()).set_cap_reached is False


def test_a_long_session_earns_exactly_the_cap() -> None:
    earned = 0
    for _ in range(CAP * 2):
        earned += pe.award_for_set(set_ctx(session_set_points=earned)).total
    assert earned == CAP


# --------------------------------------------------------------------------
# PR bonus
# --------------------------------------------------------------------------


def test_a_real_pr_earns_the_bonus() -> None:
    outcome = pe.award_for_set(set_ctx(pr_events=(pr(),)))
    assert outcome.total == rules.SET_POINTS + rules.PR_BONUS
    assert sources(outcome) == [LedgerSource.SET_LOGGED, LedgerSource.PR_ACHIEVED]
    assert outcome.bonus_record is not None
    assert outcome.bonus_record.record_type is RecordType.MAX_WEIGHT


def test_a_baseline_earns_no_bonus() -> None:
    """Otherwise creating custom exercises would farm PR bonuses."""
    event = pr(previous=None, baseline=True)
    outcome = pe.award_for_set(set_ctx(pr_events=(event,)))
    assert outcome.total == rules.SET_POINTS
    assert outcome.bonus_record is None


def test_one_set_beating_several_records_earns_one_bonus() -> None:
    events = (
        pr(RecordType.MAX_REPS_AT_WEIGHT, value="0", previous=None, weight="0"),
        pr(RecordType.EST_1RM, value="120", previous="110"),
        pr(RecordType.MAX_WEIGHT),
    )
    outcome = pe.award_for_set(set_ctx(pr_events=events))
    assert sources(outcome).count(LedgerSource.PR_ACHIEVED) == 1
    # Heaviest weight is the strongest signal, so it is the one reported.
    assert outcome.bonus_record is not None
    assert outcome.bonus_record.record_type is RecordType.MAX_WEIGHT


def test_an_est_1rm_pr_alone_is_paid() -> None:
    outcome = pe.award_for_set(
        set_ctx(pr_events=(pr(RecordType.EST_1RM, value="120", previous="110"),))
    )
    assert LedgerSource.PR_ACHIEVED in sources(outcome)


def test_an_exercise_earns_at_most_one_bonus_per_session() -> None:
    outcome = pe.award_for_set(set_ctx(exercise_has_pr_bonus=True, pr_events=(pr(),)))
    assert LedgerSource.PR_ACHIEVED not in sources(outcome)


def test_the_per_session_pr_limit_is_enforced_at_its_edge() -> None:
    below = pe.award_for_set(
        set_ctx(session_pr_bonuses=rules.PR_BONUSES_PER_SESSION - 1, pr_events=(pr(),))
    )
    at = pe.award_for_set(
        set_ctx(session_pr_bonuses=rules.PR_BONUSES_PER_SESSION, pr_events=(pr(),))
    )
    assert LedgerSource.PR_ACHIEVED in sources(below)
    assert LedgerSource.PR_ACHIEVED not in sources(at)


def test_a_pr_bonus_is_paid_even_after_the_set_cap() -> None:
    """The caps are independent: a PR late in a long session still counts."""
    outcome = pe.award_for_set(set_ctx(session_set_points=CAP, pr_events=(pr(),)))
    assert outcome.total == rules.PR_BONUS


def test_a_weighted_rep_pr_is_not_paid() -> None:
    """A few more reps at a light weight would be a PR every session."""
    event = pr(RecordType.MAX_REPS_AT_WEIGHT, value="8", previous="6", weight="60")
    assert pe.bonus_eligible(event) is False


def test_a_bodyweight_rep_pr_is_paid() -> None:
    """At bodyweight, reps are the only record there is."""
    event = pr(RecordType.MAX_REPS_AT_WEIGHT, value="11", previous="10", weight="0")
    assert pe.bonus_eligible(event) is True


def test_a_volume_record_is_never_paid() -> None:
    """One extra set raises volume - that is not a PR worth 50 points."""
    event = pr(RecordType.MAX_VOLUME, value="5000", previous="4000", weight=None)
    assert pe.bonus_eligible(event) is False


def test_a_micro_improvement_is_recorded_but_not_paid() -> None:
    assert pe.bonus_eligible(pr(value="100.5", previous="100")) is False


def test_the_minimum_improvement_is_inclusive() -> None:
    assert pe.bonus_eligible(pr(value="101", previous="100")) is True


def test_a_record_with_nothing_comparable_before_is_not_paid() -> None:
    event = pr(RecordType.MAX_REPS_AT_WEIGHT, value="12", previous=None, weight="0")
    assert pe.bonus_eligible(event) is False


# --------------------------------------------------------------------------
# Session bonus
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("minutes", "sets", "expected"),
    [
        (rules.SESSION_MIN_MINUTES - 0.1, 20, 0),  # too short
        (60, rules.SESSION_MIN_WORKING_SETS - 1, 0),  # too few sets
        # At the minimums: 25 * (1 + .25 * 10/60 + .25 * 3/20) = 26.98
        (rules.SESSION_MIN_MINUTES, rules.SESSION_MIN_WORKING_SETS, 27),
        (30, 10, 31),  # 25 * 1.25 = 31.25
        (60, 20, 38),  # the x1.5 ceiling: 37.5 rounds half UP
        (600, 200, 38),  # still the ceiling
    ],
)
def test_session_bonus(minutes: float, sets: int, expected: int) -> None:
    assert pe.session_bonus(minutes, sets) == expected


def test_a_forgotten_session_cannot_bank_extra_duration() -> None:
    capped = rules.MAX_SESSION_HOURS * 60
    assert pe.session_bonus(capped * 10, 5) == pe.session_bonus(capped, 5)


@pytest.mark.parametrize(
    ("weeks", "expected"),
    [
        (0, 0),
        (1, rules.STREAK_BONUS_PER_WEEK),
        (3, 3 * rules.STREAK_BONUS_PER_WEEK),
        (1000, rules.STREAK_BONUS_CAP),
    ],
)
def test_streak_bonus_escalates_and_caps(weeks: int, expected: int) -> None:
    assert pe.streak_bonus(weeks) == expected


# --------------------------------------------------------------------------
# Completion
# --------------------------------------------------------------------------


def completion_ctx(**overrides) -> pe.CompletionContext:
    values = dict(
        duration_minutes=60,
        working_sets=20,
        week_sessions=1,
        streak_weeks=0,
        streak_bonus_paid_this_week=False,
    )
    values.update(overrides)
    return pe.CompletionContext(**values)


def test_completion_short_of_the_weekly_target_pays_only_the_session_bonus() -> None:
    awards = pe.award_for_completion(completion_ctx())
    assert [a.source_type for a in awards] == [LedgerSource.SESSION_COMPLETED]


def test_the_session_that_hits_the_weekly_target_pays_the_streak_bonus() -> None:
    awards = pe.award_for_completion(
        completion_ctx(week_sessions=rules.STREAK_SESSIONS_PER_WEEK, streak_weeks=3)
    )
    streak = [a for a in awards if a.source_type is LedgerSource.STREAK_BONUS]
    assert len(streak) == 1
    assert streak[0].points == pe.streak_bonus(3)


def test_the_streak_bonus_is_paid_once_per_week() -> None:
    awards = pe.award_for_completion(
        completion_ctx(
            week_sessions=rules.STREAK_SESSIONS_PER_WEEK + 1,
            streak_weeks=3,
            streak_bonus_paid_this_week=True,
        )
    )
    assert LedgerSource.STREAK_BONUS not in [a.source_type for a in awards]


def test_a_non_qualifying_session_pays_nothing_even_at_the_target() -> None:
    """Three start/finish taps must not keep a streak alive."""
    awards = pe.award_for_completion(
        completion_ctx(
            duration_minutes=2,
            working_sets=1,
            week_sessions=rules.STREAK_SESSIONS_PER_WEEK,
            streak_weeks=4,
        )
    )
    assert awards == ()
