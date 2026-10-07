"""Analytics read models - pure functions from workout facts to the numbers
the clarity screens show. No database, no request: the routes load the facts
and these compute, so every figure can be checked by hand against a fixture.

Everything here works on LOCAL dates: the routes convert each instant to the
user's calendar date (periods.local_date) before calling in, so a week or a
month is the user's, not the server's. Weeks start on Monday (ISO).

Recovery lives next door, in app/core/recovery.py.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Iterable, Sequence
from decimal import Decimal

from app.core import workout_rules as rules

# A working set loads its exercise's primary muscles fully and the secondary
# ones half - the same weights the recovery model will use.
PRIMARY_WEIGHT = 1.0
SECONDARY_WEIGHT = 0.5


def muscle_load(sets: Iterable[tuple[Sequence[str], Sequence[str]]]) -> dict[str, float]:
    """Raw load per muscle group from working sets, each given as
    (primary muscle codes, secondary muscle codes)."""
    load: dict[str, float] = {}
    for primary, secondary in sets:
        for code in primary:
            load[code] = load.get(code, 0.0) + PRIMARY_WEIGHT
        for code in secondary:
            if code not in primary:
                load[code] = load.get(code, 0.0) + SECONDARY_WEIGHT
    return load


def muscle_intensity(sets: Iterable[tuple[Sequence[str], Sequence[str]]]) -> dict[str, float]:
    """0-1 per muscle group, relative to the most-worked one - what the body
    map fills with. Cardio and full-body are not places on a body."""
    load = {k: v for k, v in muscle_load(sets).items() if k not in ("cardio", "full_body")}
    top = max(load.values(), default=0.0)
    if top <= 0:
        return {}
    return {code: round(value / top, 3) for code, value in sorted(load.items())}


# ---------------------------------------------------------------------------
# Weeks
# ---------------------------------------------------------------------------


def monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def weeks_between(first: dt.date, last: dt.date) -> list[dt.date]:
    """Every Monday from first's week to last's, inclusive."""
    start, end = monday(first), monday(last)
    out = []
    while start <= end:
        out.append(start)
        start += dt.timedelta(days=7)
    return out


def range_start(range_: str, today: dt.date, first_day: dt.date | None) -> dt.date:
    """The Monday a range starts on. 3M is the last 13 weeks INCLUDING this
    one; "All" goes back to the week of the first workout (this week if none)."""
    if range_ == "All":
        return monday(first_day or today)
    weeks = rules.ANALYTICS_RANGE_WEEKS[range_]
    return monday(today) - dt.timedelta(days=7 * (weeks - 1))


# ---------------------------------------------------------------------------
# Session facts -> snapshot, series, calendar
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SessionFact:
    """One completed workout, as the clarity screens see it."""

    day: dt.date                 # local date it started
    duration_seconds: int
    volume_kg: Decimal
    working_sets: int
    prs: int


METRICS = ("duration", "volume", "workouts", "points")


def _value(facts: Sequence[SessionFact], metric: str) -> float:
    if metric == "workouts":
        return float(len(facts))
    if metric == "duration":
        return float(sum(f.duration_seconds for f in facts))
    if metric == "volume":
        return float(sum((f.volume_kg for f in facts), Decimal(0)))
    raise ValueError(metric)


def _in_week(facts: Iterable[SessionFact], week: dt.date) -> list[SessionFact]:
    end = week + dt.timedelta(days=7)
    return [f for f in facts if week <= f.day < end]


@dataclasses.dataclass(frozen=True)
class Snapshot:
    week: dt.date
    workouts: int
    duration_seconds: int
    volume_kg: float
    # This week minus last week, per stat.
    workouts_delta: int
    duration_delta: int
    volume_delta: float


def snapshot(facts: Sequence[SessionFact], week: dt.date) -> Snapshot:
    """This week's three numbers and how each moved since the week before."""
    now = _in_week(facts, week)
    before = _in_week(facts, week - dt.timedelta(days=7))
    workouts, duration, volume = (int(_value(now, "workouts")), int(_value(now, "duration")),
                                  round(_value(now, "volume"), 1))
    return Snapshot(
        week=week, workouts=workouts, duration_seconds=duration, volume_kg=volume,
        workouts_delta=workouts - int(_value(before, "workouts")),
        duration_delta=duration - int(_value(before, "duration")),
        volume_delta=round(volume - _value(before, "volume"), 1),
    )


def weekly_series(facts: Sequence[SessionFact], metric: str, start: dt.date, end: dt.date,
                  points_by_day: dict[dt.date, int] | None = None) -> list[tuple[dt.date, float]]:
    """(Monday, value) for every week from start's to end's, zero weeks
    included so the chart's x axis is even. Points come from the ledger, by
    the day each award was written (`points_by_day`), not from sessions -
    quests and reversals count too."""
    out = []
    for week in weeks_between(start, end):
        if metric == "points":
            stop = week + dt.timedelta(days=7)
            value = float(sum(v for d, v in (points_by_day or {}).items() if week <= d < stop))
        else:
            value = _value(_in_week(facts, week), metric)
        out.append((week, round(value, 1)))
    return out


@dataclasses.dataclass(frozen=True)
class CalendarMonth:
    month: dt.date               # first of the month
    days: dict[dt.date, int]     # trained day -> workouts that day
    runs: list[tuple[dt.date, dt.date]]  # consecutive trained days, first..last


def calendar(facts: Sequence[SessionFact], month: dt.date) -> CalendarMonth:
    first = month.replace(day=1)
    nxt = (first + dt.timedelta(days=32)).replace(day=1)
    days: dict[dt.date, int] = {}
    for f in facts:
        if first <= f.day < nxt:
            days[f.day] = days.get(f.day, 0) + 1
    runs: list[tuple[dt.date, dt.date]] = []
    for day in sorted(days):
        if runs and runs[-1][1] + dt.timedelta(days=1) == day:
            runs[-1] = (runs[-1][0], day)
        else:
            runs.append((day, day))
    return CalendarMonth(month=first, days=days, runs=runs)


def muscle_sets(sets: Iterable[tuple[Sequence[str], Sequence[str]]]) -> tuple[dict[str, float], dict[str, float]]:
    """(load per muscle, 0-1 intensity) for a range's working sets - the
    You tab's "muscles you worked" map and its legend."""
    load = {k: round(v, 1) for k, v in muscle_load(sets).items() if k not in ("cardio", "full_body")}
    top = max(load.values(), default=0.0)
    intensity = {k: round(v / top, 3) for k, v in sorted(load.items())} if top > 0 else {}
    return load, intensity


# ---------------------------------------------------------------------------
# Monthly Summary
# ---------------------------------------------------------------------------


def month_bounds(month: dt.date) -> tuple[dt.date, dt.date]:
    """(first day, first day of the next month)."""
    first = month.replace(day=1)
    return first, (first + dt.timedelta(days=32)).replace(day=1)


def volume_comparison(kg: float) -> str:
    """"That's about 3 small cars" - the largest everyday weight it reaches at
    least once; nothing for a month with no volume."""
    if kg <= 0:
        return ""
    reached = [c for c in rules.VOLUME_COMPARISONS if kg >= c[2]]
    if not reached:
        one, _, weight = rules.VOLUME_COMPARISONS[0]
        return f"That's {round(kg / weight * 100)}% of {one}"
    one, many, weight = reached[-1]
    count = kg / weight
    if count < 1.5:
        return f"That's about {one}"
    shown = f"{count:.1f}".rstrip("0").rstrip(".") if count < 10 else f"{round(count):,}"
    return f"That's about {shown} {many}"


@dataclasses.dataclass(frozen=True)
class MonthTotals:
    workouts: int
    duration_seconds: int
    volume_kg: float
    working_sets: int
    active_days: int
    best_week_workouts: int


def month_totals(facts: Sequence[SessionFact], month: dt.date) -> MonthTotals:
    first, nxt = month_bounds(month)
    inside = [f for f in facts if first <= f.day < nxt]
    weeks: dict[dt.date, int] = {}
    for f in inside:
        weeks[monday(f.day)] = weeks.get(monday(f.day), 0) + 1
    return MonthTotals(
        workouts=len(inside),
        duration_seconds=sum(f.duration_seconds for f in inside),
        volume_kg=round(float(sum((f.volume_kg for f in inside), Decimal(0))), 1),
        working_sets=sum(f.working_sets for f in inside),
        active_days=len({f.day for f in inside}),
        best_week_workouts=max(weeks.values(), default=0),
    )
