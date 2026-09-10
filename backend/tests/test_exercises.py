"""The exercise library, custom exercises, progress history, and the importer."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from scripts.import_exercises import DEFAULT_FILE, import_exercises, read_file

EX = "/api/v1/exercises"
WK = "/api/v1/workouts"


def make_custom(client: TestClient, auth: dict, **overrides) -> dict:
    payload = {
        "name": "Landmine Press",
        "category": "strength",
        "primary_muscle_groups": ["shoulders", "chest"],
        "equipment": "barbell",
    }
    payload.update(overrides)
    r = client.post(EX, json=payload, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------
# Library and search
# --------------------------------------------------------------------------


def test_the_seeded_library_is_searchable(client: TestClient, auth: dict) -> None:
    rows = client.get(EX, params={"q": "bench"}, headers=auth).json()
    names = {r["name"] for r in rows}
    assert "Barbell Bench Press" in names
    assert all("bench" in n.lower() for n in names)


def test_filters_narrow_the_library(client: TestClient, auth: dict) -> None:
    chest = client.get(EX, params={"muscle": "chest", "limit": 200}, headers=auth).json()
    assert chest and all("chest" in r["primary_muscle_groups"] for r in chest)

    cardio = client.get(EX, params={"category": "cardio"}, headers=auth).json()
    assert cardio and all(r["category"] == "cardio" for r in cardio)

    cables = client.get(EX, params={"equipment": "cable"}, headers=auth).json()
    assert cables and all(r["equipment"] == "cable" for r in cables)


def test_search_treats_like_wildcards_literally(client: TestClient, auth: dict) -> None:
    assert client.get(EX, params={"q": "%"}, headers=auth).json() == []


def test_meta_lists_the_vocabularies(client: TestClient, auth: dict) -> None:
    meta = client.get(f"{EX}/meta", headers=auth).json()
    assert "strength" in meta["categories"]
    assert "quads" in meta["muscle_groups"]
    assert meta["weight_units"] == ["kg", "lb"]


def test_the_library_is_read_only(client: TestClient, auth: dict) -> None:
    library = client.get(EX, params={"q": "Deadlift"}, headers=auth).json()[0]
    r = client.patch(f"{EX}/{library['id']}", json={"name": "Mine now"}, headers=auth)
    assert r.status_code == 403
    assert client.delete(f"{EX}/{library['id']}", headers=auth).status_code == 403


# --------------------------------------------------------------------------
# Custom exercises
# --------------------------------------------------------------------------


def test_a_custom_exercise_is_private(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    mine = make_custom(client, alice)
    assert mine["is_custom"] is True

    assert client.get(f"{EX}/{mine['id']}", headers=bob).status_code == 404
    assert client.patch(f"{EX}/{mine['id']}", json={"name": "x"}, headers=bob).status_code == 404
    assert mine["id"] not in {r["id"] for r in client.get(EX, params={"q": "Landmine"}, headers=bob).json()}
    assert mine["id"] in {r["id"] for r in client.get(EX, params={"q": "Landmine"}, headers=alice).json()}


def test_custom_names_are_unique_per_user_ignoring_case_and_spacing(
    client: TestClient, user_factory
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    make_custom(client, alice, name="Landmine Press")
    dup = client.post(
        EX,
        json={"name": "landmine   PRESS", "category": "strength",
              "primary_muscle_groups": ["shoulders"], "equipment": "barbell"},
        headers=alice,
    )
    assert dup.status_code == 409
    make_custom(client, bob, name="Landmine Press")  # a different user may


def test_unknown_muscle_groups_are_rejected(client: TestClient, auth: dict) -> None:
    r = client.post(
        EX,
        json={"name": "X", "category": "strength", "primary_muscle_groups": ["wings"],
              "equipment": "other"},
        headers=auth,
    )
    assert r.status_code == 422


def test_an_unused_custom_exercise_is_deleted(client: TestClient, auth: dict) -> None:
    mine = make_custom(client, auth)
    r = client.delete(f"{EX}/{mine['id']}", headers=auth)
    assert r.json() == {"archived": False}
    assert client.get(f"{EX}/{mine['id']}", headers=auth).status_code == 404


def test_a_used_custom_exercise_is_archived_not_deleted(client: TestClient, auth: dict) -> None:
    """History must never point at a deleted exercise."""
    mine = make_custom(client, auth)
    session = client.post(f"{WK}/sessions", json={}, headers=auth).json()
    client.post(
        f"{WK}/sessions/{session['id']}/sets",
        json={"exercise_id": mine["id"], "weight": 40, "reps": 10},
        headers=auth,
    )
    assert client.delete(f"{EX}/{mine['id']}", headers=auth).json() == {"archived": True}

    visible = {r["id"] for r in client.get(EX, params={"custom_only": True}, headers=auth).json()}
    assert mine["id"] not in visible
    archived = client.get(
        EX, params={"custom_only": True, "include_archived": True}, headers=auth
    ).json()
    assert mine["id"] in {r["id"] for r in archived}

    # And it can no longer be logged against.
    r = client.post(
        f"{WK}/sessions/{session['id']}/sets",
        json={"exercise_id": mine["id"], "weight": 40, "reps": 10},
        headers=auth,
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------
# Progress history
# --------------------------------------------------------------------------


def test_history_is_one_point_per_completed_session_oldest_first(
    client: TestClient, auth: dict
) -> None:
    ex = client.get(EX, params={"q": "Back Squat"}, headers=auth).json()[0]["id"]
    for weights in ((100, 110), (105, 120)):
        session = client.post(f"{WK}/sessions", json={}, headers=auth).json()
        for w in weights:
            client.post(
                f"{WK}/sessions/{session['id']}/sets",
                json={"exercise_id": ex, "weight": w, "reps": 5},
                headers=auth,
            )
        client.post(
            f"{WK}/sessions/{session['id']}/sets",
            json={"exercise_id": ex, "weight": 60, "reps": 10, "is_warmup": True},
            headers=auth,
        )
        client.post(f"{WK}/sessions/{session['id']}/finish", headers=auth)

    history = client.get(f"{EX}/{ex}/history", headers=auth).json()
    assert [p["top_weight_kg"] for p in history] == [110, 120]
    assert history[0]["volume_kg"] == 1050  # warm-up excluded
    assert history[1]["best_est_1rm"] == 140  # 120 * 35/30
    assert history[0]["working_sets"] == 2


def test_last_performance_is_empty_for_a_new_exercise(client: TestClient, auth: dict) -> None:
    ex = client.get(EX, params={"q": "Pull-Up"}, headers=auth).json()[0]["id"]
    ghost = client.get(f"{EX}/{ex}/last-performance", headers=auth).json()
    assert ghost["sets"] == [] and ghost["session_id"] is None


# --------------------------------------------------------------------------
# Importer
# --------------------------------------------------------------------------


def test_the_shipped_seed_file_is_a_real_starter_library() -> None:
    records = read_file(DEFAULT_FILE)
    assert 50 <= len(records) <= 150
    categories = {r["category"] for r in records}
    assert categories == {"strength", "cardio", "bodyweight", "mobility"}


def test_reimporting_is_a_no_op(db: Session) -> None:
    """conftest already imported the file once; a second run changes nothing."""
    records = read_file(DEFAULT_FILE)
    report = import_exercises(db, records)
    assert report.inserted == 0 and report.updated == 0
    assert report.unchanged == len(records)


def test_the_importer_updates_in_place_by_slug(db: Session) -> None:
    records = read_file(DEFAULT_FILE)
    records[0] = {**records[0], "instructions": "Updated cue."}
    report = import_exercises(db, records)
    assert report.updated == 1 and report.inserted == 0


def test_a_bad_seed_file_is_rejected_whole(db: Session) -> None:
    bad = [
        {"name": "Good One", "category": "strength", "primary_muscle_groups": ["chest"], "equipment": "barbell"},
        {"name": "Bad One", "category": "juggling", "primary_muscle_groups": ["chest"], "equipment": "barbell"},
    ]
    with pytest.raises(ValueError, match="Bad One"):
        import_exercises(db, bad)


def test_duplicate_names_in_a_seed_file_are_rejected(db: Session) -> None:
    dup = [
        {"slug": "a", "name": "Same", "category": "strength", "primary_muscle_groups": ["chest"], "equipment": "barbell"},
        {"slug": "b", "name": "same", "category": "strength", "primary_muscle_groups": ["chest"], "equipment": "barbell"},
    ]
    with pytest.raises(ValueError, match="duplicate name_key"):
        import_exercises(db, dup)
