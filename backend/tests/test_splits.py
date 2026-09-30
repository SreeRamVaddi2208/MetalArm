"""Split-aware stretches: matching, inheritance, the panel, and the library."""

import datetime as dt
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import library, splits
from app.models.split import StretchPhase
from app.models.workout import Exercise, RecommendedStretch, Routine, WorkoutSession
from app.models.workout_enums import SessionStatus

SPLITS = "/api/v1/splits"
STRETCHES = "/api/v1/stretches"
SESSIONS = "/api/v1/workouts/sessions"
ROUTINES = "/api/v1/routines"


# --- The matcher, which is pure ------------------------------------------


def test_overlap_is_the_whole_rule() -> None:
    assert splits.matches(["chest", "triceps"], ["chest", "shoulders", "triceps"])
    assert not splits.matches(["hamstrings"], ["chest", "shoulders", "triceps"])


def test_full_body_suits_any_day() -> None:
    """A world's-greatest-stretch is not wasted on a push day, and tagging it
    with every group individually would misdescribe what it works."""
    assert splits.matches(["full_body"], ["chest"])
    assert splits.matches(["full_body"], ["quads"])


def test_a_phase_is_respected_as_well_as_the_groups() -> None:
    entries = [
        ("warm", ["chest"], "pre"),
        ("cool", ["chest"], "post"),
        ("legs", ["quads"], "pre"),
    ]
    assert splits.for_split(entries, ["chest"], StretchPhase.PRE) == ["warm"]
    assert splits.for_split(entries, ["chest"], StretchPhase.POST) == ["cool"]


def test_an_unknown_split_is_simply_not_one() -> None:
    assert splits.known("push")
    assert not splits.known("legday")
    assert not splits.known(None)


# --- The shipped definitions ---------------------------------------------


def test_every_split_is_offered(client: TestClient, auth: dict) -> None:
    rows = client.get(SPLITS, headers=auth).json()
    assert {row["split_type"] for row in rows} == {"push", "pull", "legs", "custom"}


def test_a_custom_day_still_gets_suggestions(client: TestClient, auth: dict) -> None:
    """The alternative was showing nothing, which makes the panel pointless for
    anyone not training a textbook split."""
    rows = client.get(STRETCHES, params={"split_type": "custom", "phase": "pre"}, headers=auth).json()
    assert rows, "a custom day should still warm up"


def test_a_push_day_never_offers_leg_work(client: TestClient, auth: dict) -> None:
    rows = client.get(STRETCHES, params={"split_type": "push", "phase": "post"}, headers=auth).json()
    assert rows
    for row in rows:
        groups = set(row["primary_muscle_groups"])
        assert groups & {"chest", "shoulders", "triceps"} or "full_body" in groups, row["name"]
        assert "hamstrings" not in groups or "full_body" in groups, row["name"]


def test_a_legs_day_never_offers_chest_work(client: TestClient, auth: dict) -> None:
    rows = client.get(STRETCHES, params={"split_type": "legs", "phase": "post"}, headers=auth).json()
    assert rows
    assert not any(
        "chest" in row["primary_muscle_groups"] and "full_body" not in row["primary_muscle_groups"]
        for row in rows
    )


def test_every_stretch_says_how_long_to_hold_it(client: TestClient, auth: dict) -> None:
    rows = client.get(STRETCHES, headers=auth).json()
    assert len(rows) >= 20
    for row in rows:
        assert row["hold_seconds"], row["name"]
        assert row["instructions"], row["name"]


def test_stretches_need_a_signed_in_user(client: TestClient) -> None:
    assert client.get(STRETCHES).status_code == 401
    assert client.get(SPLITS).status_code == 401


# --- The panel ------------------------------------------------------------


def test_answering_the_picker_fills_the_panel(client: TestClient, auth: dict) -> None:
    session = client.post(SESSIONS, json={}, headers=auth).json()
    assert session["split_type"] is None, "a blank start has nothing to inherit"

    panel = client.post(f"{SESSIONS}/{session['id']}/split", json={"split_type": "push"}, headers=auth)
    assert panel.status_code == 200, panel.text
    body = panel.json()
    assert body["split_type"] == "push"
    assert body["pre"] and body["post"]
    assert all(entry["source"] == "auto_matched" for entry in body["pre"])


def test_the_panel_survives_a_reload(client: TestClient, auth: dict) -> None:
    """It is rebuilt from the server, not from whatever the client remembered."""
    session = client.post(SESSIONS, json={}, headers=auth).json()
    client.post(f"{SESSIONS}/{session['id']}/split", json={"split_type": "pull"}, headers=auth)
    again = client.get(f"{SESSIONS}/{session['id']}/recommended-stretches", headers=auth).json()
    assert again["split_type"] == "pull"
    assert again["pre"]


def test_your_own_pick_is_never_matched_away(client: TestClient, auth: dict, db: Session) -> None:
    """The reason source is recorded at all: re-matching only writes
    auto_matched rows, so a user's choice stays."""
    session = client.post(SESSIONS, json={}, headers=auth).json()
    client.post(f"{SESSIONS}/{session['id']}/split", json={"split_type": "push"}, headers=auth)

    # Something a push day would never suggest.
    hamstring = db.scalar(
        select(Exercise).where(Exercise.stretch_phase.is_not(None))
        .where(Exercise.primary_muscle_groups.any("hamstrings"))
    )
    added = client.post(
        f"{SESSIONS}/{session['id']}/recommended-stretches",
        json={"exercise_id": str(hamstring.id), "phase": "post"}, headers=auth,
    )
    assert added.status_code == 201, added.text
    assert any(e["source"] == "user_added" for e in added.json()["post"])

    # Answer the picker again; the hand-picked one is still there.
    panel = client.post(
        f"{SESSIONS}/{session['id']}/split", json={"split_type": "push"}, headers=auth
    ).json()
    mine = [e for e in panel["post"] if e["source"] == "user_added"]
    assert [e["name"] for e in mine] == [hamstring.name]


def test_adding_the_same_stretch_twice_is_a_no_op(
    client: TestClient, auth: dict, db: Session
) -> None:
    session = client.post(SESSIONS, json={}, headers=auth).json()
    stretch = db.scalar(select(Exercise).where(Exercise.stretch_phase == "post"))
    body = {"exercise_id": str(stretch.id), "phase": "post"}
    for _ in range(3):
        assert client.post(
            f"{SESSIONS}/{session['id']}/recommended-stretches", json=body, headers=auth
        ).status_code == 201

    db.expire_all()
    rows = db.scalars(
        select(RecommendedStretch).where(RecommendedStretch.session_id == uuid.UUID(session["id"]))
    ).all()
    assert len([r for r in rows if r.exercise_id == stretch.id]) == 1


def test_somebody_elses_session_is_not_found(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    session = client.post(SESSIONS, json={}, headers=mine).json()
    r = client.post(f"{SESSIONS}/{session['id']}/split", json={"split_type": "push"}, headers=theirs)
    assert r.status_code == 404


# --- Inheritance: the one place the question is skipped -------------------


def test_a_preset_session_already_knows_its_split(client: TestClient, auth: dict) -> None:
    started = client.post(SESSIONS, json={"preset_slug": "bodybuilding-push-day"}, headers=auth)
    assert started.status_code == 201, started.text
    # A push day IS a push day; the client must not ask.
    assert started.json()["split_type"] == "push"


def test_a_routine_session_inherits_and_a_blank_one_does_not(
    client: TestClient, auth: dict, db: Session
) -> None:
    routine = client.post(ROUTINES, json={"name": "My push day", "exercises": []}, headers=auth).json()
    db.get(Routine, uuid.UUID(routine["id"])).split_type = "push"
    db.commit()

    from_routine = client.post(SESSIONS, json={"routine_id": routine["id"]}, headers=auth).json()
    assert from_routine["split_type"] == "push"
    client.post(f"{SESSIONS}/{from_routine['id']}/abandon", headers=auth)

    blank = client.post(SESSIONS, json={}, headers=auth).json()
    assert blank["split_type"] is None


# --- The library ----------------------------------------------------------


def test_the_library_is_empty_until_there_are_routines(client: TestClient, auth: dict) -> None:
    assert client.get(f"{ROUTINES}/library", headers=auth).json() == []


def test_pinned_routines_come_first(client: TestClient, auth: dict) -> None:
    first = client.post(ROUTINES, json={"name": "Aaa", "exercises": []}, headers=auth).json()
    last = client.post(ROUTINES, json={"name": "Zzz", "exercises": []}, headers=auth).json()

    pinned = client.post(f"{ROUTINES}/{last['id']}/pin", headers=auth)
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["is_pinned"] is True

    order = [row["name"] for row in client.get(f"{ROUTINES}/library", headers=auth).json()]
    assert order == ["Zzz", "Aaa"]

    client.post(f"{ROUTINES}/{last['id']}/pin", params={"pinned": "false"}, headers=auth)
    order = [row["name"] for row in client.get(f"{ROUTINES}/library", headers=auth).json()]
    assert order == ["Aaa", "Zzz"], "unpinning puts it back in name order"


def test_usage_is_counted_from_sessions_not_stored(
    client: TestClient, auth: dict, db: Session
) -> None:
    """The reason there is no use_count column: delete the session and the
    count goes with it, rather than overstating for ever."""
    routine = client.post(ROUTINES, json={"name": "Weekly", "exercises": []}, headers=auth).json()
    me = client.get("/api/v1/auth/me", headers=auth).json()

    now = dt.datetime.now(dt.timezone.utc)
    for _ in range(2):
        db.add(WorkoutSession(
            user_id=uuid.UUID(me["id"]), routine_id=uuid.UUID(routine["id"]),
            started_at=now - dt.timedelta(hours=1), ended_at=now,
            status=SessionStatus.COMPLETED.value,
        ))
    db.commit()

    row = client.get(f"{ROUTINES}/library", headers=auth).json()[0]
    assert row["use_count"] == 2
    assert row["last_used_at"]

    db.query(WorkoutSession).filter(
        WorkoutSession.routine_id == uuid.UUID(routine["id"])
    ).delete()
    db.commit()
    assert client.get(f"{ROUTINES}/library", headers=auth).json()[0]["use_count"] == 0


def test_an_abandoned_workout_is_not_a_use(
    client: TestClient, auth: dict, db: Session
) -> None:
    routine = client.post(ROUTINES, json={"name": "Started once", "exercises": []}, headers=auth).json()
    started = client.post(SESSIONS, json={"routine_id": routine["id"]}, headers=auth).json()
    client.post(f"{SESSIONS}/{started['id']}/abandon", headers=auth)
    assert client.get(f"{ROUTINES}/library", headers=auth).json()[0]["use_count"] == 0


def test_the_library_is_yours_alone(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    client.post(ROUTINES, json={"name": "Mine", "exercises": []}, headers=mine)
    assert client.get(f"{ROUTINES}/library", headers=theirs).json() == []


def test_stretches_do_not_touch_scoring(client: TestClient, auth: dict, db: Session) -> None:
    """A suggestion must never change a score."""
    before = client.get("/api/v1/auth/me", headers=auth).json()["progress"]
    session = client.post(SESSIONS, json={}, headers=auth).json()
    client.post(f"{SESSIONS}/{session['id']}/split", json={"split_type": "legs"}, headers=auth)
    after = client.get("/api/v1/auth/me", headers=auth).json()["progress"]
    assert before == after
