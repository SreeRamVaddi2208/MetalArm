"""Overhaul phase 1, Library: programs, favourites, the library listing, and
suggested workouts."""

import datetime as dt
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import suggestions
from app.core import workout_rules as rules
from tests.test_workouts import BENCH, SQUAT, age, exercise_id, finish, log, start

NOW = dt.datetime(2026, 10, 6, 12, tzinfo=dt.timezone.utc)


def routine(client: TestClient, auth: dict, name: str, **extra) -> dict:
    ex = exercise_id(client, auth, BENCH)
    r = client.post("/api/v1/routines", json={"name": name, "exercises": [{"exercise_id": ex}], **extra},
                    headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_programs_hold_routines_in_order(client: TestClient, auth: dict) -> None:
    program = client.post("/api/v1/programs", json={"name": "Upper/Lower", "weeks": 8,
                                                     "sessions_per_week": 4, "level": "intermediate"},
                          headers=auth).json()
    routine(client, auth, "Lower A", program_id=program["id"], order_in_program=1)
    routine(client, auth, "Upper A", program_id=program["id"], order_in_program=0)
    got = client.get(f"/api/v1/programs/{program['id']}", headers=auth).json()
    assert [r["name"] for r in got["routines"]] == ["Upper A", "Lower A"]
    assert got["routines"][0]["exercise_count"] == 1


def test_someone_elses_program_cannot_be_used(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    program = client.post("/api/v1/programs", json={"name": "Mine"}, headers=mine).json()
    assert client.get(f"/api/v1/programs/{program['id']}", headers=theirs).status_code == 404
    r = client.post("/api/v1/routines", json={"name": "X", "program_id": program["id"]}, headers=theirs)
    assert r.status_code == 404


def test_deleting_a_program_keeps_its_routines(client: TestClient, auth: dict) -> None:
    program = client.post("/api/v1/programs", json={"name": "Short-lived"}, headers=auth).json()
    kept = routine(client, auth, "Push", program_id=program["id"])
    assert client.delete(f"/api/v1/programs/{program['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/routines/{kept['id']}", headers=auth).json()["program_id"] is None


def test_favourites_toggle_and_show_in_the_library(client: TestClient, auth: dict) -> None:
    r = routine(client, auth, "Arms")
    assert client.post("/api/v1/favorites", json={"target_type": "routine", "target_id": r["id"]},
                       headers=auth).status_code == 204
    # Twice is fine.
    assert client.post("/api/v1/favorites", json={"target_type": "routine", "target_id": r["id"]},
                       headers=auth).status_code == 204
    page = client.get("/api/v1/library", params={"filter": "favorites"}, headers=auth).json()
    assert [i["title"] for i in page["items"]] == ["Arms"] and page["favorite_count"] == 1
    client.delete(f"/api/v1/favorites/routine/{r['id']}", headers=auth)
    assert client.get("/api/v1/library", params={"filter": "favorites"}, headers=auth).json()["items"] == []


def test_favouriting_something_you_cannot_see_is_404(client: TestClient, auth: dict) -> None:
    r = client.post("/api/v1/favorites", json={"target_type": "routine", "target_id": str(uuid.uuid4())},
                    headers=auth)
    assert r.status_code == 404


def test_the_library_lists_sorts_and_pages(client: TestClient, auth: dict) -> None:
    for name in ("Cardio", "Arms", "Back"):
        routine(client, auth, name)
    by_name = client.get("/api/v1/library", params={"filter": "routines", "sort": "name"}, headers=auth).json()
    assert [i["title"] for i in by_name["items"]] == ["Arms", "Back", "Cardio"]
    first = client.get("/api/v1/library", params={"filter": "routines", "sort": "name", "limit": 2},
                       headers=auth).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = client.get("/api/v1/library", params={"filter": "routines", "sort": "name", "limit": 2,
                                                 "cursor": first["next_cursor"]}, headers=auth).json()
    assert [i["title"] for i in rest["items"]] == ["Cardio"] and rest["next_cursor"] is None
    assert client.get("/api/v1/library", params={"cursor": "nonsense"}, headers=auth).status_code == 422


def test_the_library_lists_logged_exercises(client: TestClient, auth: dict) -> None:
    session = start(client, auth)
    log(client, auth, session["id"], exercise_id(client, auth, SQUAT))
    items = client.get("/api/v1/library", params={"filter": "exercises"}, headers=auth).json()["items"]
    assert [i["title"] for i in items] == [SQUAT]
    assert items[0]["subtitle"].startswith("Quads")


def test_suggestions_put_the_stalest_routine_first(client: TestClient, auth: dict, db: Session) -> None:
    done = routine(client, auth, "Done today")
    routine(client, auth, "Never done")
    session = start(client, auth, routine_id=done["id"])
    for _ in range(3):
        log(client, auth, session["id"], exercise_id(client, auth, BENCH))
    age(db, session["id"], 30)
    finish(client, auth, session["id"])
    got = client.get("/api/v1/workouts/suggested", headers=auth).json()
    assert [s["name"] for s in got] == ["Never done", "Done today"]
    assert got[1]["days_since"] == 0 and got[0]["days_since"] is None
    assert got[0]["abbreviation"] == "Ne"


def test_ranking_weighs_staleness_then_path() -> None:
    old = NOW - dt.timedelta(days=5)
    fresh = NOW - dt.timedelta(days=1)
    ranked = suggestions.rank([
        suggestions.Candidate(uuid.uuid4(), "Old, other path", old, "athlete"),
        suggestions.Candidate(uuid.uuid4(), "Fresher, my path", fresh, "powerlifter"),
        suggestions.Candidate(uuid.uuid4(), "Never", None, None),
    ], path="powerlifter", now=NOW)
    assert [r.candidate.name for r in ranked] == ["Never", "Old, other path", "Fresher, my path"]
    # Within the bonus, the path wins.
    close = suggestions.rank([
        suggestions.Candidate(uuid.uuid4(), "A", NOW - dt.timedelta(days=3), None),
        suggestions.Candidate(uuid.uuid4(), "B", NOW - dt.timedelta(days=1), "powerlifter"),
    ], path="powerlifter", now=NOW)
    assert close[0].candidate.name == "B" and close[0].score == 1 + rules.SUGGEST_CATEGORY_BONUS_DAYS


def test_abbreviations() -> None:
    assert suggestions.abbreviation("Lower A") == "Lo"
    assert suggestions.abbreviation("5x5 day") == "5x"
    assert suggestions.abbreviation("!") == "?"


def test_a_finished_workout_saves_as_a_routine(client: TestClient, auth: dict) -> None:
    bench, squat = exercise_id(client, auth, BENCH), exercise_id(client, auth, SQUAT)
    s = start(client, auth, name="Monday")
    log(client, auth, s["id"], squat, 60, 8, is_warmup=True)
    log(client, auth, s["id"], squat, 120, 5)
    log(client, auth, s["id"], squat, 125, 3)
    log(client, auth, s["id"], bench, 80, 8)
    # Not yet: only a finished workout is a template.
    assert client.post(f"/api/v1/routines/from-session/{s['id']}", json={},
                       headers=auth).status_code == 409
    finish(client, auth, s["id"])
    r = client.post(f"/api/v1/routines/from-session/{s['id']}", json={}, headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Monday"
    slots = [(x["exercise"]["id"], x["target_sets"], x["target_reps"]) for x in body["exercises"]]
    # Warm-ups are not targets; the top working set is.
    assert slots == [(squat, 2, 3), (bench, 1, 8)]


def test_someone_elses_workout_cannot_be_saved(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    s = start(client, mine)
    assert client.post(f"/api/v1/routines/from-session/{s['id']}", json={},
                       headers=theirs).status_code == 404
