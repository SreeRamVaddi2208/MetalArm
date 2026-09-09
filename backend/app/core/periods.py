"""Derivation of `period_key` - the string that makes recurrence correct.

quest_completions carries UNIQUE(quest_id, user_id, period_key). That
constraint is the ONLY real defense against XP farming by double-submitting,
because "have they already completed this?" checked in Python is a race: two
concurrent requests both read "no" before either writes. So the key this module
produces is load-bearing, not cosmetic.

Everything is computed in the USER's timezone. A "daily" quest must reset at
the user's midnight, not the server's, or someone in UTC+13 gets a different
number of chances per day than someone in UTC-7.
"""

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.enums import ONE_OFF_PERIOD_KEY, Recurrence

# Fallback when a user's stored zone is unknown to the system tzdata. Better to
# award XP against UTC than to 500 on a completion.
FALLBACK_TZ = "UTC"


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(FALLBACK_TZ)


def local_now(tz_name: str) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone(resolve_timezone(tz_name))


def local_date(moment: dt.datetime, tz_name: str) -> dt.date:
    """The user's calendar date for an instant.

    `moment` must be timezone-aware; a naive datetime here would be silently
    treated as local-to-the-server and shift the boundary.
    """
    if moment.tzinfo is None:
        raise ValueError("local_date requires a timezone-aware datetime")
    return moment.astimezone(resolve_timezone(tz_name)).date()


def period_key(recurrence: str, moment: dt.datetime, tz_name: str) -> str:
    """The period bucket an instant falls into, for a given recurrence.

        daily   -> '2026-09-10'   (user's local calendar date)
        weekly  -> '2026-W37'     (ISO week; weeks start Monday)
        none    -> 'once'         (sentinel - see below)

    A one-off quest uses a constant sentinel rather than NULL because NULL
    never equals NULL in SQL, so a NULL key would satisfy the UNIQUE constraint
    an unlimited number of times - exactly the farming hole the constraint
    exists to close.

    ISO week uses isocalendar(), not strftime('%Y-W%W'): around New Year the
    ISO year differs from the calendar year (2026-12-28 is ISO 2026-W53 but
    2027-01-01 is also ISO 2026-W53), and mixing the two would let one week be
    completed twice.
    """
    day = local_date(moment, tz_name)

    if recurrence == Recurrence.DAILY.value:
        return day.isoformat()

    if recurrence == Recurrence.WEEKLY.value:
        iso_year, iso_week, _ = day.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    if recurrence == Recurrence.NONE.value:
        return ONE_OFF_PERIOD_KEY

    raise ValueError(f"unsupported recurrence: {recurrence!r}")
