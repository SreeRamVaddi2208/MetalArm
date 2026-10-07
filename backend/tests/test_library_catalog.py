"""The Library tab over HTTP: what it leads with for each training path,
filters, starting and saving a workout, and following a program through to
its end - without a point changing hands differently."""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.library import LibraryProgram, ProgramEnrollment
from app.models.workout import WorkoutSession

A = "/api/v1"
LIB = f"{A}/library"
ME = f"{A}/auth/me"


def _path(client: TestClient, auth: dict, path: str) -> None:
    r = client.patch(ME, json={"character_class": path}, headers=auth)
    assert r.status_code == 200, r.text


def _start(client: TestClient, auth: dict, slug: str) -> dict:
    r = client.post(f"{LIB}/workouts/{slug}/start", headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def _finish_with_a_set(client: TestClient, auth: dict, session: dict, db: Session) -> dict:
    card = session["exercises"][0]
    logged = client.post(f"{A}/workouts/sessions/{session['id']}/sets", headers=auth, json={
        "exercise_id": card["exercise"]["id"], "session_exercise_id": card["session_exercise_id"],
        "weight": 20, "reps": card["target"]["target_reps_low"] or 5,
    })
    assert logged.status_code == 201, logged.text
    # Old enough to be a real workout, without sleeping.
    db.execute(update(WorkoutSession).where(WorkoutSession.id == uuid.UUID(session["id"]))
               .values(started_at=WorkoutSession.started_at - dt.timedelta(minutes=40)))
    db.flush()
    r = client.post(f"{A}/workouts/sessions/{session['id']}/finish", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# What the Library leads with
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["athlete", "bodybuilder", "powerlifter"])
def test_home_leads_with_the_users_path(client: TestClient, auth: dict, path: str) -> None:
    _path(client, auth, path)
    home = client.get(f"{LIB}/home", headers=auth).json()
    assert home["path"] == path and home["needs_path"] is False
    assert len(home["recommended_programs"]) == 3 and len(home["recommended_workouts"]) == 4
    for item in home["recommended_programs"] + home["recommended_workouts"]:
        assert item["category"] == path and item["recommended"] is True
    # Server order: easiest first, then the smallest commitment.
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    programs = home["recommended_programs"]
    assert [p["sort"] for p in programs] == sorted(p["sort"] for p in programs)
    keys = [(order[p["difficulty"]], p["days_per_week"]) for p in programs]
    assert keys == sorted(keys)
    assert sorted(o["category"] for o in home["other_paths"]) == sorted(
        {"athlete", "bodybuilder", "powerlifter"} - {path})
    assert all(o["programs"] == 3 and o["workouts"] == 4 for o in home["other_paths"])


def test_home_without_a_path_asks_for_one_and_hides_nothing(client: TestClient, auth: dict) -> None:
    home = client.get(f"{LIB}/home", headers=auth).json()
    assert home["path"] == "" and home["needs_path"] is True
    assert home["recommended_programs"] == [] and home["recommended_workouts"] == []
    assert sorted(o["category"] for o in home["other_paths"]) == ["athlete", "bodybuilder", "powerlifter"]


def test_changing_path_changes_the_next_load(client: TestClient, auth: dict) -> None:
    _path(client, auth, "athlete")
    assert {p["category"] for p in client.get(f"{LIB}/home", headers=auth).json()["recommended_programs"]} == {"athlete"}
    _path(client, auth, "powerlifter")
    assert {p["category"] for p in client.get(f"{LIB}/home", headers=auth).json()["recommended_programs"]} == {
        "powerlifter"}


def test_lists_put_the_users_path_first(client: TestClient, auth: dict) -> None:
    _path(client, auth, "bodybuilder")
    programs = client.get(f"{LIB}/programs", headers=auth).json()
    assert len(programs) == 9
    assert [p["recommended"] for p in programs] == [True] * 3 + [False] * 6
    assert [p["sort"] for p in programs] == list(range(9))


def test_filters(client: TestClient, auth: dict) -> None:
    get = lambda kind, **q: client.get(f"{LIB}/{kind}", params=q, headers=auth).json()  # noqa: E731
    assert {p["category"] for p in get("programs", category="powerlifter")} == {"powerlifter"}
    assert all(p["difficulty"] == "beginner" for p in get("programs", difficulty="beginner"))
    assert all(p["days_per_week"] == 4 for p in get("programs", days_per_week=4))
    short = get("workouts", max_minutes=30)
    assert short and all(w["duration_minutes"] <= 30 for w in short)
    bodyweight = get("workouts", equipment=["bodyweight", "band"])
    assert bodyweight and all(set(w["equipment"]) <= {"bodyweight", "band"} for w in bodyweight)
    assert get("workouts", category="athlete", difficulty="advanced") == []


def test_unknown_and_hidden_items_are_404(client: TestClient, auth: dict) -> None:
    assert client.get(f"{LIB}/workouts/no-such-workout", headers=auth).status_code == 404
    assert client.get(f"{LIB}/programs/no-such-program", headers=auth).status_code == 404
    # The legacy entries are kept for the old endpoints only.
    assert client.get(f"{LIB}/programs/barbell-foundations", headers=auth).status_code == 404
    assert client.get(f"{LIB}/workouts/powerlifting-heavy-day", headers=auth).status_code == 404


def test_detail_shows_targets_and_the_schedule(client: TestClient, auth: dict) -> None:
    workout = client.get(f"{LIB}/workouts/chest-and-triceps", headers=auth).json()
    first = workout["exercises"][0]
    assert first["exercise"]["slug"] == "incline-barbell-bench-press"
    assert (first["target_sets"], first["rep_low"], first["rep_high"], first["rest_seconds"]) == (4, 8, 10, 120)
    assert "weight" not in str(first.keys())
    program = client.get(f"{LIB}/programs/linear-strength-base", headers=auth).json()
    assert len(program["schedule"]) == 8 and all(len(w["days"]) == 7 for w in program["schedule"])
    week_one = [d["workout_slug"] for d in program["schedule"][0]["days"]]
    assert week_one == ["linear-a", None, "linear-b", None, "linear-a", None, None]
    assert [w["slug"] for w in program["workouts"]] == ["linear-a", "linear-b"]
    assert program["enrollment"] is None
    # A program day opens as a workout too.
    assert client.get(f"{LIB}/workouts/linear-a", headers=auth).status_code == 200


# ---------------------------------------------------------------------------
# Start and save
# ---------------------------------------------------------------------------


def test_start_preloads_the_workout_with_its_targets(client: TestClient, auth: dict, db: Session) -> None:
    detail = client.get(f"{LIB}/workouts/back-and-biceps", headers=auth).json()
    session = _start(client, auth, "back-and-biceps")
    assert [c["exercise"]["slug"] for c in session["exercises"]] == [e["exercise"]["slug"] for e in detail["exercises"]]
    target = session["exercises"][0]["target"]
    assert (target["target_sets"], target["target_reps_low"], target["target_reps_high"]) == (4, 8, 12)
    assert target["target_weight_kg"] is None
    assert session["name"] == "Back and biceps"
    assert session["library_workout_id"] is not None and session["program_enrollment_id"] is None
    # One live workout at a time.
    assert client.post(f"{LIB}/workouts/squat-day/start", headers=auth).status_code == 409


def test_a_session_from_the_library_rehydrates_with_its_targets(client: TestClient, auth: dict) -> None:
    session = _start(client, auth, "legs-and-glutes")
    active = client.get(f"{A}/workouts/sessions/active", headers=auth).json()["session"]
    assert active["id"] == session["id"]
    assert active["exercises"][0]["target"]["target_reps_high"] == 10


def test_save_to_routines_is_faithful_and_once(client: TestClient, auth: dict) -> None:
    saved = client.post(f"{LIB}/workouts/shoulders-and-arms/save-to-routines", headers=auth)
    assert saved.status_code == 201, saved.text
    routine = saved.json()
    detail = client.get(f"{LIB}/workouts/shoulders-and-arms", headers=auth).json()
    assert detail["routine_id"] == routine["id"]
    assert [(s["exercise"]["slug"], s["target_sets"], s["target_reps_low"], s["target_reps_high"], s["rest_seconds"])
            for s in routine["exercises"]] == [
        (e["exercise"]["slug"], e["target_sets"], e["rep_low"], e["rep_high"], e["rest_seconds"])
        for e in detail["exercises"]]
    supersets = [s["superset_group"] for s in routine["exercises"]]
    assert supersets[-2:] == [1, 1] and supersets[0] is None
    again = client.post(f"{LIB}/workouts/shoulders-and-arms/save-to-routines", headers=auth)
    assert again.status_code == 200 and again.json()["id"] == routine["id"]


# ---------------------------------------------------------------------------
# Following a program
# ---------------------------------------------------------------------------


def test_follow_pause_and_resume(client: TestClient, auth: dict) -> None:
    followed = client.post(f"{LIB}/programs/upper-lower-8wk/follow", headers=auth).json()
    assert followed["status"] == "active" and followed["next_workout"]["slug"] == "upper-a"
    home = client.get(f"{LIB}/home", headers=auth).json()
    assert home["your_program"]["program"]["slug"] == "upper-lower-8wk"
    assert home["your_program"]["program"]["following"] is True
    paused = client.delete(f"{LIB}/programs/upper-lower-8wk/follow", headers=auth).json()
    assert paused["status"] == "paused"
    assert client.get(f"{LIB}/home", headers=auth).json()["your_program"] is None
    again = client.post(f"{LIB}/programs/upper-lower-8wk/follow", headers=auth).json()
    assert again["status"] == "active" and again["id"] == followed["id"]
    assert client.delete(f"{LIB}/programs/meet-prep-peak/follow", headers=auth).status_code == 404


def test_following_another_program_pauses_the_first(client: TestClient, auth: dict) -> None:
    first = client.post(f"{LIB}/programs/linear-strength-base/follow", headers=auth).json()
    client.post(f"{LIB}/programs/five-day-split/follow", headers=auth)
    detail = client.get(f"{LIB}/programs/linear-strength-base", headers=auth).json()
    assert detail["enrollment"]["id"] == first["id"] and detail["enrollment"]["status"] == "paused"
    assert client.get(f"{LIB}/home", headers=auth).json()["your_program"]["program"]["slug"] == "five-day-split"


def test_finishing_the_next_workout_moves_the_program_on(client: TestClient, auth: dict, db: Session) -> None:
    client.post(f"{LIB}/programs/linear-strength-base/follow", headers=auth)
    session = _start(client, auth, "linear-a")
    assert session["program_enrollment_id"] is not None
    _finish_with_a_set(client, auth, session, db)
    enrollment = client.get(f"{LIB}/programs/linear-strength-base", headers=auth).json()["enrollment"]
    # Day 1 done; day 2 is rest, so the next is day 3, Strength B.
    assert (enrollment["current_week"], enrollment["current_day"]) == (1, 3)
    assert enrollment["next_workout"]["slug"] == "linear-b"


def test_a_different_workout_or_an_abandoned_one_does_not_move_it(client: TestClient, auth: dict, db: Session) -> None:
    client.post(f"{LIB}/programs/linear-strength-base/follow", headers=auth)
    other = _start(client, auth, "squat-day")
    assert other["program_enrollment_id"] is None
    _finish_with_a_set(client, auth, other, db)
    right = _start(client, auth, "linear-a")
    client.post(f"{A}/workouts/sessions/{right['id']}/abandon", headers=auth)
    enrollment = client.get(f"{LIB}/programs/linear-strength-base", headers=auth).json()["enrollment"]
    assert (enrollment["current_week"], enrollment["current_day"]) == (1, 1)


def test_the_last_workout_completes_the_program(client: TestClient, auth: dict, db: Session) -> None:
    followed = client.post(f"{LIB}/programs/linear-strength-base/follow", headers=auth).json()
    # Jump to the last training day: week 8, day 5.
    db.execute(update(ProgramEnrollment).where(ProgramEnrollment.id == uuid.UUID(followed["id"]))
               .values(current_week=8, current_day=5))
    db.flush()
    nxt = client.get(f"{LIB}/programs/linear-strength-base", headers=auth).json()["enrollment"]["next_workout"]
    session = _start(client, auth, nxt["slug"])
    _finish_with_a_set(client, auth, session, db)
    enrollment = client.get(f"{LIB}/programs/linear-strength-base", headers=auth).json()["enrollment"]
    assert enrollment["status"] == "completed" and enrollment["next_workout"] is None
    # Following it again starts over.
    again = client.post(f"{LIB}/programs/linear-strength-base/follow", headers=auth).json()
    assert (again["status"], again["current_week"], again["current_day"]) == ("active", 1, 1)


def test_a_program_day_earns_what_any_session_earns(client: TestClient, user_factory, db: Session) -> None:
    """Same workout, same set, same duration: one user following the program,
    one not. The finish pays the same."""
    paid = []
    for following in (True, False):
        headers, _ = user_factory()
        if following:
            client.post(f"{LIB}/programs/linear-strength-base/follow", headers=headers)
        session = _start(client, headers, "linear-a")
        assert (session["program_enrollment_id"] is not None) is following
        result = _finish_with_a_set(client, headers, session, db)
        paid.append((result["points_credited"], [a["points"] for a in result["awards"]],
                     result["progression"]["xp_gained"] if "xp_gained" in result["progression"] else None))
    assert paid[0] == paid[1]
