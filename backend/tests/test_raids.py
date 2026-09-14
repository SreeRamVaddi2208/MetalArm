"""Weekly party raids (app/core/raids.py): a boss sized to the party, damage
from qualified workouts, one hit per session, healing on idle days, a boss
that stays down once beaten, and a new boss every week."""

import datetime as dt
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import raids
from app.models.party import Party
from app.models.raid import RaidHit
from tests.test_workouts import exercise_id, finish, full_workout, log, start

PARTIES = "/api/v1/parties"
# A Friday: Monday to Thursday of its ISO week (2026-W37) are before it.
FRIDAY = dt.datetime(2026, 9, 11, 12, 0, tzinfo=dt.timezone.utc)


def make_party(client: TestClient, owner: dict, *members: dict) -> dict:
    r = client.post(PARTIES, json={"name": "Iron Crew"}, headers=owner)
    assert r.status_code == 201, r.text
    party = r.json()
    for member in members:
        joined = client.post(f"{PARTIES}/join", json={"invite_code": party["invite_code"]}, headers=member)
        assert joined.status_code == 200, joined.text
    return party


def raid(client: TestClient, headers: dict, party: dict) -> dict:
    r = client.get(f"{PARTIES}/{party['id']}/raid", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_party_faces_a_boss_sized_to_its_members(client: TestClient, user_factory) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner, member)

    boss = raid(client, owner, party)
    assert boss["name"] in raids.BOSS_NAMES
    assert boss["max_hp"] == 2 * raids.HP_PER_MEMBER_KG
    # Healing never takes a boss above its max.
    assert boss["hp_remaining"] == boss["max_hp"]
    assert boss["hitters"] == []
    assert not boss["defeated"]


def test_a_qualified_workout_hits_the_boss_for_its_volume(
    client: TestClient, user_factory, db: Session
) -> None:
    owner, _ = user_factory()
    party = make_party(client, owner)

    # 3 x (100 kg x 5) = 1500 kg lifted.
    result = full_workout(client, owner, db, exercise_id(client, owner))
    assert result["qualified"]
    [hit] = result["raids"]
    assert hit["damage"] == 1500
    assert hit["party_id"] == party["id"]

    boss = raid(client, owner, party)
    assert boss["damage_dealt"] == 1500
    assert boss["hitters"][0]["damage"] == 1500
    assert boss["hitters"][0]["hits"] == 1
    assert boss["hitters"][0]["is_me"]


def test_a_short_workout_deals_no_damage(client: TestClient, user_factory) -> None:
    owner, _ = user_factory()
    party = make_party(client, owner)
    session = start(client, owner)
    log(client, owner, session["id"], exercise_id(client, owner))

    result = finish(client, owner, session["id"])
    assert not result["qualified"]
    assert result["raids"] == []
    assert raid(client, owner, party)["damage_dealt"] == 0


def test_a_light_session_still_lands_the_minimum_hit(
    client: TestClient, user_factory, db: Session
) -> None:
    owner, _ = user_factory()
    make_party(client, owner)
    result = full_workout(client, owner, db, exercise_id(client, owner), sets=((20, 5),) * 3)
    assert result["raids"][0]["damage"] == raids.MIN_HIT


def test_a_session_hits_each_boss_once(client: TestClient, user_factory, db: Session) -> None:
    owner, me = user_factory()
    party = make_party(client, owner)
    result = full_workout(client, owner, db, exercise_id(client, owner))

    # The same workout landing again (a retried finish) changes nothing.
    again = raids.hit_parties(
        db,
        user_id=uuid.UUID(me["id"]),
        session_id=uuid.UUID(result["session"]["id"]),
        volume=1500,
        now=dt.datetime.now(dt.timezone.utc),
    )
    assert again == []
    assert raid(client, owner, party)["damage_dealt"] == 1500


def test_idle_days_heal_the_boss(client: TestClient, user_factory, db: Session) -> None:
    owner, me = user_factory()
    party_row = db.get(Party, uuid.UUID(make_party(client, owner)["id"]))
    boss = raids.current_boss(db, party_row, FRIDAY)
    assert boss.max_hp == raids.HP_PER_MEMBER_KG

    # No hits all week: Monday to Thursday are idle, 5% each.
    boss.damage = 9_000
    assert raids.idle_days(db, boss, FRIDAY) == 4
    assert raids.hp_remaining(db, boss, FRIDAY) == 15_000 - 9_000 + 3_000

    # A hit on Tuesday makes Tuesday an active day.
    session = start(client, owner)
    db.add(
        RaidHit(
            boss_id=boss.id,
            user_id=uuid.UUID(me["id"]),
            session_id=uuid.UUID(session["id"]),
            damage=1_000,
            created_at=FRIDAY - dt.timedelta(days=3),
        )
    )
    db.flush()
    assert raids.idle_days(db, boss, FRIDAY) == 3
    assert raids.hp_remaining(db, boss, FRIDAY) == 15_000 - 9_000 + 2_250


def test_a_beaten_boss_stays_down(client: TestClient, user_factory, db: Session) -> None:
    owner, me = user_factory()
    party_row = db.get(Party, uuid.UUID(make_party(client, owner)["id"]))
    session = start(client, owner)

    [hit] = raids.hit_parties(
        db, user_id=uuid.UUID(me["id"]), session_id=uuid.UUID(session["id"]), volume=20_000, now=FRIDAY
    )
    assert hit["defeated_now"]
    assert hit["hp_remaining"] == 0

    # Idle days after its defeat don't bring it back.
    boss = raids.current_boss(db, party_row, FRIDAY)
    sunday = FRIDAY + dt.timedelta(days=2)
    assert raids.hp_remaining(db, boss, sunday) == 0
    assert raids.raid_view(db, party_row, uuid.UUID(me["id"]), sunday)["defeated"]


def test_each_week_brings_a_new_boss(client: TestClient, user_factory, db: Session) -> None:
    owner, _ = user_factory()
    party_row = db.get(Party, uuid.UUID(make_party(client, owner)["id"]))

    this_week = raids.current_boss(db, party_row, FRIDAY)
    assert raids.current_boss(db, party_row, FRIDAY + dt.timedelta(days=1)).id == this_week.id
    next_week = raids.current_boss(db, party_row, FRIDAY + dt.timedelta(days=7))
    assert next_week.id != this_week.id
    assert next_week.week_key == "2026-W38"
    assert next_week.damage == 0


def test_only_members_see_the_raid(client: TestClient, user_factory) -> None:
    owner, _ = user_factory()
    outsider, _ = user_factory()
    party = make_party(client, owner)
    assert client.get(f"{PARTIES}/{party['id']}/raid", headers=outsider).status_code == 404
