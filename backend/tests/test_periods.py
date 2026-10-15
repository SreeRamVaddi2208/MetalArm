"""period_key backs the UNIQUE(quest_id, user_id, period_key) anti-farming
constraint, so its boundaries matter."""

import datetime as dt

import pytest

from app.core import periods
from app.models.enums import ONE_OFF_PERIOD_KEY, Recurrence

UTC = dt.timezone.utc


def test_daily_key_is_the_users_local_date() -> None:
    # 23:30 UTC on the 9th is already the 10th in Auckland (UTC+12/13).
    moment = dt.datetime(2026, 9, 9, 23, 30, tzinfo=UTC)
    assert periods.period_key(Recurrence.DAILY.value, moment, "UTC") == "2026-09-09"
    assert (
        periods.period_key(Recurrence.DAILY.value, moment, "Pacific/Auckland")
        == "2026-09-10"
    )


def test_weekly_key_uses_iso_weeks_starting_monday() -> None:
    sunday = dt.datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
    monday = dt.datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    assert periods.period_key(Recurrence.WEEKLY.value, sunday, "UTC") == "2026-W36"
    assert periods.period_key(Recurrence.WEEKLY.value, monday, "UTC") == "2026-W37"


def test_weekly_key_uses_the_iso_year_around_new_year() -> None:
    new_year = dt.datetime(2027, 1, 1, 12, 0, tzinfo=UTC)
    assert periods.period_key(Recurrence.WEEKLY.value, new_year, "UTC") == "2026-W53"


def test_one_off_uses_the_sentinel_not_null() -> None:
    moment = dt.datetime(2026, 9, 9, tzinfo=UTC)
    assert periods.period_key(Recurrence.NONE.value, moment, "UTC") == ONE_OFF_PERIOD_KEY


def test_unknown_recurrence_is_rejected() -> None:
    with pytest.raises(ValueError):
        periods.period_key("monthly", dt.datetime(2026, 9, 9, tzinfo=UTC), "UTC")


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError):
        periods.local_date(dt.datetime(2026, 9, 9), "UTC")


def test_unknown_timezone_falls_back_to_utc() -> None:
    assert periods.resolve_timezone("Not/AZone").key == periods.FALLBACK_TZ
    assert periods.resolve_timezone("").key == periods.FALLBACK_TZ


def test_local_now_is_timezone_aware() -> None:
    assert periods.local_now("Asia/Tokyo").tzinfo is not None
