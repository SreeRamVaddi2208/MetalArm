#!/usr/bin/env python3
"""Seed a demo account rich enough to show every MetalArm feature on camera.

Development only - it refuses to run with ENVIRONMENT=production. Used by the
demo recorder (scripts/dev.sh record web), against a database of its own:

    POSTGRES_DB=metalarm_demo docker compose run --rm backend \\
        python -m scripts.seed_demo --email hero@metalarm.dev --password ...

Live actions go through the real API (accounts, the party, rewards, quests,
body weight, duel challenges), so they take exactly the paths a user's would.
Only HISTORY is written straight to the tables, because the API stamps
everything "now" and a demo needs eight weeks behind it: backdated sessions
(rebuilt into records with the same replay the app uses), a week a freeze
covered, and one duel that has already ended - judged by the tour's first
read, which is the moment the result screen is for.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import activity, leveling
from app.core import workout_store as store
from app.core import workout_streaks as streaks
from app.core.config import get_settings
from app.db.session import engine
from app.models.duel import ActivityType, BaselineType, Duel, DuelBaseline, DuelStatus
from app.models.user import LevelProgress, User
from app.models.workout import Exercise, PointsLedgerEntry, SetEntry, WorkoutSession
from app.models.workout_enums import LedgerSource, SessionStatus

API = "http://backend:8000/api/v1"
NOW = dt.datetime.now(dt.timezone.utc)

# What a week of training looks like: (session name, [(slug, sets, reps, base kg)]).
PLAN = [
    ("Squat day", [("back-squat", 4, 5, 110), ("romanian-deadlift", 3, 8, 80), ("leg-extension", 3, 12, 45)]),
    ("Bench day", [("barbell-bench-press", 4, 5, 82.5), ("overhead-press", 3, 6, 47.5), ("barbell-row", 3, 8, 70)]),
    ("Pull day", [("deadlift", 3, 4, 150), ("lat-pulldown", 3, 10, 60), ("barbell-curl", 3, 10, 30)]),
]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def call(method: str, path: str, body: dict | None = None, token: str = "") -> dict | list | None:
    request = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} -> {exc.code}: {exc.read().decode()[:300]}") from None


def account(email: str, password: str, name: str, path: str) -> tuple[str, str]:
    """(user id, token). Signs up, or signs in if the account already exists."""
    try:
        call("POST", "/auth/signup", {"email": email, "password": password, "display_name": name, "timezone": "UTC"})
    except SystemExit as exc:
        if "409" not in str(exc) and "already" not in str(exc).lower():
            raise
    token = call("POST", "/auth/login", {"email": email, "password": password})["access_token"]
    me = call("PATCH", "/auth/me", {"character_class": path}, token)
    return me["id"], token


# ---------------------------------------------------------------------------
# History, written to the tables
# ---------------------------------------------------------------------------


def week_monday(weeks_back: int) -> dt.datetime:
    today = NOW.date()
    monday = today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=weeks_back)
    return dt.datetime.combine(monday, dt.time(18, 0), tzinfo=dt.timezone.utc)


def train(db: Session, user_id: uuid.UUID, at: dt.datetime, name: str, lifts, growth: float) -> None:
    """One finished, qualified workout at `at`, with its session-bonus ledger row."""
    ids = {e.slug: e.id for e in db.scalars(select(Exercise).where(Exercise.slug.in_([l[0] for l in lifts])))}
    session = WorkoutSession(
        user_id=user_id, name=name, started_at=at - dt.timedelta(minutes=55), ended_at=at,
        status=SessionStatus.COMPLETED.value, qualified=True,
        week_key=streaks.week_key(at, "UTC"),
    )
    db.add(session)
    db.flush()
    minute = 0
    for slug, sets, reps, base in lifts:
        weight = Decimal(str(round(base * growth / 2.5) * 2.5))
        for number in range(1, sets + 1):
            minute += 3
            db.add(SetEntry(
                session_id=session.id, user_id=user_id, exercise_id=ids[slug], set_number=number,
                weight_kg=weight, reps=reps, is_warmup=False,
                completed_at=session.started_at + dt.timedelta(minutes=minute),
            ))
    db.add(PointsLedgerEntry(
        user_id=user_id, source_type=LedgerSource.SESSION_COMPLETED.value, source_id=session.id,
        points=42, session_id=session.id, reason="Workout completed", created_at=at,
    ))
    session.points_credited = 42


def history(db: Session, user_id: uuid.UUID, *, short_week: int | None, strength: float) -> None:
    """Eight weeks back to last week, three sessions a week, getting stronger -
    except `short_week`, which gets one session (a freeze covers it)."""
    for back in range(8, 0, -1):
        monday = week_monday(back)
        days = [0] if back == short_week else [0, 2, 4]
        for i, offset in enumerate(days):
            name, lifts = PLAN[i % len(PLAN)]
            growth = strength * (1 + (8 - back) * 0.012)
            train(db, user_id, monday + dt.timedelta(days=offset), name, lifts, growth)


def this_week(db: Session, user_id: uuid.UUID, strength: float, days_back: list[int]) -> None:
    for i, back in enumerate(days_back):
        name, lifts = PLAN[i % len(PLAN)]
        train(db, user_id, NOW - dt.timedelta(days=back, hours=2), name, lifts, strength * 1.1)


def rebuild_records(db: Session, user_id: uuid.UUID) -> None:
    db.flush()
    for exercise_id in set(db.scalars(select(SetEntry.exercise_id).where(SetEntry.user_id == user_id))):
        store.replay_exercise(db, user_id, exercise_id)
    # The totals finish would have written: the clarity screens read them.
    store.write_totals(db, list(db.scalars(select(WorkoutSession).where(
        WorkoutSession.user_id == user_id, WorkoutSession.status == SessionStatus.COMPLETED.value))))


def progress(db: Session, user_id: uuid.UUID, xp: int, points: int, streak: int) -> None:
    row = db.get(LevelProgress, user_id)
    row.total_xp = xp
    row.current_level = leveling.level_for_xp(xp)
    row.points_balance = points
    row.current_streak = row.longest_streak = streak
    row.last_completed_on = (NOW - dt.timedelta(days=1)).date()
    row.rank = leveling.rank_for(row.current_level, streak, row.trials_passed)


def finished_progress_duel(db: Session, hero: uuid.UUID, rival: uuid.UUID) -> None:
    """A progress duel that ended yesterday, which the rival edged: the tour's
    first read judges it and shows the result screen."""
    start, end = NOW - dt.timedelta(days=8), NOW - dt.timedelta(days=1)
    duel = Duel(
        challenger_id=hero, opponent_id=rival, is_ai_opponent=False, metric="progress",
        window_start=start, window_end=end, status=DuelStatus.ACTIVE.value,
        created_at=start - dt.timedelta(hours=2),
    )
    db.add(duel)
    db.flush()
    bench = db.scalar(select(Exercise.id).where(Exercise.slug == "barbell-bench-press"))
    for user_id, base in ((hero, Decimal("100")), (rival, Decimal("80"))):
        db.add(DuelBaseline(duel_id=duel.id, user_id=user_id, exercise_id=bench,
                            baseline_type=BaselineType.E1RM.value, baseline_value=base))
    # Inside the window: the hero gains 3%, the rival 7%.
    for user_id, kg in ((hero, 87.5), (rival, 72.5)):
        train(db, user_id, start + dt.timedelta(days=2), "Bench day",
              [("barbell-bench-press", 3, 5, kg)], 1.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()
    if get_settings().environment == "production":
        print("Refusing to seed demo data into production.", file=sys.stderr)
        return 1

    stamp = uuid.uuid4().hex[:6]
    hero_id, hero = account(args.email, args.password, "MetalArm", "powerlifter")
    rival_id, rival = account(f"rival-{stamp}@metalarm.dev", args.password, "Maya", "athlete")
    third_id, third = account(f"crew-{stamp}@metalarm.dev", args.password, "Dev", "bodybuilder")
    # Joined this week, nothing logged yet: the duel picker shows which fair
    # modes need history, and says why.
    _, newcomer = account(f"new-{stamp}@metalarm.dev", args.password, "Sam", "athlete")

    # --- History -----------------------------------------------------------
    with Session(engine) as db:
        uid = {name: uuid.UUID(value) for name, value in
               (("hero", hero_id), ("rival", rival_id), ("third", third_id))}
        history(db, uid["hero"], short_week=2, strength=1.0)
        history(db, uid["rival"], short_week=None, strength=0.72)
        history(db, uid["third"], short_week=5, strength=0.85)
        this_week(db, uid["hero"], 1.0, [2, 1])
        this_week(db, uid["rival"], 0.72, [1])
        finished_progress_duel(db, uid["hero"], uid["rival"])
        for user_id in uid.values():
            rebuild_records(db, user_id)
        progress(db, uid["hero"], xp=5600, points=180, streak=6)
        progress(db, uid["rival"], xp=4100, points=90, streak=3)
        progress(db, uid["third"], xp=3300, points=60, streak=1)
        # Freezes settle from nine weeks back, so the first streak read earns
        # one at the 4-week mark and spends it on the short week - and the
        # dashboard opens on "your streak was saved".
        hero_user = db.get(User, uid["hero"])
        hero_user.freeze_settled_through = streaks.week_key(week_monday(9), "UTC")
        hero_user.streak_seen_at = None
        db.commit()

    # --- The party, through the API ------------------------------------------
    party = call("POST", "/parties", {"name": "Iron Syndicate"}, hero)
    for token in (rival, third, newcomer):
        call("POST", "/parties/join", {"invite_code": party["invite_code"]}, token)
    call("POST", f"/parties/{party['id']}/quests",
         {"title": "Everyone trains 3x this week", "xp_reward": 60, "recurrence": "weekly"}, hero)

    with Session(engine) as db:
        rival_user = db.get(User, uuid.UUID(rival_id))
        for headline in ("New record: Back Squat", "Finished Bench day", "Reached Advanced"):
            activity.record(db, user_id=rival_user.id,
                            event_type=ActivityType.PR_ACHIEVED if "record" in headline
                            else ActivityType.RANK_UP if "Reached" in headline
                            else ActivityType.SESSION_COMPLETED,
                            headline=headline, source_id=uuid.uuid4(),
                            at=NOW - dt.timedelta(hours=5))
        db.commit()

    # --- Everything else a user would make -----------------------------------
    for i, kg in enumerate((86.4, 85.9, 85.1, 84.6, 84.0, 83.7, 83.2, 82.8)):
        call("POST", "/body-measurements", {"metric": "weight", "value": kg, "unit": "kg",
                               "recorded_at": (NOW - dt.timedelta(days=7 * (7 - i))).isoformat()}, hero)
    for title, cost in (("Cheat meal", 120), ("New lifting straps", 300), ("Rest day, guilt-free", 80)):
        call("POST", "/rewards", {"title": title, "point_cost": cost}, hero)
    call("POST", "/quests", {"title": "Stretch for 10 minutes", "xp_reward": 40,
                              "points_reward": 10, "recurrence": "daily"}, hero)
    call("POST", "/quests", {"title": "Hit 8 hours of sleep", "xp_reward": 30, "recurrence": "daily"}, hero)
    call("GET", "/leagues/current", None, hero)
    call("GET", f"/parties/{party['id']}/raid", None, hero)

    # A live consistency duel with the rival, already a few days in...
    duel = call("POST", "/duels", {"opponent_id": rival_id, "metric": "consistency"}, hero)
    call("POST", f"/duels/{duel['id']}/accept", None, rival)
    with Session(engine) as db:
        row = db.get(Duel, uuid.UUID(duel["id"]))
        row.window_start = NOW - dt.timedelta(days=3)
        row.window_end = row.window_start + dt.timedelta(days=7)
        db.commit()
    # ...and a fresh challenge from the third member, waiting on the hero.
    call("POST", "/duels", {"opponent_id": hero_id, "metric": "relative_volume"}, third)

    print(json.dumps({"email": args.email, "hero_id": hero_id, "rival_id": rival_id,
                      "party_id": party["id"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
