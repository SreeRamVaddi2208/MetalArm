"""The training path: what it means, choosing it, and what it changes."""

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import training_categories
from app.core.security import normalize_email
from app.models.training_category import TrainingCategoryProfile
from app.models.user import User

PATHS = "/api/v1/training-categories"
ME = "/api/v1/auth/me"
PRESETS = "/api/v1/workouts/presets"


def test_every_path_is_described(client: TestClient, auth: dict) -> None:
    rows = client.get(PATHS, headers=auth).json()
    assert [row["category"] for row in rows] == ["athlete", "bodybuilder", "powerlifter"]
    assert [row["display_name"] for row in rows] == ["Athletic", "Bodybuilder", "Powerlifter"]
    for row in rows:
        assert row["tagline"] and row["description"]
        assert 1 <= row["rep_range_low"] <= row["rep_range_high"]
        assert row["emphasis_tags"]


def test_the_numbers_match_the_definitions(client: TestClient, auth: dict) -> None:
    """Athletic trains light and high; powerlifting heavy and low. If these
    ever cross over, the paths have stopped meaning anything."""
    rows = {row["category"]: row for row in client.get(PATHS, headers=auth).json()}

    assert rows["athlete"]["relative_load"] == "low"
    assert rows["athlete"]["relative_volume"] == "high"
    assert rows["athlete"]["rep_range_low"] >= 12

    assert rows["powerlifter"]["relative_load"] == "heavy"
    assert rows["powerlifter"]["relative_volume"] == "low"
    assert rows["powerlifter"]["rep_range_high"] <= 6

    assert rows["bodybuilder"]["rep_range_low"] >= rows["powerlifter"]["rep_range_high"]
    assert rows["powerlifter"]["rest_seconds_guidance"] > rows["athlete"]["rest_seconds_guidance"]


def test_paths_need_a_signed_in_user(client: TestClient) -> None:
    assert client.get(PATHS).status_code == 401


def test_choosing_a_path_records_when(client: TestClient, auth: dict, db: Session) -> None:
    before = client.get(ME, headers=auth).json()
    assert before["character_class"] == ""

    chosen = client.patch(ME, json={"character_class": "athlete"}, headers=auth)
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["character_class"] == "athlete"

    db.expire_all()
    user = db.scalar(select(User).where(User.email_normalized == normalize_email(before["email"])))
    assert user.character_class_set_at is not None
    assert (dt.datetime.now(dt.timezone.utc) - user.character_class_set_at).total_seconds() < 60


def test_a_path_can_be_changed_and_cleared(client: TestClient, auth: dict, db: Session) -> None:
    """It is a preference, not a one-time decision: training goals shift."""
    client.patch(ME, json={"character_class": "powerlifter"}, headers=auth)
    switched = client.patch(ME, json={"character_class": "bodybuilder"}, headers=auth)
    assert switched.json()["character_class"] == "bodybuilder"

    cleared = client.patch(ME, json={"character_class": ""}, headers=auth)
    assert cleared.json()["character_class"] == ""
    db.expire_all()
    email = client.get(ME, headers=auth).json()["email"]
    user = db.scalar(select(User).where(User.email_normalized == normalize_email(email)))
    # Cleared, but still asked: onboarding must not ask again.
    assert user.character_class_set_at is not None


def test_an_unknown_path_is_refused(client: TestClient, auth: dict) -> None:
    assert client.patch(ME, json={"character_class": "crossfitter"}, headers=auth).status_code == 422


def test_no_path_is_a_valid_state(client: TestClient, auth: dict) -> None:
    """Skipping the question must leave every screen working."""
    assert client.get(ME, headers=auth).json()["character_class"] == ""
    assert client.get("/api/v1/profile", headers=auth).status_code == 200
    assert client.get("/api/v1/profile/character", headers=auth).status_code == 200
    presets = client.get(PRESETS, headers=auth).json()
    assert len(presets) == 3
    assert not any(preset["matches_your_path"] for preset in presets)


def test_your_own_workout_comes_first(client: TestClient, auth: dict) -> None:
    client.patch(ME, json={"character_class": "bodybuilder"}, headers=auth)
    presets = client.get(PRESETS, headers=auth).json()
    assert presets[0]["category"] == "bodybuilder"
    assert presets[0]["matches_your_path"] is True
    assert [p["matches_your_path"] for p in presets[1:]] == [False, False]


def test_the_seed_is_idempotent(db: Session) -> None:
    """It runs on every deploy."""
    assert training_categories.seed(db) == 0

    athlete = db.get(TrainingCategoryProfile, "athlete")
    athlete.tagline = "drifted"
    db.flush()
    assert training_categories.seed(db) == 1
    db.flush()
    db.expire_all()
    assert db.get(TrainingCategoryProfile, "athlete").tagline != "drifted"


def test_a_path_never_touches_scoring(client: TestClient, auth: dict) -> None:
    """The whole reason a path is safe to choose freely."""
    before = client.get("/api/v1/workouts/points", headers=auth).json()
    client.patch(ME, json={"character_class": "powerlifter"}, headers=auth)
    after = client.get("/api/v1/workouts/points", headers=auth).json()
    assert before == after
