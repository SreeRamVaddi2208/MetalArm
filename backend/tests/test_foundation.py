"""Overhaul phase 0: the profile fields, the taxonomy, and exercise media
attribution."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import taxonomy
from app.models.workout import Exercise
from app.models.workout_enums import Equipment, MuscleGroup
from scripts.import_exercises import LibraryExercise

ME = "/api/v1/auth/me"


def test_the_taxonomy_covers_every_code_the_exercises_use(client: TestClient, auth: dict) -> None:
    got = client.get("/api/v1/taxonomy", headers=auth).json()
    assert {m["code"] for m in got["muscle_groups"]} == {m.value for m in MuscleGroup}
    assert {e["code"] for e in got["equipment"]} == {e.value for e in Equipment}
    chest = next(m for m in got["muscle_groups"] if m["code"] == "chest")
    assert chest["display_name"] == "Chest" and chest["svg_path_ids"] and chest["browsable"]
    # The Explore grid: the spec's thirteen tiles, in order.
    assert [m["display_name"] for m in got["muscle_groups"] if m["browsable"]][:3] == [
        "Chest", "Biceps", "Triceps",
    ]


def test_the_taxonomy_needs_auth(client: TestClient) -> None:
    assert client.get("/api/v1/taxonomy").status_code == 401


def test_seeding_the_taxonomy_twice_writes_nothing(db: Session) -> None:
    assert taxonomy.seed(db) == 0


def test_profile_fields_round_trip(client: TestClient, auth: dict) -> None:
    r = client.patch(ME, json={
        "username": "Iron_Mike", "bio": "Squats on Mondays", "default_rest_seconds": 120,
        "default_visibility": "public", "display_name": "Mike",
    }, headers=auth)
    assert r.status_code == 200, r.text
    me = client.get(ME, headers=auth).json()
    assert (me["username"], me["bio"], me["default_rest_seconds"], me["default_visibility"],
            me["display_name"]) == ("Iron_Mike", "Squats on Mondays", 120, "public", "Mike")
    # null clears a bio; null leaves a default alone.
    client.patch(ME, json={"bio": None, "default_rest_seconds": None}, headers=auth)
    me = client.get(ME, headers=auth).json()
    assert me["bio"] is None and me["default_rest_seconds"] == 120


def test_usernames_are_unique_ignoring_case(client: TestClient, user_factory) -> None:
    a, _ = user_factory()
    b, _ = user_factory()
    assert client.patch(ME, json={"username": "lifter"}, headers=a).status_code == 200
    r = client.patch(ME, json={"username": "LIFTER"}, headers=b)
    assert r.status_code == 409


@pytest.mark.parametrize("bad", ["ab", "has space", "x" * 31, "emoji💪"])
def test_bad_usernames_are_rejected(client: TestClient, auth: dict, bad: str) -> None:
    assert client.patch(ME, json={"username": bad}, headers=auth).status_code == 422


def test_bad_visibility_is_rejected(client: TestClient, auth: dict) -> None:
    assert client.patch(ME, json={"default_visibility": "everyone"}, headers=auth).status_code == 422


def test_library_artwork_without_attribution_is_refused() -> None:
    base = {"name": "Thing", "category": "strength", "primary_muscle_groups": ["chest"],
            "equipment": "barbell", "illustration_url": "/assets/x.png"}
    with pytest.raises(ValueError):
        LibraryExercise.model_validate(base)
    ok = LibraryExercise.model_validate({**base, "media_license": "CC-BY-SA 4", "media_author": "someone"})
    assert ok.columns()["media_license"] == "CC-BY-SA 4"


def test_the_database_refuses_unattributed_artwork(db: Session) -> None:
    # Every library exercise has credited artwork now: take one and drop
    # the credit, keeping the picture.
    exercise = db.scalars(select(Exercise).where(Exercise.illustration_url.is_not(None)).limit(1)).one()
    exercise.media_license = None
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.flush()


def test_exercises_carry_the_new_fields(client: TestClient, auth: dict) -> None:
    rows = client.get("/api/v1/exercises", params={"q": "Bench", "limit": 5}, headers=auth).json()
    first = rows[0]
    for field in ("secondary_muscle_groups", "mechanic", "steps", "tips", "illustration_url",
                  "media_license", "media_author"):
        assert field in first
