"""Rank trials (app/core/rank_trials.py): B, A and S need a bench, squat and
deadlift at a multiple of bodyweight. Checked through the API: the trial list,
bodyweight in either unit, gaining weight costing a trial, the gate on the
rank, and a trial passed mid-workout reported as a rank-up."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core import leveling
from app.models.user import LevelProgress
from tests.test_workouts import exercise_id, log, start

TRIALS = "/api/v1/profile/trials"
BODY = "/api/v1/body-measurements"
ME = "/api/v1/auth/me"
BENCH = "Barbell Bench Press"


def log_bodyweight(client: TestClient, auth: dict, value: float, unit: str = "kg") -> None:
    r = client.post(BODY, json={"metric": "weight", "value": value, "unit": unit}, headers=auth)
    assert r.status_code == 201, r.text


def trials(client: TestClient, auth: dict) -> dict[str, dict]:
    r = client.get(TRIALS, headers=auth)
    assert r.status_code == 200, r.text
    return {trial["rank"]: trial for trial in r.json()}


def bench(client: TestClient, auth: dict, weight: float) -> dict:
    session = start(client, auth)
    return log(client, auth, session["id"], exercise_id(client, auth, BENCH), weight=weight, reps=3)


def set_level(db: Session, client: TestClient, auth: dict, level: int) -> None:
    user_id = uuid.UUID(client.get(ME, headers=auth).json()["id"])
    db.execute(
        update(LevelProgress)
        .where(LevelProgress.user_id == user_id)
        .values(total_xp=leveling.xp_for_level(level), current_level=level)
    )
    db.flush()


def test_the_trials_wait_for_a_bodyweight(client: TestClient, auth: dict) -> None:
    listed = trials(client, auth)
    assert list(listed) == ["B", "A", "S"]
    assert listed["B"]["description"] == "Barbell Bench Press at 1x bodyweight"
    assert listed["S"]["description"] == "Deadlift at 2x bodyweight"
    assert all(trial["target_kg"] is None and not trial["passed"] for trial in listed.values())


def test_a_bench_at_bodyweight_passes_the_b_trial(client: TestClient, auth: dict) -> None:
    log_bodyweight(client, auth, 80)
    bench(client, auth, 80)

    listed = trials(client, auth)
    assert listed["B"]["passed"]
    assert listed["B"]["target_kg"] == 80.0
    assert listed["B"]["best_kg"] == 80.0
    assert listed["A"]["target_kg"] == 120.0
    assert not listed["A"]["passed"]
    assert client.get(ME, headers=auth).json()["progress"]["trials_passed"] == "B"


def test_a_bodyweight_in_pounds_is_converted(client: TestClient, auth: dict) -> None:
    log_bodyweight(client, auth, 176.37, unit="lb")
    assert abs(trials(client, auth)["B"]["target_kg"] - 80.0) < 0.01


def test_gaining_bodyweight_can_cost_a_trial(client: TestClient, auth: dict) -> None:
    log_bodyweight(client, auth, 80)
    bench(client, auth, 80)
    assert trials(client, auth)["B"]["passed"]

    log_bodyweight(client, auth, 90)
    assert not trials(client, auth)["B"]["passed"]
    assert client.get(ME, headers=auth).json()["progress"]["trials_passed"] == ""


def test_the_trial_gates_the_rank(client: TestClient, auth: dict, db: Session) -> None:
    set_level(db, client, auth, 30)
    progress = client.get(ME, headers=auth).json()["progress"]
    assert progress["rank_by_level"] == "B"
    assert progress["rank"] == "C"
    assert progress["next_rank"] == "B"
    assert progress["next_rank_trial"] == "Barbell Bench Press at 1x bodyweight"

    log_bodyweight(client, auth, 80)
    bench(client, auth, 80)
    progress = client.get(ME, headers=auth).json()["progress"]
    assert progress["rank"] == "B"
    assert progress["next_rank_trial"] is None or progress["next_rank"] == "A"


def test_passing_a_trial_mid_workout_is_a_rank_up(client: TestClient, auth: dict, db: Session) -> None:
    set_level(db, client, auth, 30)
    log_bodyweight(client, auth, 80)

    result = bench(client, auth, 82.5)
    assert result["progression"]["rank_before"] == "C"
    assert result["progression"]["rank_after"] == "B"
    assert result["progression"]["ranked_up"]
