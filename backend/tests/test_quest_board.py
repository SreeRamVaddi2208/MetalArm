"""Generated quests and streak freezes over HTTP: lazy generation, progress
from logged sets, completion and its reversal, rerolls, the weekly bonus, and
freezes covering a short week.

Every test here is marked `quests` (conftest.py turns generation off
elsewhere). Most also pin the draw with `force`, so a test can name the quests
it is about instead of depending on which ones a random user id picks.
"""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import quest_board
from app.core import workout_rules as rules
from app.core import workout_streaks as streaks
from app.models.quest_board import QuestAssignment, StreakFreezeEvent
from app.models.user import User
from app.models.workout import PointsLedgerEntry, WorkoutSession
from tests.test_workouts import (
    BENCH,
    WK,
    age,
    exercise_id,
    finish,
    ledger_total,
    log,
    progress,
    start,
)

pytestmark = pytest.mark.quests

BOARD = "/api/v1/quests/current"
STREAK = "/api/v1/streak"


@pytest.fixture
def force(monkeypatch: pytest.MonkeyPatch):
    """Pin which templates are handed out: the first `count` of `codes` that
    the pool offers, in order, skipping excluded ones."""

    def _force(*codes: str) -> None:
        def choose(pool, *, seed, count, exclude=()):
            offered = {c.code for c in pool}
            return [c for c in codes if c in offered and c not in set(exclude)][:count]

        monkeypatch.setattr(quest_board.engine, "choose", choose)

    return _force


def board(client: TestClient, auth: dict) -> dict:
    r = client.get(BOARD, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def quest_rows(db: Session, user_id: str, *types: str) -> list[PointsLedgerEntry]:
    return list(
        db.scalars(
            select(PointsLedgerEntry).where(
                PointsLedgerEntry.user_id == uuid.UUID(user_id),
                PointsLedgerEntry.source_type.in_(types or ("quest_completed", "quest_bonus")),
            )
        )
    )


def set_targets(db: Session, user_id: str, target: int, period: str | None = None) -> None:
    query = update(QuestAssignment).where(QuestAssignment.user_id == uuid.UUID(user_id))
    if period:
        query = query.where(QuestAssignment.period == period)
    db.execute(query.values(target_value=target))
    db.flush()
    db.expire_all()


def set_path(client: TestClient, auth: dict, path: str) -> None:
    r = client.patch("/api/v1/auth/me", json={"character_class": path}, headers=auth)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def test_the_board_is_generated_once_and_never_reshuffles(client: TestClient, auth: dict) -> None:
    first = board(client, auth)
    assert len(first["daily"]) == rules.DAILY_QUESTS
    assert len(first["weekly"]) == rules.WEEKLY_QUESTS
    assert first["rerolls_left"] == rules.QUEST_REROLLS_PER_DAY
    second = board(client, auth)
    assert [q["id"] for q in second["daily"] + second["weekly"]] == [
        q["id"] for q in first["daily"] + first["weekly"]
    ]


def test_a_path_gets_its_own_quests(client: TestClient, auth: dict) -> None:
    set_path(client, auth, "powerlifter")
    got = board(client, auth)
    codes = [q["template_code"] for q in got["daily"] + got["weekly"]]
    assert all(c.startswith(("pl-", "any-")) for c in codes)
    assert any(c.startswith("pl-") for c in codes)


def test_quests_need_auth(client: TestClient) -> None:
    assert client.get(BOARD).status_code == 401
    assert client.get(STREAK).status_code == 401


# ---------------------------------------------------------------------------
# Progress and completion
# ---------------------------------------------------------------------------


def test_sets_advance_a_quest_and_complete_it_once(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("pl-big3-5", "pl-low-rep-8", "pl-big3-pr", "pl-heavy-10", "pl-low-rep-30")
    auth, user = user_factory()
    set_path(client, auth, "powerlifter")
    board(client, auth)
    bench = exercise_id(client, auth)
    session = start(client, auth)

    warmup = log(client, auth, session["id"], bench, weight=40, reps=5, is_warmup=True)
    chip = next(q for q in warmup["quest_progress"] if q["title"] == "Squat, bench, pull")
    assert chip["progress"] == 0 and chip["advanced"] is False

    for n in range(1, 5):
        r = log(client, auth, session["id"], bench, weight=100, reps=5)
        chip = next(q for q in r["quest_progress"] if q["title"] == "Squat, bench, pull")
        assert (chip["progress"], chip["advanced"], chip["completed"]) == (n, True, False)
        assert r["quests_completed"] == []

    fifth = log(client, auth, session["id"], bench, weight=100, reps=5)
    assert [q["title"] for q in fifth["quests_completed"]] == ["Squat, bench, pull"]
    assert fifth["points_awarded"] == rules.SET_POINTS + rules.DAILY_QUEST_POINTS

    sixth = log(client, auth, session["id"], bench, weight=100, reps=5)
    assert sixth["quests_completed"] == []
    assert len(quest_rows(db, user["id"], "quest_completed")) == 1
    assert ledger_total(db, user["id"]) == progress(client, auth)["total_xp"]


def test_quest_points_are_credited_at_finish_and_shown_in_the_breakdown(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    board(client, auth)
    set_targets(db, user["id"], 1, "daily")
    bench = exercise_id(client, auth)
    session = start(client, auth)

    first = log(client, auth, session["id"], bench)
    assert len(first["quests_completed"]) == 2
    assert progress(client, auth)["points_balance"] == 0  # waits for finish

    log(client, auth, session["id"], bench)
    log(client, auth, session["id"], bench)
    age(db, session["id"], 30)
    done = finish(client, auth, session["id"])
    assert done["breakdown"]["quest_points"] == 2 * rules.DAILY_QUEST_POINTS
    assert done["points_credited"] == done["breakdown"]["total"]
    assert progress(client, auth)["points_balance"] == done["points_credited"]


def test_quest_points_never_eat_into_the_set_cap(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    board(client, auth)
    set_targets(db, user["id"], 1)
    bench = exercise_id(client, auth)
    session = start(client, auth)
    sets_to_cap = rules.SET_POINTS_CAP_PER_SESSION // rules.SET_POINTS
    for _ in range(sets_to_cap + 2):
        log(client, auth, session["id"], bench, weight=60, reps=10)

    set_points = db.scalar(
        select(func.sum(PointsLedgerEntry.points)).where(
            PointsLedgerEntry.user_id == uuid.UUID(user["id"]),
            PointsLedgerEntry.source_type == "set_logged",
        )
    )
    assert set_points == rules.SET_POINTS_CAP_PER_SESSION
    assert quest_rows(db, user["id"], "quest_completed")


def test_a_session_quest_needs_a_qualifying_workout(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-show-up", "any-sets-12", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    board(client, auth)
    bench = exercise_id(client, auth)

    trivial = start(client, auth)
    log(client, auth, trivial["id"], bench)
    assert finish(client, auth, trivial["id"])["quests_completed"] == []

    real = start(client, auth)
    for _ in range(3):
        log(client, auth, real["id"], bench)
    age(db, real["id"], 30)
    done = finish(client, auth, real["id"])
    assert [q["title"] for q in done["quests_completed"]] == ["Show up"]


def test_deleting_the_set_that_completed_a_quest_reopens_it(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    board(client, auth)
    set_targets(db, user["id"], 2, "daily")
    bench = exercise_id(client, auth)
    session = start(client, auth)
    log(client, auth, session["id"], bench, weight=20, reps=5)
    second = log(client, auth, session["id"], bench, weight=20, reps=5)
    assert any(q["title"] == "Twelve working sets" for q in second["quests_completed"])

    r = client.delete(f"{WK}/sessions/{session['id']}/sets/{second['set']['id']}", headers=auth)
    assert r.status_code == 200, r.text
    chip = next(q for q in r.json()["quest_progress"] if q["title"] == "Twelve working sets")
    assert (chip["progress"], chip["completed"]) == (1, False)
    assert ledger_total(db, user["id"]) == progress(client, auth)["total_xp"]

    # Completing it again pays again - once.
    again = log(client, auth, session["id"], bench, weight=20, reps=5)
    assert any(q["title"] == "Twelve working sets" for q in again["quests_completed"])
    assert ledger_total(db, user["id"]) == progress(client, auth)["total_xp"]


def test_abandoning_takes_quest_rewards_back(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    board(client, auth)
    set_targets(db, user["id"], 1, "daily")
    bench = exercise_id(client, auth)
    session = start(client, auth)
    log(client, auth, session["id"], bench)

    r = client.post(f"{WK}/sessions/{session['id']}/abandon", headers=auth)
    assert r.status_code == 200
    assert progress(client, auth)["total_xp"] == 0
    assert ledger_total(db, user["id"]) == 0
    assert all(q["status"] == "active" for q in board(client, auth)["daily"])


def test_finishing_every_weekly_quest_pays_the_bonus_once(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-sessions-3", "any-sets-50", "any-volume-20000")
    auth, user = user_factory()
    board(client, auth)
    set_targets(db, user["id"], 1, "weekly")
    bench = exercise_id(client, auth)
    session = start(client, auth)
    for _ in range(3):
        log(client, auth, session["id"], bench)
    age(db, session["id"], 30)
    done = finish(client, auth, session["id"])

    assert len(quest_rows(db, user["id"], "quest_bonus")) == 1
    assert done["breakdown"]["quest_points"] == (
        rules.WEEKLY_QUESTS * rules.WEEKLY_QUEST_POINTS + rules.ALL_WEEKLY_QUESTS_BONUS
    )
    board(client, auth)
    assert len(quest_rows(db, user["id"], "quest_bonus")) == 1


def test_reading_the_board_again_writes_nothing(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    board(client, auth)
    set_targets(db, user["id"], 1, "daily")
    bench = exercise_id(client, auth)
    session = start(client, auth)
    log(client, auth, session["id"], bench)
    before = len(quest_rows(db, user["id"]))
    for _ in range(3):
        board(client, auth)
    assert len(quest_rows(db, user["id"])) == before


# ---------------------------------------------------------------------------
# Rerolls
# ---------------------------------------------------------------------------


def test_one_reroll_a_day_swaps_in_a_quest_not_already_drawn(
    client: TestClient, auth: dict, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-show-up", "any-sessions-3", "any-sets-50", "any-pr")
    first = board(client, auth)
    target = first["daily"][0]
    assert target["can_reroll"] is True

    r = client.post(f"/api/v1/quests/assignments/{target['id']}/reroll", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["quest"]["template_code"] == "any-show-up"
    assert r.json()["rerolls_left"] == 0

    after = board(client, auth)
    assert target["id"] not in [q["id"] for q in after["daily"]]
    assert all(q["can_reroll"] is False for q in after["daily"])
    again = client.post(f"/api/v1/quests/assignments/{after['daily'][0]['id']}/reroll", headers=auth)
    assert again.status_code == 409
    assert "No rerolls left" in again.json()["detail"]


def test_weekly_and_completed_quests_cannot_be_rerolled(
    client: TestClient, user_factory, db: Session, force
) -> None:
    force("any-sets-12", "any-volume-3000", "any-show-up", "any-sessions-3", "any-sets-50", "any-pr")
    auth, user = user_factory()
    got = board(client, auth)
    weekly = client.post(f"/api/v1/quests/assignments/{got['weekly'][0]['id']}/reroll", headers=auth)
    assert weekly.status_code == 409

    set_targets(db, user["id"], 1, "daily")
    log(client, auth, start(client, auth)["id"], exercise_id(client, auth))
    done = client.post(f"/api/v1/quests/assignments/{got['daily'][0]['id']}/reroll", headers=auth)
    assert done.status_code == 409
    assert "completed" in done.json()["detail"]


def test_another_users_quest_is_404(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    qid = board(client, mine)["daily"][0]["id"]
    assert client.post(f"/api/v1/quests/assignments/{qid}/reroll", headers=theirs).status_code == 404


# ---------------------------------------------------------------------------
# Streak freezes
# ---------------------------------------------------------------------------


def _week_offset(week: str, back: int) -> str:
    for _ in range(back):
        week = streaks.previous_week(week)
    return week


def _qualifying_sessions(db: Session, user_id: uuid.UUID, week: str, n: int = 3) -> None:
    monday = dt.date.fromisocalendar(*map(int, week.replace("-W", " ").split()), 2)
    at = dt.datetime.combine(monday, dt.time(12), tzinfo=dt.timezone.utc)
    for i in range(n):
        db.add(
            WorkoutSession(
                user_id=user_id,
                started_at=at + dt.timedelta(hours=i * 2),
                ended_at=at + dt.timedelta(hours=i * 2, minutes=45),
                status="completed",
                qualified=True,
                week_key=week,
            )
        )
    db.flush()


def test_a_held_freeze_covers_a_short_week_and_is_announced_once(
    client: TestClient, user_factory, db: Session
) -> None:
    auth, payload = user_factory()
    uid = uuid.UUID(payload["id"])
    now = dt.datetime.now(dt.timezone.utc)
    current = streaks.week_key(now, "UTC")
    _qualifying_sessions(db, uid, _week_offset(current, 3))
    _qualifying_sessions(db, uid, _week_offset(current, 2))
    # Last week: nothing. Settled up to the week before it, one freeze held.
    db.execute(
        update(User).where(User.id == uid).values(freeze_settled_through=_week_offset(current, 2))
    )
    db.add(StreakFreezeEvent(user_id=uid, delta=1, reason="weekly_quests_complete", week_key=_week_offset(current, 2)))
    db.flush()
    db.expire_all()

    got = client.get(STREAK, headers=auth).json()
    assert got["weeks"] == 2
    assert got["freezes_held"] == 0
    assert got["freezes_used_unseen"] == [_week_offset(current, 1)]

    # Settling again changes nothing.
    assert client.get(STREAK, headers=auth).json()["freezes_held"] == 0
    assert db.scalar(
        select(func.count(StreakFreezeEvent.id)).where(StreakFreezeEvent.user_id == uid)
    ) == 2

    assert client.post(f"{STREAK}/seen", headers=auth).status_code == 204
    assert client.get(STREAK, headers=auth).json()["freezes_used_unseen"] == []
    # The workout summary's streak agrees.
    assert client.get(f"{WK}/points", headers=auth).json()["streak"]["weeks"] == 2


def test_without_a_freeze_the_short_week_still_breaks_the_streak(
    client: TestClient, user_factory, db: Session
) -> None:
    auth, payload = user_factory()
    uid = uuid.UUID(payload["id"])
    current = streaks.week_key(dt.datetime.now(dt.timezone.utc), "UTC")
    _qualifying_sessions(db, uid, _week_offset(current, 2))
    db.execute(
        update(User).where(User.id == uid).values(freeze_settled_through=_week_offset(current, 2))
    )
    db.flush()
    db.expire_all()
    got = client.get(STREAK, headers=auth).json()
    assert (got["weeks"], got["freezes_held"], got["freezes_used_unseen"]) == (0, 0, [])


def test_a_new_user_starts_with_no_freezes_and_old_history_earns_none(
    client: TestClient, user_factory, db: Session
) -> None:
    auth, payload = user_factory()
    uid = uuid.UUID(payload["id"])
    current = streaks.week_key(dt.datetime.now(dt.timezone.utc), "UTC")
    for back in range(2, 12):
        _qualifying_sessions(db, uid, _week_offset(current, back))
    got = client.get(STREAK, headers=auth).json()
    assert got["freezes_held"] == 0
    assert got["freeze_cap"] == rules.FREEZE_CAP
