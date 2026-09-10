"""The weekly workout streak.

A week counts once it holds STREAK_SESSIONS_PER_WEEK qualifying completed
sessions (see points_engine.session_qualifies). The streak is the run of
consecutive counting weeks.

Weeks rather than days because rest days are part of training. Weeks are ISO
weeks in the USER's timezone, via the same period_key() that drives weekly
quests, so the New-Year ISO-week overlap is handled once, in one place.

The current week is special: while it is still in progress and short of
target, it does not break the streak - last week's run is still alive. It only
breaks once the week ENDS short, which is exactly when the next week begins
and its key is no longer the current one.
"""

import dataclasses
import datetime as dt
from collections.abc import Mapping

from app.core import workout_rules as rules
from app.core.periods import period_key
from app.models.enums import Recurrence


def week_key(moment: dt.datetime, tz_name: str) -> str:
    return period_key(Recurrence.WEEKLY.value, moment, tz_name)


def _monday(key: str) -> dt.date:
    year, week = key.split("-W")
    return dt.date.fromisocalendar(int(year), int(week), 1)


def previous_week(key: str) -> str:
    """'2027-W01' -> '2026-W53'. Goes through a real date so ISO years with 53
    weeks are handled, rather than doing arithmetic on the week number."""
    iso_year, iso_week, _ = (_monday(key) - dt.timedelta(days=7)).isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def longest_weekly_streak(
    sessions_per_week: Mapping[str, int],
    target: int = rules.STREAK_SESSIONS_PER_WEEK,
) -> int:
    """The longest run of consecutive counting weeks ever held.

    Drives the streak badge, which - like the daily-streak badges - keys off a
    value that never goes down, so taking a week off cannot revoke it.
    """
    mondays = sorted(_monday(k) for k, n in sessions_per_week.items() if n >= target)
    best = run = 0
    previous: dt.date | None = None
    for monday in mondays:
        run = run + 1 if previous is not None and (monday - previous).days == 7 else 1
        best = max(best, run)
        previous = monday
    return best


@dataclasses.dataclass(frozen=True)
class WeeklyStreak:
    weeks: int
    this_week_sessions: int
    target: int
    this_week_done: bool

    @property
    def sessions_to_go(self) -> int:
        return max(0, self.target - self.this_week_sessions)


def weekly_streak(
    sessions_per_week: Mapping[str, int],
    current_week: str,
    target: int = rules.STREAK_SESSIONS_PER_WEEK,
) -> WeeklyStreak:
    """Streak state from counts of qualifying sessions keyed by ISO week."""
    this_week = sessions_per_week.get(current_week, 0)
    done = this_week >= target

    key = current_week if done else previous_week(current_week)
    weeks = 0
    while sessions_per_week.get(key, 0) >= target:
        weeks += 1
        key = previous_week(key)

    return WeeklyStreak(
        weeks=weeks, this_week_sessions=this_week, target=target, this_week_done=done
    )
