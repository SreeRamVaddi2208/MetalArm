"""Workout sessions over HTTP: the logging loop, records, the points ledger,
reversals, and the anti-farming guarantees.

Point values are asserted against workout_rules constants, so these tests pin
BEHAVIOUR (what is paid, when, and how often), not today's placeholder numbers.

Sessions need real duration to qualify for the session bonus, so `age()` moves
a session's started_at into the past through the shared test DB session rather
than sleeping.
"""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import points_engine as pe
from app.core import workout_rules as rules
from app.models.workout import PointsLedgerEntry, WorkoutSession

WK = "/api/v1/workouts"
EX = "/api/v1/exercises"
ME = "/api/v1/auth/me"

BENCH = "Barbell Bench Press"
SQUAT = "Back Squat"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def exercise_id(client: TestClient, auth: dict, name: str = BENCH) -> str:
    rows = client.get(EX, params={"q": name, "limit": 200}, headers=auth).json()
    return next(r["id"] for r in rows if r["name"] == name)


def start(client: TestClient, auth: dict, **body) -> dict:
    r = client.post(f"{WK}/sessions", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def log(
    client: TestClient,
    auth: dict,
    session_id: str,
    ex_id: str,
    weight: float = 100,
    reps: int | None = 5,
    **extra,
) -> dict:
    body = {"exercise_id": ex_id, "weight": weight, "reps": reps, **extra}
    r = client.post(f"{WK}/sessions/{session_id}/sets", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def finish(client: TestClient, auth: dict, session_id: str) -> dict:
    r = client.post(f"{WK}/sessions/{session_id}/finish", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def age(db: Session, session_id: str, minutes: float) -> None:
    db.execute(
        update(WorkoutSession)
        .where(WorkoutSession.id == uuid.UUID(session_id))
        .values(started_at=WorkoutSession.started_at - dt.timedelta(minutes=minutes))
    )
    db.flush()
    db.expire_all()


def progress(client: TestClient, auth: dict) -> dict:
    return client.get(ME, headers=auth).json()["progress"]


def full_workout(
    client: TestClient, auth: dict, db: Session, ex_id: str, sets=((100, 5),) * 3
) -> dict:
    """A session that qualifies: enough working sets and enough time."""
    session = start(client, auth)
    for weight, reps in sets:
        log(client, auth, session["id"], ex_id, weight=weight, reps=reps)
    age(db, session["id"], 45)
    return finish(client, auth, session["id"])


def ledger_total(db: Session, user_id: str) -> int:
    rows = db.scalars(
        select(PointsLedgerEntry.points).where(
            PointsLedgerEntry.user_id == uuid.UUID(user_id)
        )
    )
    return sum(rows)


# --------------------------------------------------------------------------
# Access
# --------------------------------------------------------------------------


def test_workout_endpoints_require_auth(client: TestClient) -> None:
    assert client.get(f"{WK}/sessions/active").status_code == 401
    assert client.post(f"{WK}/sessions", json={}).status_code == 401
    assert client.get(EX).status_code == 401


def test_another_users_session_is_404_everywhere(
    client: TestClient, user_factory
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    ex = exercise_id(client, alice)
    session = start(client, alice)
    logged = log(client, alice, session["id"], ex)
    base = f"{WK}/sessions/{session['id']}"

    assert client.get(base, headers=bob).status_code == 404
    assert client.post(f"{base}/sets", json={"exercise_id": ex, "reps": 5}, headers=bob).status_code == 404
    assert client.delete(f"{base}/sets/{logged['set']['id']}", headers=bob).status_code == 404
    assert client.post(f"{base}/finish", headers=bob).status_code == 404
    assert client.post(f"{base}/abandon", headers=bob).status_code == 404
    # And bob earned nothing from alice's workout.
    assert progress(client, bob)["total_xp"] == 0


# --------------------------------------------------------------------------
# Session lifecycle
# --------------------------------------------------------------------------


def test_the_active_session_can_be_rehydrated(client: TestClient, auth: dict) -> None:
    assert client.get(f"{WK}/sessions/active", headers=auth).json() == {"session": None}
    session = start(client, auth, name="Push day")
    active = client.get(f"{WK}/sessions/active", headers=auth).json()["session"]
    assert active["id"] == session["id"]
    assert active["status"] == "in_progress"
    assert active["name"] == "Push day"


def test_only_one_workout_can_be_live(client: TestClient, auth: dict) -> None:
    """Parallel sessions would multiply the per-session caps."""
    first = start(client, auth)
    second = client.post(f"{WK}/sessions", json={}, headers=auth)
    assert second.status_code == 409
    assert first["id"] in second.json()["detail"]


def test_a_finished_workout_is_immutable(client: TestClient, auth: dict, db: Session) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    logged = log(client, auth, session["id"], ex)
    finish(client, auth, session["id"])
    base = f"{WK}/sessions/{session['id']}"

    assert client.post(f"{base}/sets", json={"exercise_id": ex, "reps": 5}, headers=auth).status_code == 409
    assert client.delete(f"{base}/sets/{logged['set']['id']}", headers=auth).status_code == 409
    assert client.patch(f"{base}/sets/{logged['set']['id']}", json={"reps": 9}, headers=auth).status_code == 409
    assert client.post(f"{base}/finish", headers=auth).status_code == 409
    assert client.post(f"{base}/abandon", headers=auth).status_code == 409


def test_a_session_open_too_long_refuses_new_sets(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    age(db, session["id"], (rules.MAX_SESSION_HOURS + 1) * 60)
    r = client.post(
        f"{WK}/sessions/{session['id']}/sets", json={"exercise_id": ex, "reps": 5}, headers=auth
    )
    assert r.status_code == 409


def test_starting_from_a_routine_lists_its_exercises_and_targets(
    client: TestClient, auth: dict
) -> None:
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    routine = client.post(
        "/api/v1/routines",
        json={
            "name": "Full body",
            "exercises": [
                {"exercise_id": squat, "target_sets": 5, "target_reps": 5, "target_weight_kg": 100},
                {"exercise_id": bench, "target_sets": 3, "target_reps": 8},
            ],
        },
        headers=auth,
    ).json()
    session = start(client, auth, routine_id=routine["id"])

    assert session["name"] == "Full body"
    assert [e["exercise"]["id"] for e in session["exercises"]] == [squat, bench]
    assert session["exercises"][0]["target"]["target_weight_kg"] == 100
    assert session["exercises"][0]["sets"] == []


def test_the_previous_sessions_sets_are_the_ghost_values(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    full_workout(client, auth, db, ex, sets=((80, 8), (85, 6), (90, 4)))

    session = start(client, auth)
    log(client, auth, session["id"], ex, weight=85, reps=8)
    detail = client.get(f"{WK}/sessions/{session['id']}", headers=auth).json()
    previous = detail["exercises"][0]["previous_sets"]
    assert [(s["weight_kg"], s["reps"]) for s in previous] == [(80, 8), (85, 6), (90, 4)]

    ghost = client.get(f"{EX}/{ex}/last-performance", headers=auth).json()
    assert len(ghost["sets"]) == 3


# --------------------------------------------------------------------------
# Logging sets: points and records
# --------------------------------------------------------------------------


def test_a_set_moves_xp_live_but_shop_points_wait_for_finish(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    first = log(client, auth, session["id"], ex)

    assert first["points_awarded"] == rules.SET_POINTS
    assert first["progression"]["total_xp"] == rules.SET_POINTS
    assert progress(client, auth)["total_xp"] == rules.SET_POINTS
    assert progress(client, auth)["points_balance"] == 0  # not yet

    log(client, auth, session["id"], ex)
    log(client, auth, session["id"], ex)
    age(db, session["id"], 30)
    done = finish(client, auth, session["id"])

    assert done["points_credited"] == done["breakdown"]["total"]
    assert progress(client, auth)["points_balance"] == done["points_credited"]
    wallet = client.get("/api/v1/rewards/wallet", headers=auth).json()
    assert wallet["total_points_earned"] == done["points_credited"]


def test_the_first_ever_set_is_a_baseline_and_earns_no_pr_bonus(
    client: TestClient, auth: dict
) -> None:
    ex = exercise_id(client, auth)
    first = log(client, auth, start(client, auth)["id"], ex)
    assert first["pr_events"], "a baseline is still recorded"
    assert all(e["is_baseline"] for e in first["pr_events"])
    assert not any(e["bonus_awarded"] for e in first["pr_events"])
    assert first["points_awarded"] == rules.SET_POINTS
    # Recorded, but not badged as a PR.
    assert first["set"]["is_pr"] is False


def test_a_real_pr_is_flagged_and_paid(client: TestClient, auth: dict, db: Session) -> None:
    ex = exercise_id(client, auth)
    full_workout(client, auth, db, ex)

    session = start(client, auth)
    result = log(client, auth, session["id"], ex, weight=110, reps=5)

    paid = [e for e in result["pr_events"] if e["bonus_awarded"]]
    assert len(paid) == 1
    assert paid[0]["record_type"] == "max_weight"
    assert paid[0]["previous_value"] == 100
    assert result["set"]["is_pr"] is True
    assert result["points_awarded"] == rules.SET_POINTS + rules.PR_BONUS
    assert "pr_achieved" in [a["source_type"] for a in result["awards"]]


def test_an_exercise_earns_one_pr_bonus_per_session(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    full_workout(client, auth, db, ex)
    session = start(client, auth)
    first = log(client, auth, session["id"], ex, weight=110, reps=5)
    second = log(client, auth, session["id"], ex, weight=120, reps=5)

    assert first["points_awarded"] == rules.SET_POINTS + rules.PR_BONUS
    # Still a record - celebrated - but not paid again.
    assert second["set"]["is_pr"] is True
    assert second["points_awarded"] == rules.SET_POINTS


def test_set_points_stop_at_the_session_cap(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth, SQUAT)
    session = start(client, auth)
    total = 0
    last = None
    for _ in range(rules.SET_POINTS_CAP_PER_SESSION // rules.SET_POINTS + 5):
        # A dominated set every time after the first: no PRs muddying the sum.
        last = log(client, auth, session["id"], ex, weight=60, reps=5)
        total += last["points_awarded"]
    assert total == rules.SET_POINTS_CAP_PER_SESSION
    assert last["set_cap_reached"] is True
    assert last["points_awarded"] == 0


def test_warmups_earn_nothing_and_set_no_records(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    warmup = log(client, auth, start(client, auth)["id"], ex, weight=200, reps=1, is_warmup=True)
    assert warmup["points_awarded"] == 0
    assert warmup["pr_events"] == []
    assert client.get(f"{WK}/records", headers=auth).json() == []


def test_a_retried_submit_is_not_logged_twice(client: TestClient, auth: dict) -> None:
    """client_set_id makes a double-tap or network retry idempotent."""
    ex = exercise_id(client, auth)
    session = start(client, auth)
    token = str(uuid.uuid4())
    first = log(client, auth, session["id"], ex, client_set_id=token)
    retry = log(client, auth, session["id"], ex, client_set_id=token)

    assert retry["is_duplicate"] is True
    assert retry["set"]["id"] == first["set"]["id"]
    assert retry["points_awarded"] == 0
    assert progress(client, auth)["total_xp"] == rules.SET_POINTS
    detail = client.get(f"{WK}/sessions/{session['id']}", headers=auth).json()
    assert len(detail["exercises"][0]["sets"]) == 1


def test_a_client_supplied_point_value_is_ignored(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    result = log(client, auth, start(client, auth)["id"], ex, points=9999, xp=9999)
    assert result["points_awarded"] == rules.SET_POINTS
    assert progress(client, auth)["total_xp"] == rules.SET_POINTS


def test_pounds_are_converted_to_kilograms(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    result = log(client, auth, start(client, auth)["id"], ex, weight=225, unit="lb")
    assert result["set"]["weight_kg"] == 102.06


def test_a_cardio_set_can_be_logged_by_duration(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth, "Treadmill Run")
    result = log(
        client, auth, start(client, auth)["id"], ex, weight=0, reps=None,
        duration_seconds=1200, distance_m=3000,
    )
    assert result["set"]["duration_seconds"] == 1200
    assert result["pr_events"] == []


def test_a_set_with_no_measure_is_rejected(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    r = client.post(
        f"{WK}/sessions/{session['id']}/sets",
        json={"exercise_id": ex, "weight": 100},
        headers=auth,
    )
    assert r.status_code == 422


@pytest.mark.parametrize("weight", [1001, -5])
def test_absurd_weights_are_rejected(client: TestClient, auth: dict, weight: float) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    r = client.post(
        f"{WK}/sessions/{session['id']}/sets",
        json={"exercise_id": ex, "weight": weight, "reps": 1},
        headers=auth,
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------
# Edits, deletes, abandonment: reversals
# --------------------------------------------------------------------------


def test_deleting_a_set_reverses_its_points(
    client: TestClient, user_factory, db: Session
) -> None:
    auth, user = user_factory()
    ex = exercise_id(client, auth)
    session = start(client, auth)
    logged = log(client, auth, session["id"], ex)

    r = client.delete(f"{WK}/sessions/{session['id']}/sets/{logged['set']['id']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["points_awarded"] == -rules.SET_POINTS
    assert r.json()["session_points"] == 0
    assert progress(client, auth)["total_xp"] == 0

    ledger = client.get(f"{WK}/points/ledger", headers=auth).json()
    assert sorted(e["source_type"] for e in ledger) == ["reversal", "set_logged"]
    assert ledger_total(db, user["id"]) == 0


def test_deleting_the_record_set_restores_the_previous_record(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    full_workout(client, auth, db, ex)
    session = start(client, auth)
    heavy = log(client, auth, session["id"], ex, weight=120, reps=3)
    client.delete(f"{WK}/sessions/{session['id']}/sets/{heavy['set']['id']}", headers=auth)

    records = client.get(f"{WK}/records", params={"exercise_id": ex}, headers=auth).json()
    max_weight = [r for r in records if r["record_type"] == "max_weight"]
    assert [r["value"] for r in max_weight] == [100]


def test_deleting_a_set_renumbers_the_rest(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    sets = [log(client, auth, session["id"], ex, weight=60, reps=r) for r in (5, 6, 7)]
    client.delete(f"{WK}/sessions/{session['id']}/sets/{sets[0]['set']['id']}", headers=auth)
    detail = client.get(f"{WK}/sessions/{session['id']}", headers=auth).json()
    assert [s["set_number"] for s in detail["exercises"][0]["sets"]] == [1, 2]


def test_editing_a_set_rejudges_it(client: TestClient, user_factory, db: Session) -> None:
    """A typo fixed to a record weight earns the PR it should have earned."""
    auth, user = user_factory()
    ex = exercise_id(client, auth)
    full_workout(client, auth, db, ex)
    session = start(client, auth)
    typo = log(client, auth, session["id"], ex, weight=90, reps=5)
    assert typo["set"]["is_pr"] is False

    fixed = client.patch(
        f"{WK}/sessions/{session['id']}/sets/{typo['set']['id']}",
        json={"weight": 110},
        headers=auth,
    )
    assert fixed.status_code == 200, fixed.text
    body = fixed.json()
    assert body["set"]["weight_kg"] == 110
    assert body["set"]["is_pr"] is True
    assert body["points_awarded"] == rules.PR_BONUS  # set points reversed, then re-paid
    assert ledger_total(db, user["id"]) == progress(client, auth)["total_xp"]


def test_abandoning_reverses_every_award(
    client: TestClient, user_factory, db: Session
) -> None:
    auth, user = user_factory()
    ex = exercise_id(client, auth)
    session = start(client, auth)
    for _ in range(3):
        log(client, auth, session["id"], ex)

    r = client.post(f"{WK}/sessions/{session['id']}/abandon", headers=auth)
    assert r.status_code == 200
    assert r.json()["points_reversed"] == 3 * rules.SET_POINTS
    assert progress(client, auth)["total_xp"] == 0
    assert progress(client, auth)["points_balance"] == 0
    assert ledger_total(db, user["id"]) == 0
    # Its sets no longer count toward records.
    assert client.get(f"{WK}/records", headers=auth).json() == []
    # And a new workout can start.
    start(client, auth)


# --------------------------------------------------------------------------
# Finishing: bonuses, volume records, streaks
# --------------------------------------------------------------------------


def test_a_trivial_session_earns_no_bonus(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    log(client, auth, session["id"], ex)
    done = finish(client, auth, session["id"])

    assert done["qualified"] is False
    assert done["breakdown"]["session_bonus"] == 0
    assert done["points_credited"] == rules.SET_POINTS
    # A non-qualifying session does not advance the daily streak either.
    assert progress(client, auth)["current_streak"] == 0


def test_a_real_workout_earns_the_session_bonus_and_advances_the_streak(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    done = full_workout(client, auth, db, ex)

    assert done["qualified"] is True
    assert done["breakdown"]["session_bonus"] == pe.session_bonus(45, 3)
    assert done["progression"]["current_streak"] == 1
    assert progress(client, auth)["current_streak"] == 1


def test_volume_records_are_judged_at_finish(client: TestClient, auth: dict, db: Session) -> None:
    ex = exercise_id(client, auth)
    first = full_workout(client, auth, db, ex)
    first_volume = [e for e in first["pr_events"] if e["record_type"] == "max_volume"]
    assert first_volume and first_volume[0]["is_baseline"] is True

    second = full_workout(client, auth, db, ex, sets=((100, 5),) * 4)
    volume = [e for e in second["pr_events"] if e["record_type"] == "max_volume"]
    assert volume[0]["previous_value"] == 1500
    assert volume[0]["value"] == 2000
    # Recorded, never paid: one more set would otherwise be a PR every time.
    assert volume[0]["bonus_awarded"] is False


def test_the_weekly_streak_bonus_is_paid_once_on_hitting_target(
    client: TestClient, auth: dict, db: Session
) -> None:
    ex = exercise_id(client, auth)
    results = [full_workout(client, auth, db, ex) for _ in range(rules.STREAK_SESSIONS_PER_WEEK + 1)]

    streak_awards = [
        [a for a in r["awards"] if a["source_type"] == "streak_bonus"] for r in results
    ]
    assert [len(a) for a in streak_awards] == [0] * (rules.STREAK_SESSIONS_PER_WEEK - 1) + [1, 0]
    assert streak_awards[rules.STREAK_SESSIONS_PER_WEEK - 1][0]["points"] == pe.streak_bonus(1)
    assert results[-1]["streak"]["weeks"] == 1
    assert results[-1]["streak"]["this_week_done"] is True


def test_the_ledger_always_equals_the_xp_it_produced(
    client: TestClient, user_factory, db: Session
) -> None:
    """Every path - log, edit, delete, finish - keeps SUM(ledger) == total_xp."""
    auth, user = user_factory()
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    full_workout(client, auth, db, bench)

    session = start(client, auth)
    a = log(client, auth, session["id"], bench, weight=110, reps=5)
    log(client, auth, session["id"], squat, weight=140, reps=5)
    b = log(client, auth, session["id"], squat, weight=150, reps=3)
    client.patch(f"{WK}/sessions/{session['id']}/sets/{a['set']['id']}", json={"reps": 6}, headers=auth)
    client.delete(f"{WK}/sessions/{session['id']}/sets/{b['set']['id']}", headers=auth)
    age(db, session["id"], 40)
    finish(client, auth, session["id"])

    assert ledger_total(db, user["id"]) == progress(client, auth)["total_xp"]
    summary = client.get(f"{WK}/points", headers=auth).json()
    assert summary["total_points"] == progress(client, auth)["total_xp"]
    assert summary["sessions_completed"] == 2


def test_history_lists_sessions_newest_first(client: TestClient, auth: dict, db: Session) -> None:
    ex = exercise_id(client, auth)
    first = full_workout(client, auth, db, ex)
    second = full_workout(client, auth, db, ex, sets=((105, 5),) * 3)

    history = client.get(f"{WK}/sessions", headers=auth).json()
    assert [h["id"] for h in history] == [second["session"]["id"], first["session"]["id"]]
    assert history[0]["working_sets"] == 3
    assert history[0]["pr_count"] >= 1
    assert history[0]["points_total"] == second["breakdown"]["total"]

    completed = client.get(f"{WK}/sessions", params={"status": "completed", "limit": 1}, headers=auth).json()
    assert len(completed) == 1
