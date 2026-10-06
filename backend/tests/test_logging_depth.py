"""Overhaul phase 1, logging: exercise cards in a session, set types, the
previous column, and the finish summary's totals and muscle map."""

import datetime as dt
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import analytics
from app.core import workout_rules as rules
from app.models.workout import SessionExercise, SetEntry, WorkoutSession
from tests.test_workouts import BENCH, SQUAT, WK, age, exercise_id, finish, ledger_total, log, progress, start


def cards(session: dict) -> list[dict]:
    return session["exercises"]


def add(client: TestClient, auth: dict, session_id: str, ex: str, **extra) -> dict:
    r = client.post(f"{WK}/sessions/{session_id}/exercises", json={"exercise_id": ex, **extra}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_an_added_exercise_is_a_card_before_any_set(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    got = add(client, auth, session["id"], exercise_id(client, auth, BENCH), notes="Pause reps")
    assert [c["exercise"]["name"] for c in cards(got)] == [BENCH]
    card = cards(got)[0]
    assert card["sets"] == [] and card["notes"] == "Pause reps"
    assert card["rest_seconds"] == 90  # the user's default
    # And it survives a reload - no client-side copy needed.
    again = client.get(f"{WK}/sessions/{session['id']}", headers=auth).json()
    assert cards(again)[0]["session_exercise_id"] == card["session_exercise_id"]


def test_sets_go_on_the_named_card_and_number_within_it(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    bench = exercise_id(client, auth, BENCH)
    first = cards(add(client, auth, session["id"], bench))[0]["session_exercise_id"]
    # The same exercise again, as a back-off block.
    second = cards(add(client, auth, session["id"], bench))[1]["session_exercise_id"]
    log(client, auth, session["id"], bench, session_exercise_id=first)
    log(client, auth, session["id"], bench, session_exercise_id=first)
    backoff = log(client, auth, session["id"], bench, weight=60, session_exercise_id=second)
    assert backoff["set"]["session_exercise_id"] == second
    assert backoff["set"]["set_number"] == 1


def test_a_set_without_a_card_makes_one(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    logged = log(client, auth, session["id"], exercise_id(client, auth, SQUAT))
    got = client.get(f"{WK}/sessions/{session['id']}", headers=auth).json()
    assert cards(got)[0]["session_exercise_id"] == logged["set"]["session_exercise_id"]


def test_a_card_from_another_workout_is_refused(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    bench = exercise_id(client, auth, BENCH)
    r = client.post(f"{WK}/sessions/{session['id']}/sets", headers=auth,
                    json={"exercise_id": bench, "weight": 50, "reps": 5,
                          "session_exercise_id": str(uuid.uuid4())})
    assert r.status_code == 404


def test_set_types_drop_and_failure_are_working_sets(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    bench = exercise_id(client, auth, BENCH)
    warm = log(client, auth, session["id"], bench, weight=40, set_type="warmup")
    drop = log(client, auth, session["id"], bench, weight=60, set_type="drop")
    fail = log(client, auth, session["id"], bench, weight=50, set_type="failure")
    assert (warm["set"]["set_type"], warm["set"]["is_warmup"], warm["points_awarded"]) == ("warmup", True, 0)
    assert drop["set"]["is_warmup"] is False and drop["points_awarded"] >= rules.SET_POINTS
    assert fail["set"]["set_type"] == "failure"
    # The old flag still works, and maps onto a type.
    legacy = log(client, auth, session["id"], bench, weight=40, is_warmup=True)
    assert legacy["set"]["set_type"] == "warmup"


def test_editing_the_type_keeps_the_flag_in_step(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    entry = log(client, auth, session["id"], exercise_id(client, auth, BENCH), weight=40)
    r = client.patch(f"{WK}/sessions/{session['id']}/sets/{entry['set']['id']}",
                     json={"set_type": "warmup"}, headers=auth)
    assert (r.json()["set"]["set_type"], r.json()["set"]["is_warmup"]) == ("warmup", True)
    r = client.patch(f"{WK}/sessions/{session['id']}/sets/{entry['set']['id']}",
                     json={"is_warmup": False}, headers=auth)
    assert (r.json()["set"]["set_type"], r.json()["set"]["is_warmup"]) == ("normal", False)


def test_cards_can_be_reordered_and_superset(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    add(client, auth, session["id"], exercise_id(client, auth, BENCH))
    got = add(client, auth, session["id"], exercise_id(client, auth, SQUAT))
    a, b = (c["session_exercise_id"] for c in cards(got))
    r = client.post(f"{WK}/sessions/{session['id']}/exercises/reorder", json={"order": [b, a]}, headers=auth)
    assert [c["exercise"]["name"] for c in cards(r.json())] == [SQUAT, BENCH]
    for card in (a, b):
        client.patch(f"{WK}/sessions/{session['id']}/exercises/{card}", json={"superset_group": 1}, headers=auth)
    got = client.get(f"{WK}/sessions/{session['id']}", headers=auth).json()
    assert {c["superset_group"] for c in cards(got)} == {1}
    # Every card, once.
    bad = client.post(f"{WK}/sessions/{session['id']}/exercises/reorder", json={"order": [a]}, headers=auth)
    assert bad.status_code == 422


def test_an_unlogged_card_can_be_replaced_a_logged_one_cannot(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    card = cards(add(client, auth, session["id"], bench))[0]["session_exercise_id"]
    r = client.patch(f"{WK}/sessions/{session['id']}/exercises/{card}", json={"exercise_id": squat}, headers=auth)
    assert cards(r.json())[0]["exercise"]["name"] == SQUAT
    log(client, auth, session["id"], squat, session_exercise_id=card)
    r = client.patch(f"{WK}/sessions/{session['id']}/exercises/{card}", json={"exercise_id": bench}, headers=auth)
    assert r.status_code == 409


def test_removing_a_card_with_sets_needs_force_and_reverses_everything(
    client: TestClient, user_factory, db: Session
) -> None:
    auth, user = user_factory()
    session = start(client, auth)
    bench = exercise_id(client, auth, BENCH)
    card = cards(add(client, auth, session["id"], bench))[0]["session_exercise_id"]
    for _ in range(3):
        log(client, auth, session["id"], bench, session_exercise_id=card)
    url = f"{WK}/sessions/{session['id']}/exercises/{card}"
    assert client.delete(url, headers=auth).status_code == 409
    r = client.delete(url, params={"force": True}, headers=auth)
    assert r.status_code == 200 and cards(r.json()) == []
    assert ledger_total(db, user["id"]) == progress(client, auth)["total_xp"] == 0
    assert client.get(f"{WK}/records", headers=auth).json() == []


def test_the_previous_column_is_last_times_sets_by_number(client: TestClient, auth: dict, db: Session) -> None:
    bench = exercise_id(client, auth, BENCH)
    first = start(client, auth)
    log(client, auth, first["id"], bench, weight=80, reps=8)
    log(client, auth, first["id"], bench, weight=82.5, reps=6)
    age(db, first["id"], 30)
    finish(client, auth, first["id"])
    second = start(client, auth)
    got = client.get(f"{WK}/sessions/{second['id']}/previous", params={"exercise_id": bench}, headers=auth).json()
    assert [(s["set_number"], s["weight_kg"], s["reps"]) for s in got["sets"]] == [(1, 80, 8), (2, 82.5, 6)]
    never = client.get(f"{WK}/sessions/{second['id']}/previous",
                       params={"exercise_id": exercise_id(client, auth, SQUAT)}, headers=auth).json()
    assert never["sets"] == [] and never["session_id"] is None


def test_finish_writes_totals_and_the_muscle_map(client: TestClient, auth: dict, db: Session) -> None:
    session = start(client, auth)
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    for _ in range(3):
        log(client, auth, session["id"], bench, weight=60, reps=10)
    log(client, auth, session["id"], squat, weight=100, reps=5)
    log(client, auth, session["id"], squat, weight=40, reps=5, set_type="warmup")
    age(db, session["id"], 40)
    done = finish(client, auth, session["id"])
    row = db.get(WorkoutSession, uuid.UUID(session["id"]))
    db.refresh(row)
    assert float(row.total_volume_kg) == 3 * 600 + 500
    assert row.total_working_sets == 4
    assert row.duration_seconds >= 40 * 60
    assert done["muscles_worked"]["chest"] == 1.0  # three bench sets: the most worked
    assert 0 < done["muscles_worked"]["quads"] < 1
    assert done["rank_change"] is None or set(done["rank_change"]) == {"from", "to"}


def test_a_routine_start_lays_out_its_cards(client: TestClient, auth: dict) -> None:
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    routine = client.post("/api/v1/routines", json={"name": "Upper", "exercises": [
        {"exercise_id": bench, "target_sets": 3, "target_reps_low": 6, "target_reps_high": 8,
         "rest_seconds": 150, "superset_group": 1, "notes": "Touch and go"},
        {"exercise_id": squat, "target_sets": 3, "target_reps": 5, "superset_group": 1},
    ]}, headers=auth).json()
    assert routine["exercises"][0]["target_reps"] == 8  # the top of the range
    session = start(client, auth, routine_id=routine["id"])
    laid = cards(session)
    assert [c["exercise"]["name"] for c in laid] == [BENCH, SQUAT]
    assert (laid[0]["rest_seconds"], laid[0]["superset_group"], laid[0]["notes"]) == (150, 1, "Touch and go")


def test_muscle_intensity_is_relative_to_the_most_worked() -> None:
    got = analytics.muscle_intensity([
        (["chest"], ["triceps", "shoulders"]),
        (["chest"], ["triceps"]),
        (["quads"], ["glutes"]),
        (["cardio"], []),
    ])
    assert got == {"chest": 1.0, "glutes": 0.25, "quads": 0.5, "shoulders": 0.25, "triceps": 0.5}
    assert analytics.muscle_intensity([]) == {}
