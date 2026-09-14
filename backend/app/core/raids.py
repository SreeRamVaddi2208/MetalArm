"""Weekly party raids.

Every week each party faces a boss. Its HP is set when the week's boss first
appears - HP_PER_MEMBER_KG of training volume per member - so a party where
everyone trains a few times a week brings it down. Every QUALIFIED workout a
member finishes hits the boss for the session's volume (kg lifted), with a
floor (MIN_HIT) so a bodyweight or cardio session still counts. A session
hits each boss at most once (unique on boss + session), so a retried finish
can never hit twice.

The boss strikes back on idle days: for each full day of the week so far on
which no member landed a hit, it heals HEAL_PER_IDLE_DAY of its max HP. That
is derived on read from the hits themselves - nothing is stored or scheduled
- and it stops once the boss is down. Raids never touch points or XP.

Weeks are ISO weeks in UTC: a party's members can live in different
timezones, and one boss needs one clock.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.party import Party, PartyMembership
from app.models.raid import RaidBoss, RaidHit
from app.models.user import User

BOSS_NAMES = (
    "Iron Golem",
    "Rust Wyrm",
    "Steel Hydra",
    "Titan of Plates",
    "Chrome Colossus",
    "Anvil Warden",
)
HP_PER_MEMBER_KG = 15_000
MIN_HIT = 1_000
HEAL_PER_IDLE_DAY = Decimal("0.05")


def week_key(now: dt.datetime) -> str:
    year, week, _ = now.astimezone(dt.timezone.utc).isocalendar()
    return f"{year}-W{week:02d}"


def week_start(key: str) -> dt.datetime:
    year, week = key.split("-W")
    monday = dt.date.fromisocalendar(int(year), int(week), 1)
    return dt.datetime.combine(monday, dt.time.min, tzinfo=dt.timezone.utc)


def boss_name(key: str) -> str:
    return BOSS_NAMES[int(key.split("-W")[1]) % len(BOSS_NAMES)]


def max_hp(member_count: int) -> int:
    return HP_PER_MEMBER_KG * max(1, member_count)


def damage_for(volume: Decimal | float) -> int:
    return max(MIN_HIT, int(round(float(volume))))


def current_boss(db: Session, party: Party, now: dt.datetime) -> RaidBoss:
    """This week's boss for the party, created on first sight. Two requests
    racing to create it both land on the same row (ON CONFLICT DO NOTHING)."""
    key = week_key(now)
    query = select(RaidBoss).where(RaidBoss.party_id == party.id, RaidBoss.week_key == key)
    boss = db.scalar(query)
    if boss is not None:
        return boss
    members = db.scalar(
        select(func.count()).select_from(PartyMembership).where(PartyMembership.party_id == party.id)
    )
    db.execute(
        insert(RaidBoss)
        .values(
            id=uuid.uuid4(),
            party_id=party.id,
            week_key=key,
            name=boss_name(key),
            max_hp=max_hp(members or 0),
            damage=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_raid_bosses_party_week")
    )
    return db.scalar(query)


def idle_days(db: Session, boss: RaidBoss, now: dt.datetime) -> int:
    """Full days of the boss's week before today on which nobody landed a hit."""
    start = week_start(boss.week_key).date()
    today = now.astimezone(dt.timezone.utc).date()
    elapsed = min((today - start).days, 7)
    if elapsed <= 0:
        return 0
    hit_days = {
        moment.astimezone(dt.timezone.utc).date()
        for moment in db.scalars(select(RaidHit.created_at).where(RaidHit.boss_id == boss.id))
    }
    week_so_far = {start + dt.timedelta(days=offset) for offset in range(elapsed)}
    return len(week_so_far - hit_days)


def healed(boss: RaidBoss, idle: int) -> int:
    return int(boss.max_hp * HEAL_PER_IDLE_DAY * idle)


def hp_remaining(db: Session, boss: RaidBoss, now: dt.datetime) -> int:
    if boss.defeated_at is not None:
        return 0
    idle = idle_days(db, boss, now)
    return max(0, min(boss.max_hp, boss.max_hp - boss.damage + healed(boss, idle)))


def hit_parties(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    volume: Decimal | float,
    now: dt.datetime,
) -> list[dict[str, Any]]:
    """Land a finished workout on the boss of every active party the user is
    in. Returns one entry per boss actually hit (none for a repeat)."""
    damage = damage_for(volume)
    parties = db.scalars(
        select(Party)
        .join(PartyMembership, PartyMembership.party_id == Party.id)
        .where(PartyMembership.user_id == user_id, Party.is_active.is_(True))
    ).all()
    results = []
    for party in parties:
        boss = current_boss(db, party, now)
        landed = db.execute(
            insert(RaidHit)
            .values(
                id=uuid.uuid4(),
                boss_id=boss.id,
                user_id=user_id,
                session_id=session_id,
                damage=damage,
                created_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_raid_hits_boss_session")
        ).rowcount
        if not landed:
            continue
        was_down = boss.defeated_at is not None
        boss.damage += damage
        db.flush()
        if not was_down and hp_remaining(db, boss, now) == 0:
            boss.defeated_at = now
        results.append(
            {
                "party_id": party.id,
                "party_name": party.name,
                "boss_name": boss.name,
                "damage": damage,
                "hp_remaining": hp_remaining(db, boss, now),
                "defeated": boss.defeated_at is not None,
                "defeated_now": not was_down and boss.defeated_at is not None,
            }
        )
    db.flush()
    return results


def raid_view(db: Session, party: Party, viewer_id: uuid.UUID, now: dt.datetime) -> dict[str, Any]:
    """The party's raid this week, for GET /parties/{id}/raid."""
    boss = current_boss(db, party, now)
    idle = 0 if boss.defeated_at is not None else idle_days(db, boss, now)
    rows = db.execute(
        select(RaidHit.user_id, func.sum(RaidHit.damage), func.count(RaidHit.id))
        .where(RaidHit.boss_id == boss.id)
        .group_by(RaidHit.user_id)
    ).all()
    names = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_([row[0] for row in rows])))
    } if rows else {}
    hitters = sorted(
        (
            {
                "user_id": user_id,
                "display_name": names.get(user_id, "Former member"),
                "damage": int(total),
                "hits": int(count),
                "is_me": user_id == viewer_id,
            }
            for user_id, total, count in rows
        ),
        key=lambda hitter: (-hitter["damage"], hitter["display_name"].casefold()),
    )
    return {
        "party_id": party.id,
        "week_key": boss.week_key,
        "name": boss.name,
        "max_hp": boss.max_hp,
        "hp_remaining": hp_remaining(db, boss, now),
        "damage_dealt": boss.damage,
        "healed": healed(boss, idle),
        "idle_days": idle,
        "defeated": boss.defeated_at is not None,
        "defeated_at": boss.defeated_at,
        "ends_at": week_start(boss.week_key) + dt.timedelta(days=7),
        "hitters": hitters,
    }
