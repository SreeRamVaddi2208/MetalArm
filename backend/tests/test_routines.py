"""Routines: CRUD, ordering, and which exercises a routine may reference."""

from fastapi.testclient import TestClient

RT = "/api/v1/routines"
EX = "/api/v1/exercises"


def ex(client: TestClient, auth: dict, name: str) -> str:
    rows = client.get(EX, params={"q": name, "limit": 200}, headers=auth).json()
    return next(r["id"] for r in rows if r["name"] == name)


def make(client: TestClient, auth: dict, exercises: list[dict], name: str = "Push") -> dict:
    r = client.post(RT, json={"name": name, "exercises": exercises}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_routine_keeps_its_exercise_order(client: TestClient, auth: dict) -> None:
    bench, ohp = ex(client, auth, "Barbell Bench Press"), ex(client, auth, "Overhead Press")
    routine = make(
        client, auth,
        [{"exercise_id": ohp, "target_sets": 3}, {"exercise_id": bench, "target_reps": 8}],
    )
    assert [s["exercise"]["id"] for s in routine["exercises"]] == [ohp, bench]
    assert [s["position"] for s in routine["exercises"]] == [0, 1]
    assert client.get(RT, headers=auth).json()[0]["id"] == routine["id"]


def test_put_replaces_the_whole_exercise_list(client: TestClient, auth: dict) -> None:
    bench, squat = ex(client, auth, "Barbell Bench Press"), ex(client, auth, "Back Squat")
    routine = make(client, auth, [{"exercise_id": bench}, {"exercise_id": squat}])
    r = client.put(
        f"{RT}/{routine['id']}",
        json={"name": "Legs", "exercises": [{"exercise_id": squat, "target_sets": 5}]},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Legs"
    assert [(s["exercise"]["id"], s["target_sets"]) for s in body["exercises"]] == [(squat, 5)]


def test_an_unknown_exercise_is_rejected(client: TestClient, auth: dict) -> None:
    r = client.post(
        RT,
        json={"name": "X", "exercises": [{"exercise_id": "00000000-0000-0000-0000-000000000000"}]},
        headers=auth,
    )
    assert r.status_code == 422


def test_another_users_private_exercise_cannot_be_referenced(
    client: TestClient, user_factory
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    private = client.post(
        EX,
        json={"name": "Secret Lift", "category": "strength",
              "primary_muscle_groups": ["back"], "equipment": "other"},
        headers=alice,
    ).json()
    r = client.post(RT, json={"name": "X", "exercises": [{"exercise_id": private["id"]}]}, headers=bob)
    assert r.status_code == 422


def test_another_users_routine_is_404(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    routine = make(client, alice, [])
    url = f"{RT}/{routine['id']}"
    assert client.get(url, headers=bob).status_code == 404
    assert client.put(url, json={"name": "x", "exercises": []}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.post("/api/v1/workouts/sessions", json={"routine_id": routine["id"]}, headers=bob).status_code == 404


def test_deleting_a_routine_keeps_workouts_started_from_it(client: TestClient, auth: dict) -> None:
    routine = make(client, auth, [{"exercise_id": ex(client, auth, "Back Squat")}])
    session = client.post(
        "/api/v1/workouts/sessions", json={"routine_id": routine["id"]}, headers=auth
    ).json()
    assert client.delete(f"{RT}/{routine['id']}", headers=auth).status_code == 204

    after = client.get(f"/api/v1/workouts/sessions/{session['id']}", headers=auth)
    assert after.status_code == 200
    assert after.json()["routine_id"] is None
