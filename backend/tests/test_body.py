"""Body measurements: validation of metric/unit/label, and ownership."""

import pytest
from fastapi.testclient import TestClient

BODY = "/api/v1/body-measurements"


def test_measurements_are_listed_newest_first(client: TestClient, auth: dict) -> None:
    client.post(BODY, json={"metric": "weight", "value": 80, "unit": "kg",
                            "recorded_at": "2026-09-01T08:00:00+00:00"}, headers=auth)
    client.post(BODY, json={"metric": "weight", "value": 79.5, "unit": "kg",
                            "recorded_at": "2026-09-08T08:00:00+00:00"}, headers=auth)
    client.post(BODY, json={"metric": "body_fat", "value": 18, "unit": "percent"}, headers=auth)

    weights = client.get(BODY, params={"metric": "weight"}, headers=auth).json()
    assert [w["value"] for w in weights] == [79.5, 80]
    assert len(client.get(BODY, headers=auth).json()) == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"metric": "weight", "value": 80, "unit": "percent"},  # wrong unit
        {"metric": "body_fat", "value": 18, "unit": "kg"},  # wrong unit
        {"metric": "body_fat", "value": 140, "unit": "percent"},  # not a percentage
        {"metric": "custom", "value": 90, "unit": "cm"},  # custom needs a label
        {"metric": "weight", "label": "morning", "value": 80, "unit": "kg"},  # only custom takes one
        {"metric": "weight", "value": 0, "unit": "kg"},
        {"metric": "weight", "value": 80, "unit": "kg", "recorded_at": "2026-09-01T08:00:00"},  # naive
    ],
)
def test_inconsistent_measurements_are_rejected(
    client: TestClient, auth: dict, payload: dict
) -> None:
    assert client.post(BODY, json=payload, headers=auth).status_code == 422


def test_a_custom_metric_carries_its_label(client: TestClient, auth: dict) -> None:
    r = client.post(BODY, json={"metric": "custom", "label": "Waist", "value": 82, "unit": "cm"}, headers=auth)
    assert r.status_code == 201
    assert r.json()["label"] == "Waist"


def test_another_users_measurement_is_invisible(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    mine = client.post(BODY, json={"metric": "weight", "value": 80, "unit": "kg"}, headers=alice).json()
    assert client.get(BODY, headers=bob).json() == []
    assert client.delete(f"{BODY}/{mine['id']}", headers=bob).status_code == 404
    assert client.delete(f"{BODY}/{mine['id']}", headers=alice).status_code == 204
