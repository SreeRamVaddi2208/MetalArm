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


@pytest.mark.parametrize(
    "level,expected", [(1, "E"), (9, "E"), (10, "D"), (20, "C"), (35, "B"), (50, "A"), (75, "S")]
)
def test_rank_for_level(level: int, expected: str) -> None:
    assert leveling.rank_for_level(level).value == expected


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
