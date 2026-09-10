"""The account weight unit, workout stats and badges on the profile, and the
party workout leaderboard."""

import datetime as dt
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.workout import PointsLedgerEntry, WorkoutSession
from tests.test_workouts import exercise_id, full_workout, log, start

ME = "/api/v1/auth/me"
PROFILE = "/api/v1/profile"
PARTIES = "/api/v1/parties"
WK = "/api/v1/workouts"


# --------------------------------------------------------------------------
# Weight unit, per account
# --------------------------------------------------------------------------


def test_weight_unit_defaults_to_kg(client: TestClient, auth: dict) -> None:
    assert client.get(ME, headers=auth).json()["weight_unit"] == "kg"


def test_weight_unit_is_saved_on_the_account(client: TestClient, auth: dict) -> None:
    r = client.patch(ME, json={"weight_unit": "lb"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["weight_unit"] == "lb"
    # Read back through every surface that reports the user.
    assert client.get(ME, headers=auth).json()["weight_unit"] == "lb"
    assert client.get(PROFILE, headers=auth).json()["user"]["weight_unit"] == "lb"


def test_an_unknown_weight_unit_is_rejected(client: TestClient, auth: dict) -> None:
    assert client.patch(ME, json={"weight_unit": "stone"}, headers=auth).status_code == 422


def test_an_empty_update_changes_nothing(client: TestClient, auth: dict) -> None:
    r = client.patch(ME, json={}, headers=auth)
    assert r.status_code == 200
    assert r.json()["weight_unit"] == "kg"


def test_updating_the_account_requires_auth(client: TestClient) -> None:
    assert client.patch(ME, json={"weight_unit": "lb"}).status_code == 401


# --------------------------------------------------------------------------
# Profile: workout stats and badges
# --------------------------------------------------------------------------


def badge(profile: dict, badge_id: str) -> dict:
    return next(b for b in profile["badges"] if b["id"] == badge_id)


def test_a_new_profile_lists_workout_badges_to_aim_at(client: TestClient, auth: dict) -> None:
    p = client.get(PROFILE, headers=auth).json()
    assert p["stats"]["workouts_completed"] == 0
    assert badge(p, "first_workout")["earned"] is False
    assert badge(p, "first_pr")["target"] == 1


def test_finished_workouts_feed_the_profile(client: TestClient, auth: dict, db: Session) -> None:
    ex = exercise_id(client, auth)
    full_workout(client, auth, db, ex)  # 3 x 100x5: a baseline, then no PRs
    full_workout(client, auth, db, ex, sets=((110, 5),) * 3)  # one PR set

    p = client.get(PROFILE, headers=auth).json()
    stats = p["stats"]
    assert stats["workouts_completed"] == 2
    # The baseline does not count; only the set that beat a record.
    assert stats["workout_prs"] == 1
    assert stats["total_volume_kg"] == 1500 + 1650
    assert badge(p, "first_workout")["earned"] is True
    assert badge(p, "first_pr")["earned"] is True
    assert badge(p, "ten_workouts")["progress"] == 2


def test_a_weekly_streak_reaches_the_profile(client: TestClient, auth: dict, db: Session) -> None:
    ex = exercise_id(client, auth)
    for _ in range(3):
        full_workout(client, auth, db, ex)
    p = client.get(PROFILE, headers=auth).json()
    assert p["stats"]["longest_workout_streak"] == 1
    assert badge(p, "workout_streak_4")["progress"] == 1


def test_abandoned_workouts_do_not_count(client: TestClient, auth: dict) -> None:
    ex = exercise_id(client, auth)
    session = start(client, auth)
    log(client, auth, session["id"], ex)
    client.post(f"{WK}/sessions/{session['id']}/abandon", headers=auth)

    stats = client.get(PROFILE, headers=auth).json()["stats"]
    assert stats["workouts_completed"] == 0
    assert stats["total_volume_kg"] == 0
    assert stats["workout_prs"] == 0


# --------------------------------------------------------------------------
# Party workout leaderboard
# --------------------------------------------------------------------------


def make_party(client: TestClient, owner: dict) -> dict:
    r = client.post(PARTIES, json={"name": "Iron Crew"}, headers=owner)
    assert r.status_code == 201, r.text
    return r.json()


def join(client: TestClient, member: dict, party: dict) -> None:
    r = client.post(f"{PARTIES}/join", json={"invite_code": party["invite_code"]}, headers=member)
    assert r.status_code == 200, r.text


def board(client: TestClient, headers: dict, party: dict, period: str = "week") -> list[dict]:
    r = client.get(f"{PARTIES}/{party['id']}/workout-leaderboard", params={"period": period}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["entries"]


def test_members_are_ranked_by_workout_points(
    client: TestClient, user_factory, db: Session
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    party = make_party(client, alice)
    join(client, bob, party)
    full_workout(client, bob, db, exercise_id(client, bob))

    entries = board(client, alice, party)
    bob_points = client.get(f"{WK}/points", headers=bob).json()["this_week_points"]
    assert [e["points"] for e in entries] == [bob_points, 0]
    assert entries[0]["workouts"] == 1
    assert [e["position"] for e in entries] == [1, 2]
    # A member who has not trained still appears, and the viewer is marked.
    assert entries[1]["is_me"] is True and entries[0]["is_me"] is False


def test_the_week_board_drops_old_points_but_all_time_keeps_them(
    client: TestClient, user_factory, db: Session
) -> None:
    alice, me = user_factory()
    party = make_party(client, alice)
    full_workout(client, alice, db, exercise_id(client, alice))

    user_id = uuid.UUID(me["id"])
    month = dt.timedelta(days=30)
    db.execute(
        update(PointsLedgerEntry)
        .where(PointsLedgerEntry.user_id == user_id)
        .values(created_at=PointsLedgerEntry.created_at - month)
    )
    db.execute(
        update(WorkoutSession)
        .where(WorkoutSession.user_id == user_id)
        .values(
            started_at=WorkoutSession.started_at - month,
            ended_at=WorkoutSession.ended_at - month,
        )
    )
    db.flush()
    db.expire_all()

    week = board(client, alice, party, "week")[0]
    assert (week["points"], week["workouts"]) == (0, 0)
    all_time = board(client, alice, party, "all")[0]
    assert all_time["points"] > 0 and all_time["workouts"] == 1


def test_an_unknown_period_is_rejected(client: TestClient, auth: dict) -> None:
    party = make_party(client, auth)
    r = client.get(f"{PARTIES}/{party['id']}/workout-leaderboard", params={"period": "year"}, headers=auth)
    assert r.status_code == 422


def test_the_workout_board_is_members_only(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    outsider, _ = user_factory()
    party = make_party(client, alice)
    r = client.get(f"{PARTIES}/{party['id']}/workout-leaderboard", headers=outsider)
    assert r.status_code == 404
