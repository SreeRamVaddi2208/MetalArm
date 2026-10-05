"""Sanity checks on the tuning constants, so a careless edit is caught."""

from app.core import workout_rules as r


def test_rewards_are_non_negative() -> None:
    for value in (
        r.SET_POINTS,
        r.WARMUP_SET_POINTS,
        r.SESSION_BONUS,
        r.PR_BONUS,
        r.STREAK_BONUS_PER_WEEK,
    ):
        assert value >= 0


def test_warmups_cannot_out_earn_working_sets() -> None:
    assert r.WARMUP_SET_POINTS <= r.SET_POINTS


def test_session_multiplier_ceiling_is_one_and_a_half() -> None:
    assert 1 + r.SESSION_DURATION_WEIGHT + r.SESSION_SETS_WEIGHT == 1.5


def test_session_caps_are_consistent() -> None:
    assert r.SET_POINTS_CAP_PER_SESSION >= r.SET_POINTS
    assert r.SESSION_MIN_WORKING_SETS <= r.SESSION_SETS_FULL
    assert r.SESSION_MIN_MINUTES <= r.SESSION_DURATION_FULL_MINUTES
    assert r.STREAK_BONUS_CAP >= r.STREAK_BONUS_PER_WEEK


def test_hint_rep_range_is_ordered() -> None:
    low, high = r.HINT_REP_RANGE
    assert 0 < low < high <= r.EST_1RM_MAX_REPS


def test_small_weight_step_is_smaller() -> None:
    assert 0 < r.SMALL_WEIGHT_STEP_KG < r.WEIGHT_STEP_KG


def test_lb_to_kg() -> None:
    assert round(100 * r.LB_TO_KG, 2) == 45.36
