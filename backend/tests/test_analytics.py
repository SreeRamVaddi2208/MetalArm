"""Overhaul phase 2: the clarity screens' numbers.

The pure functions are checked against hand-worked figures; the endpoints
against a seeded account whose every number is worked out in the comments -
the phase 2 gate ("every number matches a hand-checked calculation").
"""

import datetime as dt
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import analytics, recovery
from app.core.periods import local_date
from app.models.workout import SetEntry, WorkoutSession
from tests.test_workouts import BENCH, SQUAT, exercise_id, finish, log, start

A = "/api/v1"
UTC = dt.timezone.utc


def fact(day: dt.date, duration: int = 3600, volume: str = "1000", sets: int = 3, prs: int = 0):
    return analytics.SessionFact(day, duration, Decimal(volume), sets, prs)


# ---------------------------------------------------------------------------
# Pure: weeks, snapshot, series, calendar, muscles
# ---------------------------------------------------------------------------


def test_weeks_start_on_monday() -> None:
    assert analytics.monday(dt.date(2026, 10, 11)) == dt.date(2026, 10, 5)   # Sunday -> Monday
    assert analytics.monday(dt.date(2026, 10, 5)) == dt.date(2026, 10, 5)
    assert analytics.weeks_between(dt.date(2026, 9, 30), dt.date(2026, 10, 6)) == [
        dt.date(2026, 9, 28), dt.date(2026, 10, 5)]


def test_ranges_count_whole_weeks_including_this_one() -> None:
    today = dt.date(2026, 10, 7)
    assert analytics.range_start("3M", today, None) == dt.date(2026, 7, 13)   # 13 Mondays to Oct 5
    assert len(analytics.weeks_between(analytics.range_start("Year", today, None), today)) == 52
    assert analytics.range_start("All", today, dt.date(2025, 1, 1)) == dt.date(2024, 12, 30)
    assert analytics.range_start("All", today, None) == dt.date(2026, 10, 5)


def test_snapshot_compares_with_the_week_before() -> None:
    week = dt.date(2026, 10, 5)
    facts = [fact(dt.date(2026, 10, 5), 3600, "2340"), fact(dt.date(2026, 10, 7), 1800, "500.5"),
             fact(dt.date(2026, 9, 30), 2700, "1440"),
             fact(dt.date(2026, 9, 20), 9999, "9999")]   # two weeks ago: in neither
    snap = analytics.snapshot(facts, week)
    assert (snap.workouts, snap.duration_seconds, snap.volume_kg) == (2, 5400, 2840.5)
    assert (snap.workouts_delta, snap.duration_delta, snap.volume_delta) == (1, 2700, 1400.5)


def test_series_has_every_week_and_points_come_from_the_ledger() -> None:
    facts = [fact(dt.date(2026, 9, 21), volume="100"), fact(dt.date(2026, 10, 6), volume="250")]
    vol = analytics.weekly_series(facts, "volume", dt.date(2026, 9, 21), dt.date(2026, 10, 7))
    assert vol == [(dt.date(2026, 9, 21), 100.0), (dt.date(2026, 9, 28), 0.0), (dt.date(2026, 10, 5), 250.0)]
    pts = analytics.weekly_series([], "points", dt.date(2026, 9, 28), dt.date(2026, 10, 7),
                                  {dt.date(2026, 10, 4): 30, dt.date(2026, 10, 5): 12, dt.date(2026, 10, 6): -2})
    assert pts == [(dt.date(2026, 9, 28), 30.0), (dt.date(2026, 10, 5), 10.0)]


def test_calendar_counts_days_and_runs() -> None:
    facts = [fact(dt.date(2026, 10, d)) for d in (1, 2, 2, 3, 6, 31)] + [fact(dt.date(2026, 9, 30))]
    cal = analytics.calendar(facts, dt.date(2026, 10, 15))
    assert cal.days == {dt.date(2026, 10, 1): 1, dt.date(2026, 10, 2): 2, dt.date(2026, 10, 3): 1,
                        dt.date(2026, 10, 6): 1, dt.date(2026, 10, 31): 1}
    assert cal.runs == [(dt.date(2026, 10, 1), dt.date(2026, 10, 3)), (dt.date(2026, 10, 6), dt.date(2026, 10, 6)),
                        (dt.date(2026, 10, 31), dt.date(2026, 10, 31))]


def test_muscle_sets_weigh_secondary_half() -> None:
    load, intensity = analytics.muscle_sets([(["chest"], ["triceps"])] * 4 + [(["triceps"], [])] * 2
                                            + [(["cardio"], [])])
    assert load == {"chest": 4.0, "triceps": 4.0}       # 4 x 0.5 + 2 x 1.0
    assert intensity == {"chest": 1.0, "triceps": 1.0}


# ---------------------------------------------------------------------------
# Pure: recovery
# ---------------------------------------------------------------------------

SIZES = {"chest": "large", "triceps": "small", "shoulders": "small", "quads": "large"}
NOW = dt.datetime(2026, 10, 6, 12, tzinfo=UTC)


def test_recovery_decays_by_size_class() -> None:
    sets = [recovery.WorkingSet(NOW - dt.timedelta(hours=36), ["chest"], ["triceps"])] * 3
    r = recovery.recovery(sets, NOW, SIZES)
    # chest (large): 3 x 1.0 x 0.5^(36/36) = 1.5 of 10 -> 85
    # triceps (small, secondary): 3 x 0.5 x 0.5^(36/24) = 0.530 of 6 -> 91.2 -> 91
    assert r.muscles["chest"] == 85 and r.muscles["triceps"] == 91
    assert r.muscles["quads"] == 100 and r.muscles["shoulders"] == 100
    # Overall, weighted by load in 7 days: (85 x 3 + 91.16 x 1.5) / 4.5 = 87.05 -> 87
    assert r.overall == 87


def test_recovery_bottoms_out_and_forgets_old_sets() -> None:
    heavy = [recovery.WorkingSet(NOW, ["triceps"], [])] * 10            # 10 of 6 -> 0
    old = [recovery.WorkingSet(NOW - dt.timedelta(hours=97), ["chest"], [])] * 20  # outside 96 h
    r = recovery.recovery(heavy + old, NOW, SIZES)
    assert r.muscles["triceps"] == 0 and r.muscles["chest"] == 100
    # Chest was still trained this week, so it is in the overall: (0 x 10 + 100 x 20) / 30
    assert r.overall == 67
    assert recovery.recovery([], NOW, SIZES).overall == 100


# ---------------------------------------------------------------------------
# Timezones: weeks end at the USER's midnight, across DST too
# ---------------------------------------------------------------------------


def test_a_late_sunday_session_stays_in_its_local_week() -> None:
    # New York, DST ends Sunday 2026-11-01 at 02:00. 23:30 EST Sunday is 04:30
    # UTC on Monday - still the week of Oct 26 for the user.
    late = dt.datetime(2026, 11, 2, 4, 30, tzinfo=UTC)
    early = dt.datetime(2026, 11, 2, 5, 30, tzinfo=UTC)      # 00:30 Monday local
    days = [local_date(late, "America/New_York"), local_date(early, "America/New_York")]
    assert days == [dt.date(2026, 11, 1), dt.date(2026, 11, 2)]
    snap = analytics.snapshot([fact(days[0]), fact(days[1])], dt.date(2026, 11, 2))
    assert (snap.workouts, snap.workouts_delta) == (1, 0)


def test_an_early_monday_session_east_of_utc_starts_the_new_week() -> None:
    # 20:00 UTC Sunday is 01:30 Monday in Kolkata.
    day = local_date(dt.datetime(2026, 10, 4, 20, tzinfo=UTC), "Asia/Kolkata")
    assert day == dt.date(2026, 10, 5) and analytics.monday(day) == dt.date(2026, 10, 5)


# ---------------------------------------------------------------------------
# API, against a seeded account - the gate
# ---------------------------------------------------------------------------


def _place(db: Session, session_id: str, at: dt.datetime, duration: int) -> None:
    """Move a finished session (and its sets) to `at`, lasting `duration`."""
    db.execute(update(WorkoutSession).where(WorkoutSession.id == session_id).values(
        started_at=at, ended_at=at + dt.timedelta(seconds=duration), duration_seconds=duration))
    db.execute(update(SetEntry).where(SetEntry.session_id == session_id).values(
        completed_at=at + dt.timedelta(minutes=5)))
    db.commit()


@pytest.fixture()
def seeded(client: TestClient, auth: dict, db: Session):
    """Two workouts, in UTC:
       A: this Monday 10:00, 60 min - bench warm-up 60x5, bench 3 x 100x5,
          squat 2 x 140x3. Volume 3 x 500 + 2 x 420 = 2340 kg.
       B: last Wednesday 18:00, 45 min - bench 2 x 90x8. Volume 1440 kg."""
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    today = dt.datetime.now(UTC).date()
    monday = analytics.monday(today)
    b = start(client, auth, name="B")
    for _ in range(2):
        log(client, auth, b["id"], bench, 90, 8)
    fb = finish(client, auth, b["id"])
    _place(db, b["id"], dt.datetime.combine(monday - dt.timedelta(days=5), dt.time(18), UTC), 2700)
    a = start(client, auth, name="A")
    log(client, auth, a["id"], bench, 60, 5, is_warmup=True)
    for _ in range(3):
        log(client, auth, a["id"], bench, 100, 5)
    for _ in range(2):
        log(client, auth, a["id"], squat, 140, 3)
    fa = finish(client, auth, a["id"])
    _place(db, a["id"], dt.datetime.combine(monday, dt.time(10), UTC), 3600)
    return {"bench": bench, "squat": squat, "monday": monday, "today": today,
            "a": a["id"], "b": b["id"], "points_a": fa["points_credited"], "points_b": fb["points_credited"]}


def test_snapshot_matches_the_seed(client: TestClient, auth: dict, seeded) -> None:
    s = client.get(f"{A}/analytics/snapshot", headers=auth).json()
    assert s["week_start"] == seeded["monday"].isoformat()
    assert (s["workouts"], s["duration_seconds"], s["volume_kg"]) == (1, 3600, 2340.0)
    assert (s["workouts_delta"], s["duration_delta"], s["volume_delta"]) == (0, 900, 900.0)
    last = client.get(f"{A}/analytics/snapshot",
                      params={"week": (seeded["monday"] - dt.timedelta(days=3)).isoformat()}, headers=auth).json()
    assert (last["workouts"], last["volume_kg"], last["volume_delta"]) == (1, 1440.0, 1440.0)


def test_series_matches_the_seed(client: TestClient, auth: dict, seeded) -> None:
    vol = client.get(f"{A}/analytics/series", params={"metric": "volume", "range": "3M"}, headers=auth).json()
    assert len(vol["points"]) == 13 and vol["unit"] == "kg"
    assert [p["value"] for p in vol["points"][-2:]] == [1440.0, 2340.0]
    assert sum(p["value"] for p in vol["points"][:-2]) == 0
    work = client.get(f"{A}/analytics/series", params={"metric": "workouts", "range": "All"}, headers=auth).json()
    assert [p["value"] for p in work["points"]] == [1.0, 1.0]
    pts = client.get(f"{A}/analytics/series", params={"metric": "points", "range": "3M"}, headers=auth).json()
    # Points are counted on the day each award was WRITTEN (today) - the
    # sessions were moved back in time after earning them.
    assert pts["points"][-1]["value"] == seeded["points_a"] + seeded["points_b"]


def test_muscles_this_week_match_the_seed(client: TestClient, auth: dict, seeded) -> None:
    m = client.get(f"{A}/analytics/muscles", headers=auth).json()
    load = {x["code"]: x["sets"] for x in m["muscles"]}
    # Bench: chest, triceps, shoulders primary x 3 working sets (warm-up out);
    # squat: quads, glutes, hamstrings x 2. Last week's bench is outside.
    assert load == {"chest": 3.0, "triceps": 3.0, "shoulders": 3.0, "quads": 2.0, "glutes": 2.0, "hamstrings": 2.0}
    assert {x["code"]: x["intensity"] for x in m["muscles"]}["quads"] == 0.667
    assert all(x["svg_path_ids"] for x in m["muscles"])


def test_calendar_matches_the_seed(client: TestClient, auth: dict, seeded) -> None:
    month = seeded["monday"].strftime("%Y-%m")
    c = client.get(f"{A}/analytics/calendar", params={"month": month}, headers=auth).json()
    expected = {d.isoformat() for d in (seeded["monday"], seeded["monday"] - dt.timedelta(days=5))
                if d.strftime("%Y-%m") == month}
    assert {d["date"] for d in c["days"]} == expected
    assert all(r["days"] == 1 for r in c["runs"])


def test_history_reads_the_finish_snapshot(client: TestClient, auth: dict, seeded) -> None:
    page = client.get(f"{A}/history", params={"limit": 1}, headers=auth).json()
    row = page["months"][0]["sessions"][0]
    assert (row["name"], row["duration_seconds"], row["volume_kg"], row["working_sets"]) == ("A", 3600, 2340.0, 5)
    assert row["exercise_count"] == 2 and row["points"] == seeded["points_a"]
    nxt = client.get(f"{A}/history", params={"cursor": page["next_cursor"]}, headers=auth).json()
    assert [s["name"] for m in nxt["months"] for s in m["sessions"]] == ["B"] and nxt["next_cursor"] is None
    assert client.get(f"{A}/history", params={"cursor": "nope"}, headers=auth).status_code == 422


def test_my_exercises_show_best_set_and_e1rm(client: TestClient, auth: dict, seeded) -> None:
    items = client.get(f"{A}/me/exercises", headers=auth).json()["items"]
    by = {i["name"]: i for i in items}
    assert by[BENCH]["sessions"] == 2 and by[SQUAT]["sessions"] == 1
    assert (by[BENCH]["best_weight_kg"], by[BENCH]["best_weight_reps"]) == (100.0, 5)
    # Epley: 90 x (30 + 8) / 30 = 114; 100 x 35 / 30 = 116.67 - the best is 116.67.
    assert by[BENCH]["best_est_1rm"] == 116.67
    assert by[SQUAT]["best_est_1rm"] == 154.0                     # 140 x 33 / 30
    page = client.get(f"{A}/me/exercises", params={"limit": 1}, headers=auth).json()
    assert len(page["items"]) == 1 and page["next_cursor"]


def test_exercise_stats_match_the_seed(client: TestClient, auth: dict, seeded) -> None:
    s = client.get(f"{A}/exercises/{seeded['bench']}/stats", headers=auth).json()
    assert [(p["best_set_weight_kg"], p["best_set_reps"], p["est_1rm"], p["volume_kg"], p["max_reps"])
            for p in s["series"]] == [(90.0, 8, 114.0, 1440.0, 8), (100.0, 5, 116.67, 1500.0, 5)]
    newest = s["sessions"][0]
    assert newest["name"] == "A" and [x["set_type"] for x in newest["sets"]][0] == "warmup"
    assert len(newest["sets"]) == 4
    records = {r["record_type"]: r["value"] for r in s["records"]}
    assert records["max_weight"] == 100.0 and records["est_1rm"] == 116.67


def test_recovery_from_logged_sets(client: TestClient, auth: dict, db: Session) -> None:
    bench = exercise_id(client, auth, BENCH)
    s = start(client, auth)
    for _ in range(3):
        log(client, auth, s["id"], bench, 100, 5)
    finish(client, auth, s["id"])
    db.execute(update(SetEntry).where(SetEntry.session_id == s["id"]).values(
        completed_at=dt.datetime.now(UTC) - dt.timedelta(hours=36)))
    db.commit()
    r = client.get(f"{A}/analytics/recovery", headers=auth).json()
    pct = {m["code"]: m["percent"] for m in r["muscles"]}
    # chest (large): 3 x 0.5^(36/36) = 1.5 of 10 -> 85
    # triceps, shoulders (small): 3 x 0.5^(36/24) = 1.06 of 6 -> 82.3 -> 82
    assert (pct["chest"], pct["triceps"], pct["shoulders"]) == (85, 82, 82)
    # Equal load on all three: (85 + 82.32 + 82.32) / 3 = 83.2 -> 83
    assert r["overall"] == 83 and "estimate" in r["note"]


def test_analytics_compute_in_the_users_timezone(client: TestClient, user_factory, db: Session) -> None:
    headers, _ = user_factory(timezone="Asia/Kolkata")
    bench = exercise_id(client, headers, BENCH)
    s = start(client, headers)
    log(client, headers, s["id"], bench, 100, 5)
    finish(client, headers, s["id"])
    # Monday 01:30 in Kolkata is Sunday 20:00 UTC: it belongs to Monday's week.
    monday = analytics.monday(dt.datetime.now(UTC).date()) - dt.timedelta(days=7)
    _place(db, s["id"], dt.datetime.combine(monday - dt.timedelta(days=1), dt.time(20), UTC), 1800)
    snap = client.get(f"{A}/analytics/snapshot", params={"week": monday.isoformat()}, headers=headers).json()
    assert snap["workouts"] == 1
    cal = client.get(f"{A}/analytics/calendar", params={"month": monday.strftime("%Y-%m")}, headers=headers).json()
    assert monday.isoformat() in {d["date"] for d in cal["days"]}


def test_analytics_validate_input(client: TestClient, auth: dict) -> None:
    assert client.get(f"{A}/analytics/series", params={"metric": "calories"}, headers=auth).status_code == 422
    assert client.get(f"{A}/analytics/series", params={"range": "2Y"}, headers=auth).status_code == 422
    assert client.get(f"{A}/analytics/snapshot", params={"week": "monday"}, headers=auth).status_code == 422
    assert client.get(f"{A}/analytics/muscles", params={"from": "2026-10-07", "to": "2026-10-01"},
                      headers=auth).status_code == 422
    assert client.get(f"{A}/analytics/recovery").status_code == 401


def test_imported_workouts_get_their_totals(client: TestClient, auth: dict) -> None:
    from tests.test_import import STRONG_CSV, post_import

    assert post_import(client, auth, STRONG_CSV).status_code == 200
    rows = {s["name"]: s for m in client.get(f"{A}/history", headers=auth).json()["months"] for s in m["sessions"]}
    push = rows["Push Day"]
    # Working sets only: 80 x 5 + 82.5 x 5 + 15 x 12 = 992.5 kg; 1h 5m.
    assert (push["volume_kg"], push["working_sets"], push["duration_seconds"]) == (992.5, 3, 3900)
