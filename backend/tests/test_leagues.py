"""Weekly leagues (app/core/leagues.py): a placement made on first access,
standings summed from the points ledger, promotion and relegation judged when
the next week is asked for, and a league that fills opening another."""

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import leagues, raids
from app.models.league import LeagueMembership
from app.models.workout import PointsLedgerEntry
from app.models.workout_enums import LedgerSource

CURRENT = "/api/v1/leagues/current"
ME = "/api/v1/auth/me"


def user_id(client: TestClient, headers: dict) -> uuid.UUID:
    return uuid.UUID(client.get(ME, headers=headers).json()["id"])


def league(client: TestClient, headers: dict) -> dict:
    r = client.get(CURRENT, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def award(db: Session, user: uuid.UUID, points: int, when: dt.datetime) -> None:
    """A ledger entry inside a chosen week - what a league actually scores."""
    db.add(
        PointsLedgerEntry(
            user_id=user,
            source_type=LedgerSource.SET_LOGGED.value,
            source_id=uuid.uuid4(),
            points=points,
            reason="test award",
            created_at=when,
        )
    )
    db.flush()


def place(db: Session, user: uuid.UUID, week_key: str, division: int, group_no: int = 0) -> None:
    db.add(
        LeagueMembership(
            user_id=user, week_key=week_key, division=division, group_no=group_no
        )
    )
    db.flush()


def last_week(now: dt.datetime | None = None) -> str:
    return leagues.previous_week(raids.week_key(now or dt.datetime.now(dt.timezone.utc)))


def test_a_first_league_starts_in_bronze(client: TestClient, auth: dict) -> None:
    board = league(client, auth)
    assert board["division"] == 0
    assert board["division_label"] == "Bronze"
    assert board["promoted_from"] is None
    assert board["promote_cutoff"] == leagues.PROMOTE
    [me] = board["entries"]
    assert me["is_me"] and me["position"] == 1 and me["points"] == 0
    # The week ends on the next Monday, in UTC.
    assert board["ends_at"].startswith(str(raids.week_start(board["week_key"]).year))


def test_this_weeks_points_order_the_board(
    client: TestClient, user_factory, db: Session
) -> None:
    quiet, _ = user_factory()
    loud, _ = user_factory()
    # Both ask, so both are placed in the same Bronze league.
    league(client, quiet)
    league(client, loud)

    now = dt.datetime.now(dt.timezone.utc)
    award(db, user_id(client, loud), 120, now)
    award(db, user_id(client, quiet), 40, now)
    db.commit()

    board = league(client, quiet)
    assert [e["points"] for e in board["entries"]] == [120, 40]
    assert board["entries"][0]["display_name"] == client.get(ME, headers=loud).json()["display_name"]
    assert board["entries"][1]["is_me"]


def test_a_reversal_never_drags_a_score_below_zero(
    client: TestClient, auth: dict, db: Session
) -> None:
    league(client, auth)
    me = user_id(client, auth)
    now = dt.datetime.now(dt.timezone.utc)
    award(db, me, 10, now)
    db.add(
        PointsLedgerEntry(
            user_id=me,
            source_type=LedgerSource.REVERSAL.value,
            source_id=uuid.uuid4(),
            points=-50,
            reason="reversal of an older award",
            created_at=now,
        )
    )
    db.commit()

    assert league(client, auth)["entries"][0]["points"] == 0


def test_finishing_at_the_top_promotes_the_next_week(
    client: TestClient, auth: dict, db: Session
) -> None:
    me = user_id(client, auth)
    previous = last_week()
    place(db, me, previous, division=0)
    award(db, me, 300, raids.week_start(previous) + dt.timedelta(days=1))
    db.commit()

    board = league(client, auth)
    assert board["division"] == 1
    assert board["division_label"] == "Silver"
    # It also says where that came from, so the client can celebrate it.
    assert board["promoted_from"] == 1


def test_finishing_at_the_bottom_relegates(
    client: TestClient, user_factory, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # One up, one down, so a two-person league settles it.
    monkeypatch.setattr(leagues, "PROMOTE", 1)
    monkeypatch.setattr(leagues, "DEMOTE", 1)
    winner, _ = user_factory()
    loser, _ = user_factory()
    previous = last_week()
    place(db, user_id(client, winner), previous, division=2)
    place(db, user_id(client, loser), previous, division=2)
    award(db, user_id(client, winner), 500, raids.week_start(previous) + dt.timedelta(days=1))
    db.commit()

    assert league(client, loser)["division"] == 1
    assert league(client, winner)["division"] == 3


def test_asking_twice_keeps_one_placement(
    client: TestClient, auth: dict, db: Session
) -> None:
    first = league(client, auth)
    second = league(client, auth)
    assert (first["division"], first["group_no"]) == (second["division"], second["group_no"])
    assert db.scalar(select(func.count(LeagueMembership.id))) == 1


def test_a_full_league_opens_another(
    client: TestClient, user_factory, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(leagues, "LEAGUE_SIZE", 2)
    boards = []
    for _ in range(3):
        headers, _ = user_factory()
        boards.append(league(client, headers))
    assert [b["group_no"] for b in boards] == [0, 0, 1]
    # The third lifter sees their own league, not the full one.
    assert len(boards[2]["entries"]) == 1
