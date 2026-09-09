"""Pure-logic tests: period keys, the XP curve, and streaks.

These need no database, and they cover the boundaries that are impractical to
reach over HTTP - notably the ISO-week/New-Year overlap and multi-day streak
gaps.
"""

import datetime as dt

import pytest

from app.core import leveling
from app.core.periods import period_key
from app.core.progression import _apply_streak
from app.models.user import LevelProgress


def utc(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc)


# --------------------------------------------------------------------------
# Period keys
# --------------------------------------------------------------------------


def test_daily_key_uses_the_users_local_date() -> None:
    """One instant, two users: 22:02 UTC is still the 9th in New York but
    already the 10th in Tokyo. A daily quest must reset at the USER's
    midnight."""
    moment = utc("2026-09-09T22:02:00")
    assert period_key("daily", moment, "America/New_York") == "2026-09-09"
    assert period_key("daily", moment, "Asia/Tokyo") == "2026-09-10"


def test_weekly_key_uses_the_iso_year_not_the_calendar_year() -> None:
    """2026-12-28 and 2027-01-01 fall in the same ISO week. Using
    strftime('%Y-W%W') would give them different keys and let one week be
    completed twice."""
    assert period_key("weekly", utc("2026-12-28T12:00:00"), "UTC") == "2026-W53"
    assert period_key("weekly", utc("2027-01-01T12:00:00"), "UTC") == "2026-W53"
    # ...and the following Monday genuinely starts a new week.
    assert period_key("weekly", utc("2027-01-04T12:00:00"), "UTC") == "2027-W01"


def test_one_off_key_is_a_sentinel_not_null() -> None:
    assert period_key("none", utc("2026-09-09T12:00:00"), "UTC") == "once"


def test_unknown_timezone_falls_back_instead_of_crashing() -> None:
    """Awarding XP against UTC beats a 500 on a completion."""
    assert period_key("daily", utc("2026-09-09T12:00:00"), "Mars/Olympus") == "2026-09-09"


def test_naive_datetime_is_rejected() -> None:
    """A naive datetime would be silently treated as server-local and shift
    the period boundary."""
    with pytest.raises(ValueError):
        period_key("daily", dt.datetime(2026, 9, 9, 22, 0), "UTC")


def test_unsupported_recurrence_raises() -> None:
    with pytest.raises(ValueError):
        period_key("monthly", utc("2026-09-09T12:00:00"), "UTC")


# --------------------------------------------------------------------------
# XP curve
# --------------------------------------------------------------------------


def test_level_one_is_free() -> None:
    assert leveling.xp_for_level(1) == 0
    assert leveling.level_for_xp(0) == 1


def test_curve_round_trips() -> None:
    """The exact XP for level n must resolve back to level n - an off-by-one
    here would strand users one XP short of every level."""
    assert all(leveling.level_for_xp(leveling.xp_for_level(n)) == n for n in range(1, 201))


def test_one_xp_short_stays_on_the_lower_level() -> None:
    assert leveling.level_for_xp(leveling.xp_for_level(5) - 1) == 4


def test_negative_xp_clamps_to_level_one() -> None:
    assert leveling.level_for_xp(-100) == 1


def test_rank_thresholds_are_ascending() -> None:
    levels = [lvl for lvl, _ in leveling.RANK_THRESHOLDS]
    assert levels == sorted(levels)


def test_curve_is_fast_enough_to_stay_reachable() -> None:
    """Guards the pacing decision itself.

    The previous placeholder curve put S rank ~9.8 years out at a realistic
    income, which made the top half of the ladder dead content. This pins the
    agreed shape so a future retune cannot silently reintroduce that.
    """
    per_day = 268  # 3 dailies at 75 XP plus a weekly at 300
    top_level = leveling.RANK_THRESHOLDS[-1][0]
    years = leveling.xp_for_level(top_level) / per_day / 365
    assert years < 3, f"S rank takes {years:.1f} years at a realistic income"


@pytest.mark.parametrize(
    "level,expected", [(1, "E"), (7, "E"), (8, "D"), (18, "C"), (30, "B"), (45, "A"), (65, "S")]
)
def test_rank_by_level_ignores_the_streak_gate(level: int, expected: str) -> None:
    """What the level alone has earned - used to tell a user they qualify but
    need the streak."""
    assert leveling.rank_by_level(level).value == expected


# --------------------------------------------------------------------------
# The streak gate on A and S
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level,streak,expected",
    [
        # E-B are level-only, so the streak is irrelevant.
        (1, 0, "E"),
        (8, 0, "D"),
        (18, 0, "C"),
        (30, 0, "B"),
        # A needs 14 days, S needs 30.
        (45, 13, "B"),
        (45, 14, "A"),
        (65, 29, "A"),
        (65, 30, "S"),
    ],
)
def test_rank_applies_the_streak_gate(level: int, streak: int, expected: str) -> None:
    assert leveling.rank_for(level, streak).value == expected


def test_a_lapsed_top_rank_falls_back_not_to_the_floor() -> None:
    """Losing a streak costs the badge, never the level or the XP behind it."""
    assert leveling.rank_for(65, 30).value == "S"
    assert leveling.rank_for(65, 0).value == "B"


def test_next_rank_requirement_reports_both_gates() -> None:
    target, level_needed, streak_needed = leveling.next_rank_requirement(30, 0)
    assert (target.value, level_needed, streak_needed) == ("A", 45, 14)


def test_next_rank_requirement_is_none_at_the_top() -> None:
    assert leveling.next_rank_requirement(65, 30) is None


# --------------------------------------------------------------------------
# Effective streak - the read-time correction
# --------------------------------------------------------------------------

TODAY_ = dt.date(2026, 9, 10)


@pytest.mark.parametrize(
    "last,expected_active",
    [
        (TODAY_, True),                          # completed today
        (TODAY_ - dt.timedelta(days=1), True),   # yesterday: still within grace
        (TODAY_ - dt.timedelta(days=2), False),  # a full day missed
        (TODAY_ - dt.timedelta(days=30), False),
        (None, False),                           # never completed anything
    ],
)
def test_streak_is_active(last, expected_active: bool) -> None:
    assert leveling.streak_is_active(last, TODAY_) is expected_active


def test_effective_streak_zeroes_a_lapsed_streak() -> None:
    """Nothing runs while a user is away, so the stored counter stays frozen at
    its old value. Without this correction a dormant user would hold S rank
    forever on a streak they no longer have.
    """
    assert leveling.effective_streak(40, TODAY_ - dt.timedelta(days=10), TODAY_) == 0
    assert leveling.effective_streak(40, TODAY_, TODAY_) == 40


def test_a_dormant_user_loses_the_top_rank() -> None:
    """The end-to-end point of the gate: identical level and stored streak,
    separated only by whether the user is still showing up."""
    stored_streak, level = 40, 65
    active = leveling.effective_streak(stored_streak, TODAY_, TODAY_)
    lapsed = leveling.effective_streak(
        stored_streak, TODAY_ - dt.timedelta(days=10), TODAY_
    )
    assert leveling.rank_for(level, active).value == "S"
    assert leveling.rank_for(level, lapsed).value == "B"


def test_progress_into_level_matches_the_curve() -> None:
    into, needed = leveling.progress_into_level(120)
    level = leveling.level_for_xp(120)
    assert into == 120 - leveling.xp_for_level(level)
    assert needed == leveling.xp_for_level(level + 1) - leveling.xp_for_level(level)


# --------------------------------------------------------------------------
# Streaks
# --------------------------------------------------------------------------

TODAY = dt.date(2026, 9, 10)


def streak_after(last: dt.date | None, today: dt.date = TODAY, current: int = 5):
    progress = LevelProgress(current_streak=current, longest_streak=9, last_completed_on=last)
    _apply_streak(progress, today)
    return progress


def test_first_ever_completion_starts_the_streak() -> None:
    assert streak_after(None).current_streak == 1


def test_second_completion_the_same_day_does_not_extend() -> None:
    assert streak_after(TODAY).current_streak == 5


def test_consecutive_day_extends() -> None:
    assert streak_after(TODAY - dt.timedelta(days=1)).current_streak == 6


@pytest.mark.parametrize("gap", [2, 3, 30])
def test_a_missed_day_resets_the_streak(gap: int) -> None:
    assert streak_after(TODAY - dt.timedelta(days=gap)).current_streak == 1


def test_longest_streak_is_recorded() -> None:
    progress = streak_after(TODAY - dt.timedelta(days=1), current=9)
    assert progress.current_streak == 10
    assert progress.longest_streak == 10


def test_longest_streak_is_never_lowered() -> None:
    assert streak_after(TODAY - dt.timedelta(days=5), current=5).longest_streak == 9


def test_backdated_completion_does_not_corrupt_the_streak() -> None:
    """Clock skew or a backdated entry must leave the streak alone rather than
    moving the marker backwards."""
    future = TODAY + dt.timedelta(days=1)
    progress = streak_after(future)
    assert progress.current_streak == 5
    assert progress.last_completed_on == future
