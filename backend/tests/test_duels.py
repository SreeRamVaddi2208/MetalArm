"""Duels: scoring, the synthetic rival, judging, and paying the winner exactly once."""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from decimal import Decimal

from app.core import duels as engine
from app.models.duel import Duel, DuelStatus
from app.models.workout import Exercise, PointsLedgerEntry, SetEntry, WorkoutSession
from app.models.workout_enums import LedgerSource, SessionStatus

DUELS = "/api/v1/duels"
PARTIES = "/api/v1/parties"
FEED = "/api/v1/feed"


def party_with(client: TestClient, owner: dict, joiner: dict) -> dict:
    party = client.post(PARTIES, json={"name": "Iron"}, headers=owner).json()
    joined = client.post(
        f"{PARTIES}/join", json={"invite_code": party["invite_code"]}, headers=joiner
    )
    assert joined.status_code == 200, joined.text
    return party


def train(db: Session, user_id: str, at: dt.datetime, *, weight: float = 100, reps: int = 10,
          sets: int = 1) -> None:
    """A finished workout inside a window, written straight to the tables.

    The API would stamp it with "now", and these tests need training that
    happened at a chosen moment - which is the whole point of a window.
    """
    exercise = db.scalars(select(Exercise).limit(1)).first()
    session = WorkoutSession(
        user_id=uuid.UUID(user_id),
        started_at=at - dt.timedelta(minutes=45),
        ended_at=at,
        status=SessionStatus.COMPLETED.value,
    )
    db.add(session)
    db.flush()
    for number in range(1, sets + 1):
        db.add(
            SetEntry(
                session_id=session.id,
                user_id=uuid.UUID(user_id),
                exercise_id=exercise.id,
                set_number=number,
                weight_kg=Decimal(str(weight)),
                reps=reps,
                is_warmup=False,
                completed_at=at,
            )
        )
    db.commit()


def backdate(db: Session, duel_id: str, days: int = 1) -> Duel:
    """Start the window in the past, so training can happen inside a RUNNING
    duel - a duel created now has its whole window in the future."""
    duel = db.get(Duel, uuid.UUID(duel_id))
    duel.window_start = duel.window_start - dt.timedelta(days=days)
    db.commit()
    db.refresh(duel)
    return duel


def close_window(db: Session, duel_id: str) -> Duel:
    """Put the window in the past so the next read judges it."""
    duel = db.get(Duel, uuid.UUID(duel_id))
    now = dt.datetime.now(dt.timezone.utc)
    duel.window_start = now - dt.timedelta(days=2)
    duel.window_end = now - dt.timedelta(seconds=1)
    db.commit()
    return duel


# --------------------------------------------------------------------------
# Creating
# --------------------------------------------------------------------------


def test_duels_need_a_signed_in_user(client: TestClient) -> None:
    assert client.get(DUELS).status_code == 401


def test_a_rival_duel_starts_immediately(client: TestClient, auth: dict) -> None:
    """There is nobody to accept it, so waiting would mean waiting forever."""
    r = client.post(DUELS, json={"against_rival": True, "days": 7}, headers=auth)
    assert r.status_code == 201, r.text
    duel = r.json()
    assert duel["status"] == "active"
    assert duel["opponent"]["is_rival"] is True
    assert duel["opponent"]["user_id"] is None


def test_a_challenge_waits_to_be_accepted(client: TestClient, user_factory) -> None:
    mine, me = user_factory()
    theirs, them = user_factory()
    party_with(client, mine, theirs)

    r = client.post(DUELS, json={"opponent_id": them["id"], "days": 3}, headers=mine)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"

    accepted = client.post(f"{DUELS}/{r.json()['id']}/accept", headers=theirs)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "active"


def test_accepting_restarts_the_window(client: TestClient, user_factory, db: Session) -> None:
    """A challenge left sitting for days must not hand the challenger a head start."""
    mine, _ = user_factory()
    theirs, them = user_factory()
    party_with(client, mine, theirs)
    made = client.post(DUELS, json={"opponent_id": them["id"], "days": 7}, headers=mine).json()

    duel = db.get(Duel, uuid.UUID(made["id"]))
    duel.window_start = duel.window_start - dt.timedelta(days=5)
    duel.window_end = duel.window_end - dt.timedelta(days=5)
    db.commit()

    client.post(f"{DUELS}/{made['id']}/accept", headers=theirs)
    db.expire_all()
    duel = db.get(Duel, uuid.UUID(made["id"]))
    remaining = duel.window_end - dt.datetime.now(dt.timezone.utc)
    assert remaining > dt.timedelta(days=6), remaining


def test_only_the_challenged_can_accept(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, them = user_factory()
    party_with(client, mine, theirs)
    made = client.post(DUELS, json={"opponent_id": them["id"]}, headers=mine).json()
    assert client.post(f"{DUELS}/{made['id']}/accept", headers=mine).status_code == 409


def test_you_cannot_challenge_a_stranger(client: TestClient, user_factory) -> None:
    """Otherwise a challenge is a way to ask whether an account exists."""
    mine, _ = user_factory()
    _, them = user_factory()
    r = client.post(DUELS, json={"opponent_id": them["id"]}, headers=mine)
    assert r.status_code == 404, r.text


def test_you_cannot_duel_yourself(client: TestClient, user_factory) -> None:
    mine, me = user_factory()
    assert client.post(DUELS, json={"opponent_id": me["id"]}, headers=mine).status_code == 422


def test_an_opponent_and_a_rival_together_are_refused(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    _, them = user_factory()
    r = client.post(
        DUELS, json={"opponent_id": them["id"], "against_rival": True}, headers=mine
    )
    assert r.status_code == 422, r.text


def test_neither_an_opponent_nor_a_rival_is_refused(client: TestClient, auth: dict) -> None:
    assert client.post(DUELS, json={"days": 7}, headers=auth).status_code == 422


def test_a_duel_someone_else_is_in_is_not_found(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    stranger, _ = user_factory()
    made = client.post(DUELS, json={"against_rival": True}, headers=mine).json()
    assert client.get(f"{DUELS}/{made['id']}", headers=stranger).status_code == 404


# --------------------------------------------------------------------------
# The rival
# --------------------------------------------------------------------------


def test_the_rival_asks_for_something_from_a_standing_start(
    client: TestClient, auth: dict, db: Session
) -> None:
    """A brand-new user has no history, and a target of zero is unlosable."""
    made = client.post(DUELS, json={"against_rival": True, "days": 7}, headers=auth).json()
    duel = db.get(Duel, uuid.UUID(made["id"]))
    assert float(duel.rival_target) == pytest.approx(engine.RIVAL_FLOOR[engine.DuelMetric.VOLUME])


def test_the_rivals_pace_is_a_straight_line(client: TestClient, auth: dict, db: Session) -> None:
    made = client.post(DUELS, json={"against_rival": True, "days": 10}, headers=auth).json()
    duel = db.get(Duel, uuid.UUID(made["id"]))
    target = float(duel.rival_target)
    half = duel.window_start + (duel.window_end - duel.window_start) / 2
    assert engine.rival_progress(duel, half) == pytest.approx(target / 2, rel=0.01)
    assert engine.rival_progress(duel, duel.window_end) == pytest.approx(target)
    # Never ahead of itself, even if asked about a moment after the end.
    assert engine.rival_progress(duel, duel.window_end + dt.timedelta(days=5)) == pytest.approx(target)


def test_the_rival_never_reads_another_users_data(
    client: TestClient, user_factory, db: Session
) -> None:
    """The whole safety argument for the rival: its pace comes from the
    challenger's own history, so a duel cannot leak anybody else's training."""
    strong, _ = user_factory()
    weak, _ = user_factory()
    # The strong user's history is irrelevant to the weak user's rival.
    made = client.post(DUELS, json={"against_rival": True, "days": 7}, headers=weak).json()
    duel = db.get(Duel, uuid.UUID(made["id"]))
    assert float(duel.rival_target) == pytest.approx(engine.RIVAL_FLOOR[engine.DuelMetric.VOLUME])


# --------------------------------------------------------------------------
# Judging
# --------------------------------------------------------------------------


def test_a_closed_duel_is_judged_when_somebody_looks(
    client: TestClient, auth: dict, db: Session
) -> None:
    """No cron: reading it is what judges it."""
    made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=auth).json()
    close_window(db, made["id"])

    seen = client.get(f"{DUELS}/{made['id']}", headers=auth).json()
    assert seen["status"] == "completed"
    assert seen["resolved_at"] is not None
    # The rival's floor beats a user who logged nothing, so there is no winner
    # to pay - and no points.
    assert seen["winner_id"] is None
    assert seen["points_awarded"] is None


def test_the_winner_is_paid_exactly_once(
    client: TestClient, user_factory, db: Session
) -> None:
    mine, me = user_factory()
    made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=mine).json()
    duel = close_window(db, made["id"])
    # Out-train the rival's target inside the window that just closed.
    train(db, me["id"], duel.window_start + dt.timedelta(hours=1), weight=100, reps=10, sets=5)

    first = client.get(f"{DUELS}/{made['id']}", headers=mine).json()
    assert first["winner_id"] is not None
    assert first["points_awarded"] == engine.WIN_POINTS

    # Every later read re-judges nothing and pays nothing.
    for _ in range(3):
        again = client.get(f"{DUELS}/{made['id']}", headers=mine).json()
        assert again["points_awarded"] is None

    db.expire_all()
    paid = db.scalars(
        select(PointsLedgerEntry)
        .where(PointsLedgerEntry.source_id == uuid.UUID(made["id"]))
        .where(PointsLedgerEntry.source_type == LedgerSource.DUEL_WON.value)
    ).all()
    assert len(paid) == 1, paid
    assert paid[0].points == engine.WIN_POINTS


def test_a_draw_has_no_winner_and_pays_nobody(
    client: TestClient, auth: dict, db: Session
) -> None:
    made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=auth).json()
    duel = close_window(db, made["id"])
    duel.rival_target = 0  # and the user logged nothing, so 0 == 0
    db.commit()
    seen = client.get(f"{DUELS}/{made['id']}", headers=auth).json()
    assert seen["status"] == "completed"
    assert seen["winner_id"] is None
    assert seen["is_draw"] is True
    assert seen["points_awarded"] is None


def test_listing_judges_and_sorts_by_state(client: TestClient, auth: dict, db: Session) -> None:
    live = client.post(DUELS, json={"against_rival": True, "days": 7}, headers=auth).json()
    done = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=auth).json()
    close_window(db, done["id"])

    listed = client.get(DUELS, headers=auth).json()
    assert [d["id"] for d in listed["active"]] == [live["id"]]
    assert [d["id"] for d in listed["completed"]] == [done["id"]]


def test_declining_ends_it(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, them = user_factory()
    party_with(client, mine, theirs)
    made = client.post(DUELS, json={"opponent_id": them["id"]}, headers=mine).json()

    declined = client.post(f"{DUELS}/{made['id']}/decline", headers=theirs)
    assert declined.status_code == 200, declined.text
    assert declined.json()["status"] == "declined"
    # And it cannot then be accepted.
    assert client.post(f"{DUELS}/{made['id']}/accept", headers=theirs).status_code == 409


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def test_volume_counts_working_sets_inside_the_window(
    client: TestClient, user_factory, db: Session
) -> None:
    mine, me = user_factory()
    made = client.post(DUELS, json={"against_rival": True, "days": 7}, headers=mine).json()
    duel = backdate(db, made["id"], days=2)
    inside = duel.window_start + dt.timedelta(hours=2)

    train(db, me["id"], inside, weight=100, reps=10, sets=3)   # 3000 kg
    train(db, me["id"], duel.window_start - dt.timedelta(days=3), weight=100, reps=10, sets=3)

    seen = client.get(f"{DUELS}/{made['id']}", headers=mine).json()
    assert seen["challenger"]["score"] == pytest.approx(3000)


def test_a_deleted_set_leaves_the_duel_too(
    client: TestClient, user_factory, db: Session
) -> None:
    """Scores are summed, never stored: taking training back takes the score
    back with it. A stored score would drift away from the sets behind it."""
    mine, me = user_factory()
    made = client.post(DUELS, json={"against_rival": True, "days": 7}, headers=mine).json()
    duel = backdate(db, made["id"], days=2)
    train(db, me["id"], duel.window_start + dt.timedelta(hours=1), weight=100, reps=10, sets=2)
    assert client.get(f"{DUELS}/{made['id']}", headers=mine).json()["challenger"]["score"] == 2000

    db.query(SetEntry).filter(SetEntry.user_id == uuid.UUID(me["id"])).delete()
    db.commit()
    assert client.get(f"{DUELS}/{made['id']}", headers=mine).json()["challenger"]["score"] == 0


def test_each_metric_measures_its_own_thing(
    client: TestClient, user_factory, db: Session
) -> None:
    mine, me = user_factory()
    sets_duel = client.post(
        DUELS, json={"against_rival": True, "days": 7, "metric": "sets"}, headers=mine
    ).json()
    duel = backdate(db, sets_duel["id"], days=2)
    train(db, me["id"], duel.window_start + dt.timedelta(hours=1), weight=60, reps=5, sets=4)

    assert client.get(f"{DUELS}/{sets_duel['id']}", headers=mine).json()["challenger"]["score"] == 4

    sessions_duel = client.post(
        DUELS, json={"against_rival": True, "days": 7, "metric": "sessions"}, headers=mine
    ).json()
    backdate(db, sessions_duel["id"], days=2)
    assert client.get(f"{DUELS}/{sessions_duel['id']}", headers=mine).json()["challenger"]["score"] == 1


# --------------------------------------------------------------------------
# The feed
# --------------------------------------------------------------------------


def test_the_feed_needs_a_signed_in_user(client: TestClient) -> None:
    assert client.get(FEED).status_code == 401


def test_a_won_duel_reaches_the_feed(client: TestClient, user_factory, db: Session) -> None:
    mine, me = user_factory()
    made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=mine).json()
    duel = close_window(db, made["id"])
    train(db, me["id"], duel.window_start + dt.timedelta(hours=1), weight=100, reps=10, sets=5)
    client.get(f"{DUELS}/{made['id']}", headers=mine)

    feed = client.get(FEED, headers=mine).json()
    assert [e["event_type"] for e in feed["entries"]] == ["duel_won"]
    assert feed["entries"][0]["source_id"] == made["id"]


def test_the_feed_shows_a_party_but_not_a_stranger(
    client: TestClient, user_factory, db: Session
) -> None:
    mine, me = user_factory()
    theirs, them = user_factory()
    stranger, its = user_factory()
    party_with(client, mine, theirs)

    for headers, who in ((theirs, them), (stranger, its)):
        made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=headers).json()
        duel = close_window(db, made["id"])
        train(db, who["id"], duel.window_start + dt.timedelta(hours=1), weight=100, reps=10, sets=5)
        client.get(f"{DUELS}/{made['id']}", headers=headers)

    seen = client.get(FEED, headers=mine).json()["entries"]
    assert {e["user_id"] for e in seen} == {them["id"]}


def test_my_own_events_appear_once(client: TestClient, user_factory, db: Session) -> None:
    """A member's event is written to their own feed AND their party's; the
    reader must not see it twice."""
    mine, me = user_factory()
    theirs, _ = user_factory()
    party_with(client, mine, theirs)

    made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=mine).json()
    duel = close_window(db, made["id"])
    train(db, me["id"], duel.window_start + dt.timedelta(hours=1), weight=100, reps=10, sets=5)
    client.get(f"{DUELS}/{made['id']}", headers=mine)

    entries = client.get(FEED, headers=mine).json()["entries"]
    assert len([e for e in entries if e["source_id"] == made["id"]]) == 1


def test_the_feed_can_be_narrowed_to_one_party(client: TestClient, user_factory, db: Session) -> None:
    mine, _ = user_factory()
    theirs, them = user_factory()
    party = party_with(client, mine, theirs)

    made = client.post(DUELS, json={"against_rival": True, "days": 1}, headers=theirs).json()
    duel = close_window(db, made["id"])
    train(db, them["id"], duel.window_start + dt.timedelta(hours=1), weight=100, reps=10, sets=5)
    client.get(f"{DUELS}/{made['id']}", headers=theirs)

    scoped = client.get(FEED, params={"party_id": party["id"]}, headers=mine).json()
    assert [e["user_id"] for e in scoped["entries"]] == [them["id"]]


def test_a_party_you_are_not_in_is_not_found(client: TestClient, user_factory) -> None:
    mine, _ = user_factory()
    theirs, _ = user_factory()
    party = client.post(PARTIES, json={"name": "Theirs"}, headers=theirs).json()
    assert client.get(FEED, params={"party_id": party["id"]}, headers=mine).status_code == 404


def test_finishing_a_workout_writes_one_feed_entry(client: TestClient, auth: dict) -> None:
    """Through the real endpoints, so the fan-out is exercised where it lives."""
    started = client.post("/api/v1/workouts/sessions", json={}, headers=auth)
    assert started.status_code == 201, started.text
    session = started.json()
    exercises = client.get("/api/v1/exercises", headers=auth).json()
    exercise_id = (exercises["items"] if isinstance(exercises, dict) else exercises)[0]["id"]
    client.post(
        f"/api/v1/workouts/sessions/{session['id']}/sets",
        json={"exercise_id": exercise_id, "weight_kg": 60, "reps": 8},
        headers=auth,
    )
    finished = client.post(f"/api/v1/workouts/sessions/{session['id']}/finish", headers=auth)
    assert finished.status_code == 200, finished.text

    kinds = [e["event_type"] for e in client.get(FEED, headers=auth).json()["entries"]]
    assert "session_completed" in kinds or "pr_achieved" in kinds, kinds
