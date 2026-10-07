"""Overhaul phase 5: the Monthly Summary - the gate is a full month of
seeded workouts producing a summary whose numbers match a hand count."""

import datetime as dt
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import analytics
from app.models.workout import PersonalRecord, PointsLedgerEntry, SetEntry, WorkoutSession
from tests.test_workouts import BENCH, SQUAT, exercise_id, finish, log, start

A = "/api/v1"
UTC = dt.timezone.utc


def test_volume_comparisons_read_naturally() -> None:
    assert analytics.volume_comparison(0) == ""
    assert analytics.volume_comparison(225) == "That's 50% of a grand piano"
    assert analytics.volume_comparison(500) == "That's about a grand piano"
    assert analytics.volume_comparison(3915) == "That's about 3.3 small cars"
    assert analytics.volume_comparison(12_000) == "That's about 2 African elephants"
    assert analytics.volume_comparison(4_500_000) == "That's about 30 blue whales"


def test_month_totals() -> None:
    f = lambda day, d, v, s: analytics.SessionFact(day, d, Decimal(v), s, 0)  # noqa: E731
    facts = [f(dt.date(2026, 9, 1), 3600, "1500", 3), f(dt.date(2026, 9, 2), 1800, "500", 2),
             f(dt.date(2026, 9, 2), 600, "100", 1), f(dt.date(2026, 9, 30), 900, "0", 0),
             f(dt.date(2026, 10, 1), 9999, "9999", 9), f(dt.date(2026, 8, 31), 9999, "9999", 9)]
    t = analytics.month_totals(facts, dt.date(2026, 9, 15))
    # Sep 1 & 2 are Tue/Wed (one week, 3 workouts); Sep 30 is the next week's.
    assert (t.workouts, t.duration_seconds, t.volume_kg, t.working_sets, t.active_days, t.best_week_workouts) == (
        4, 6900, 2100.0, 6, 3, 3)


def _place(db: Session, session_id: str, at: dt.datetime, duration: int) -> None:
    """Move a finished workout - and everything it produced - to `at`."""
    db.execute(update(WorkoutSession).where(WorkoutSession.id == session_id).values(
        started_at=at, ended_at=at + dt.timedelta(seconds=duration), duration_seconds=duration))
    db.execute(update(SetEntry).where(SetEntry.session_id == session_id).values(
        completed_at=at + dt.timedelta(minutes=5)))
    db.execute(update(PersonalRecord).where(PersonalRecord.session_id == session_id).values(
        achieved_at=at + dt.timedelta(minutes=5)))
    db.execute(update(PointsLedgerEntry).where(PointsLedgerEntry.session_id == session_id).values(
        created_at=at + dt.timedelta(seconds=duration)))
    db.commit()


def _workout(client, auth, ex, sets, weight, reps) -> str:
    s = start(client, auth)
    for _ in range(sets):
        log(client, auth, s["id"], ex, weight, reps)
    finish(client, auth, s["id"])
    return s["id"]


def test_a_seeded_month_summarises_exactly(client: TestClient, auth: dict, db: Session) -> None:
    """Last month, in UTC:
         day 3   bench 3 x 100x5  -> 1,500 kg, 3 sets, 60 min (bench baseline)
         day 10  bench 3 x 105x5  -> 1,575 kg, 3 sets, 45 min (heavier: records)
         day 11  squat 2 x 140x3  ->   840 kg, 2 sets, 30 min (squat baseline)
       plus one workout the month before and one this month, which must not count.
       Totals: 3 workouts, 8,100 s, 3,915 kg, 8 sets, 3 days -> "about 3.3 small cars".
       Muscles: bench works chest, triceps, shoulders (6 sets each), squat
       quads, glutes, hamstrings (2 each) - chest first (ties by name)."""
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    today = dt.datetime.now(UTC).date()
    first = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    at = lambda day: dt.datetime.combine(first.replace(day=day), dt.time(10), UTC)  # noqa: E731
    before = _workout(client, auth, bench, 1, 60, 5)
    _place(db, before, at(1) - dt.timedelta(days=5), 600)
    a = _workout(client, auth, bench, 3, 100, 5)
    _place(db, a, at(3), 3600)
    b = _workout(client, auth, bench, 3, 105, 5)
    _place(db, b, at(10), 2700)
    c = _workout(client, auth, squat, 2, 140, 3)
    _place(db, c, at(11), 1800)
    _workout(client, auth, bench, 1, 50, 5)     # this month: left where it is

    s = client.get(f"{A}/analytics/monthly-summary", headers=auth).json()
    assert s["month"] == first.strftime("%Y-%m")
    assert (s["workouts"], s["duration_seconds"], s["volume_kg"], s["working_sets"], s["active_days"]) == (
        3, 8100, 3915.0, 8, 3)
    weeks = {analytics.monday(first.replace(day=d)) for d in (3, 10, 11)}
    assert s["best_week_workouts"] == (2 if len(weeks) == 2 else 1)
    assert s["volume_comparison"] == "That's about 3.3 small cars"
    assert [(m["code"], m["sets"]) for m in s["muscles"]][:3] == [("chest", 6.0), ("shoulders", 6.0), ("triceps", 6.0)]
    assert {m["code"] for m in s["muscles"]} == {"chest", "shoulders", "triceps", "quads", "glutes", "hamstrings"}
    # The records are day 10's, and only those: the earlier sessions were baselines
    # (the month before's 60 kg was beaten by day 3 - so day 3 holds records too).
    expected = db.scalar(select(func.count(PersonalRecord.id)).where(
        PersonalRecord.session_id.in_([a, b, c]), PersonalRecord.is_baseline.is_(False)))
    assert s["record_count"] == expected > 0
    assert all(r["exercise_name"] in (BENCH, SQUAT) for r in s["records"])
    points = db.scalar(select(func.sum(PointsLedgerEntry.points)).where(
        PointsLedgerEntry.session_id.in_([a, b, c])))
    assert s["points"] == points
    assert (s["duels_played"], s["duels_won"]) == (0, 0)

    # Any month can be asked for; an empty one is all zeros.
    empty = client.get(f"{A}/analytics/monthly-summary", params={"month": "2020-01"}, headers=auth).json()
    assert (empty["workouts"], empty["volume_comparison"], empty["muscles"], empty["records"]) == (0, "", [], [])

    hero = client.get(f"{A}/analytics/monthly-summary/latest", headers=auth).json()
    assert hero == {"month": first.strftime("%Y-%m"), "workouts": 3, "show": today.day <= 7}


def test_the_month_is_the_users(client: TestClient, user_factory, db: Session) -> None:
    """A workout at 20:00 UTC on the last day of a month is the next month's in
    Kolkata (01:30)."""
    headers, _ = user_factory(timezone="Asia/Kolkata")
    bench = exercise_id(client, headers, BENCH)
    s = _workout(client, headers, bench, 3, 100, 5)
    _place(db, s, dt.datetime(2026, 8, 31, 20, tzinfo=UTC), 1800)
    aug = client.get(f"{A}/analytics/monthly-summary", params={"month": "2026-08"}, headers=headers).json()
    sep = client.get(f"{A}/analytics/monthly-summary", params={"month": "2026-09"}, headers=headers).json()
    assert (aug["workouts"], sep["workouts"]) == (0, 1)
    assert sep["volume_kg"] == 1500.0 and sep["muscles"][0]["code"] == "chest"
