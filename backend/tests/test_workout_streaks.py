"""The weekly workout streak: ISO-week arithmetic and the rules for when a
week keeps, extends, or breaks a streak. Pure logic, no database."""

import datetime as dt

from app.core.workout_streaks import previous_week, week_key, weekly_streak

TARGET = 3


def test_previous_week_within_a_year() -> None:
    assert previous_week("2026-W37") == "2026-W36"


def test_previous_week_across_new_year_into_a_53_week_year() -> None:
    """2026 has 53 ISO weeks; arithmetic on the week number would skip W53."""
    assert previous_week("2027-W01") == "2026-W53"


def test_previous_week_across_new_year_into_a_52_week_year() -> None:
    assert previous_week("2026-W01") == "2025-W52"


def test_week_key_uses_the_users_timezone() -> None:
    """Sunday 20:00 UTC is already Monday morning in Tokyo - a new week."""
    moment = dt.datetime(2026, 9, 6, 20, 0, tzinfo=dt.timezone.utc)
    assert week_key(moment, "UTC") == "2026-W36"
    assert week_key(moment, "Asia/Tokyo") == "2026-W37"


def test_no_sessions_no_streak() -> None:
    state = weekly_streak({}, "2026-W37", TARGET)
    assert state.weeks == 0
    assert state.sessions_to_go == TARGET


def test_the_current_week_counts_once_it_reaches_target() -> None:
    state = weekly_streak({"2026-W37": 3}, "2026-W37", TARGET)
    assert state.weeks == 1
    assert state.this_week_done is True


def test_an_in_progress_week_does_not_break_the_streak() -> None:
    """Mid-week, short of target: last week's run is still alive."""
    counts = {"2026-W35": 3, "2026-W36": 3, "2026-W37": 1}
    state = weekly_streak(counts, "2026-W37", TARGET)
    assert state.weeks == 2
    assert state.this_week_done is False
    assert state.sessions_to_go == 2


def test_a_past_week_short_of_target_breaks_the_streak() -> None:
    counts = {"2026-W35": 3, "2026-W36": 2, "2026-W37": 3}
    assert weekly_streak(counts, "2026-W37", TARGET).weeks == 1


def test_a_week_with_no_sessions_breaks_the_streak() -> None:
    counts = {"2026-W35": 3, "2026-W37": 3}
    assert weekly_streak(counts, "2026-W37", TARGET).weeks == 1


def test_the_streak_is_gone_once_a_short_week_has_ended() -> None:
    """W37 ended with nothing. Now it is W38, and the old run is over."""
    counts = {"2026-W35": 3, "2026-W36": 3}
    assert weekly_streak(counts, "2026-W38", TARGET).weeks == 0


def test_a_streak_runs_across_new_year() -> None:
    counts = {"2026-W52": 3, "2026-W53": 4, "2027-W01": 3}
    assert weekly_streak(counts, "2027-W01", TARGET).weeks == 3


def test_the_target_is_tunable() -> None:
    assert weekly_streak({"2026-W37": 1}, "2026-W37", target=1).weeks == 1
