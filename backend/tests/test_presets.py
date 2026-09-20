"""Ready-made workouts: one per training style, started in a single call."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import presets
from app.models.workout import Routine

PRESETS = "/api/v1/workouts/presets"
SESSIONS = "/api/v1/workouts/sessions"
ROUTINES = "/api/v1/routines"


def test_every_style_is_offered(client: TestClient, auth: dict) -> None:
    rows = client.get(PRESETS, headers=auth).json()
    assert {row["category"] for row in rows} == {"athletic", "powerlifting", "bodybuilding"}
    assert len(rows) == len(presets.all_presets())


def test_a_preset_carries_what_the_ui_needs(client: TestClient, auth: dict) -> None:
    lifting = next(r for r in client.get(PRESETS, headers=auth).json() if r["slug"] == "powerlifting-heavy-day")
    assert lifting["name"] and lifting["summary"]

    first = lifting["exercises"][0]
    assert first["exercise"]["name"] == "Back Squat"
    assert first["target_sets"] == 3 and first["target_reps"] == 5 and first["rest_seconds"] == 180
    # The demo player reads this; null until a link is added to the seed file.
    assert "media_url" in first["exercise"]
    assert first["exercise"]["primary_muscle_groups"]


def test_starting_a_preset_loads_its_plan(client: TestClient, auth: dict) -> None:
    started = client.post(SESSIONS, json={"preset_slug": "athletic-power-day"}, headers=auth)
    assert started.status_code == 201, started.text
    session = started.json()

    preset = presets.by_slug("athletic-power-day")
    planned = [slot["exercise"]["slug"] for slot in session["exercises"]]
    assert planned == [slot.slug for slot in preset.exercises]

    first = session["exercises"][0]
    assert first["target"]["target_sets"] == preset.exercises[0].target_sets
    assert first["target"]["target_reps"] == preset.exercises[0].target_reps
    assert first["target"]["rest_seconds"] == preset.exercises[0].rest_seconds
    assert session["name"] == "Athletic · Power Day"


def test_starting_the_same_preset_twice_reuses_one_routine(
    client: TestClient, auth: dict, db: Session
) -> None:
    """Otherwise a routine would pile up every time the card is tapped."""
    for _ in range(2):
        started = client.post(SESSIONS, json={"preset_slug": "bodybuilding-push-day"}, headers=auth)
        assert started.status_code == 201, started.text
        session_id = started.json()["id"]
        client.post(f"{SESSIONS}/{session_id}/abandon", headers=auth)

    db.expire_all()
    copies = db.scalar(
        select(func.count()).select_from(Routine).where(Routine.preset_slug == "bodybuilding-push-day")
    )
    assert copies == 1


def test_a_started_preset_becomes_an_editable_routine(client: TestClient, auth: dict) -> None:
    client.post(SESSIONS, json={"preset_slug": "powerlifting-heavy-day"}, headers=auth)
    mine = client.get(ROUTINES, headers=auth).json()
    copied = next(r for r in mine if r["name"] == "Powerlifting · Heavy Day")
    assert [s["position"] for s in copied["exercises"]] == list(range(len(copied["exercises"])))

    dropped = client.put(
        f"{ROUTINES}/{copied['id']}",
        json={
            "name": copied["name"],
            "exercises": [{"exercise_id": copied["exercises"][0]["exercise"]["id"], "target_sets": 5}],
        },
        headers=auth,
    )
    assert dropped.status_code == 200, dropped.text
    assert len(dropped.json()["exercises"]) == 1


def test_an_unknown_preset_is_404(client: TestClient, auth: dict) -> None:
    r = client.post(SESSIONS, json={"preset_slug": "crossfit-hero-wod"}, headers=auth)
    assert r.status_code == 404, r.text


def test_a_preset_and_a_routine_together_are_refused(client: TestClient, auth: dict) -> None:
    routine = client.post(ROUTINES, json={"name": "Mine", "exercises": []}, headers=auth).json()
    r = client.post(
        SESSIONS,
        json={"preset_slug": "athletic-power-day", "routine_id": routine["id"]},
        headers=auth,
    )
    assert r.status_code == 422, r.text


def test_presets_need_a_signed_in_user(client: TestClient) -> None:
    assert client.get(PRESETS).status_code == 401


def test_every_preset_slug_is_in_the_library(client: TestClient, auth: dict) -> None:
    """A typo in the seed file would otherwise start an empty workout."""
    offered = {row["slug"] for row in client.get(PRESETS, headers=auth).json()}
    assert offered == {preset.slug for preset in presets.all_presets()}
