"""The original curated programs and ready-made workouts moved into the
Library catalog. These pin that nothing a client could see changed: the data
is rebuilt identically, the old endpoints answer as before, and routines users
already made from them keep working."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import curated, presets
from app.models.library import LibraryWorkout
from app.models.workout import Routine

FIXTURES = Path(__file__).parent / "fixtures"
A = "/api/v1"


def test_curated_programs_are_rebuilt_exactly() -> None:
    """The files the old loader read, byte for byte as data."""
    assert list(curated.definitions()) == json.loads((FIXTURES / "legacy_curated_programs.json").read_text())


def test_presets_are_rebuilt_exactly() -> None:
    old = json.loads((FIXTURES / "legacy_workout_presets.json").read_text())
    assert [p.model_dump() for p in presets.all_presets()] == old


def test_the_curated_endpoint_still_serves_the_original_six(client: TestClient, auth: dict) -> None:
    old = json.loads((FIXTURES / "legacy_curated_programs.json").read_text())
    served = client.get(f"{A}/programs/curated", headers=auth).json()
    assert sorted(p["slug"] for p in served) == sorted(p["slug"] for p in old)
    by_slug = {p["slug"]: p for p in served}
    for program in old:
        got = by_slug[program["slug"]]
        assert got["name"] == program["name"] and got["weeks"] == program["weeks"]
        assert [r["name"] for r in got["routines"]] == [r["name"] for r in program["routines"]]


def test_the_presets_endpoint_still_serves_the_original_three(client: TestClient, auth: dict) -> None:
    old = json.loads((FIXTURES / "legacy_workout_presets.json").read_text())
    served = client.get(f"{A}/workouts/presets", headers=auth).json()
    assert [p["slug"] for p in served] and sorted(p["slug"] for p in served) == sorted(p["slug"] for p in old)


def test_a_preset_start_records_where_it_came_from(client: TestClient, auth: dict, db: Session) -> None:
    started = client.post(f"{A}/workouts/sessions", json={"preset_slug": "powerlifting-heavy-day"}, headers=auth)
    assert started.status_code == 201, started.text
    preset = db.scalar(select(LibraryWorkout).where(LibraryWorkout.slug == "powerlifting-heavy-day"))
    assert started.json()["library_workout_id"] == str(preset.id)


def test_a_preset_routine_made_before_the_move_is_reused(client: TestClient, auth: dict, db: Session) -> None:
    for _ in range(2):
        session = client.post(f"{A}/workouts/sessions", json={"preset_slug": "bodybuilding-push-day"}, headers=auth)
        assert session.status_code == 201, session.text
        client.post(f"{A}/workouts/sessions/{session.json()['id']}/abandon", headers=auth)
    me = client.get(f"{A}/auth/me", headers=auth).json()
    assert db.scalar(select(func.count()).select_from(Routine).where(
        Routine.user_id == me["id"], Routine.preset_slug == "bodybuilding-push-day")) == 1


def test_a_saved_curated_program_still_starts(client: TestClient, auth: dict) -> None:
    saved = client.post(f"{A}/programs/curated/barbell-foundations/save", headers=auth)
    assert saved.status_code in (200, 201), saved.text
    routine_id = saved.json()["routines"][0]["id"]
    started = client.post(f"{A}/workouts/sessions", json={"routine_id": routine_id}, headers=auth)
    assert started.status_code == 201, started.text
    assert [e["exercise"]["slug"] for e in started.json()["exercises"]][:2] == ["back-squat", "barbell-bench-press"]
