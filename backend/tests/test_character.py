"""The character sheet (app/core/character.py): three stats derived from real
training, and a class that only highlights them - never changes a number."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import character
from tests.test_workouts import exercise_id, full_workout

CHARACTER = "/api/v1/profile/character"
ME = "/api/v1/auth/me"
BODY = "/api/v1/body-measurements"


def stats(client: TestClient, headers: dict) -> dict:
    r = client.get(CHARACTER, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    return {s["key"]: s for s in body["stats"]} | {"_class": body}


def test_a_new_account_scores_zero_and_says_why(client: TestClient, auth: dict) -> None:
    sheet = stats(client, auth)
    assert [sheet[k]["value"] for k in ("strength", "endurance", "discipline")] == [0, 0, 0]
    assert sheet["strength"]["detail"] == "Log a bodyweight to score strength"
    assert sheet["_class"]["character_class"] == ""
    assert sheet["_class"]["class_label"] == ""


def test_training_moves_the_stats(client: TestClient, auth: dict, db: Session) -> None:
    assert client.post(
        BODY, json={"metric": "weight", "value": 80, "unit": "kg"}, headers=auth
    ).status_code == 201
    full_workout(client, auth, db, exercise_id(client, auth))

    sheet = stats(client, auth)
    assert sheet["strength"]["value"] > 0
    assert "bodyweight" in sheet["strength"]["detail"]
    assert sheet["endurance"]["value"] > 0
    assert "four weeks" in sheet["endurance"]["detail"]
    # One workout is not a week on target.
    assert sheet["discipline"]["value"] == 0
    assert sheet["discipline"]["detail"].endswith(f"of the last {character.DISCIPLINE_WEEKS} weeks on target")


def test_a_class_highlights_stats_without_changing_them(
    client: TestClient, auth: dict, db: Session
) -> None:
    assert client.post(
        BODY, json={"metric": "weight", "value": 80, "unit": "kg"}, headers=auth
    ).status_code == 201
    full_workout(client, auth, db, exercise_id(client, auth))
    before = stats(client, auth)

    updated = client.patch(ME, json={"character_class": "powerlifter"}, headers=auth)
    assert updated.status_code == 200, updated.text
    assert updated.json()["character_class"] == "powerlifter"

    after = stats(client, auth)
    assert after["_class"]["class_label"] == "Powerlifter"
    assert [after[k]["highlighted"] for k in ("strength", "endurance", "discipline")] == [
        True,
        False,
        False,
    ]
    # The scores are identical: a class is cosmetic.
    assert [after[k]["value"] for k in ("strength", "endurance", "discipline")] == [
        before[k]["value"] for k in ("strength", "endurance", "discipline")
    ]


def test_each_class_highlights_its_own_stats(client: TestClient, auth: dict) -> None:
    for chosen, expected in (
        ("bodybuilder", ["strength", "endurance"]),
        ("athlete", ["endurance", "discipline"]),
    ):
        assert client.patch(ME, json={"character_class": chosen}, headers=auth).status_code == 200
        sheet = stats(client, auth)
        highlighted = [k for k in ("strength", "endurance", "discipline") if sheet[k]["highlighted"]]
        assert highlighted == expected


def test_an_unknown_class_is_refused(client: TestClient, auth: dict) -> None:
    assert client.patch(ME, json={"character_class": "wizard"}, headers=auth).status_code == 422


def test_the_class_can_be_cleared(client: TestClient, auth: dict) -> None:
    assert client.patch(ME, json={"character_class": "athlete"}, headers=auth).status_code == 200
    cleared = client.patch(ME, json={"character_class": ""}, headers=auth)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["character_class"] == ""
    sheet = stats(client, auth)
    assert not any(sheet[k]["highlighted"] for k in ("strength", "endurance", "discipline"))
