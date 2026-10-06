#!/usr/bin/env python3
"""The performance budget's dataset: one account with two years of four
workouts a week, then every clarity read timed against it.

    docker compose run --rm -v "$PWD/backend/scripts:/app/scripts" backend \\
        python -m scripts.seed_load --email load@metalarm.dev --password ...

The overhaul's budget is p95 under 200 ms per read endpoint on exactly this
shape of account. Writes straight to the tables (as seed_demo does), rebuilds
records and the finish totals, then calls each endpoint 20 times through the
API and prints p50 / p95. Exits non-zero if any p95 is over budget.
Refuses to run in production.
"""

from __future__ import annotations

import argparse
import datetime as dt
import statistics
import sys
import time
import urllib.request
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import engine
from scripts.seed_demo import API, NOW, PLAN, account, call, rebuild_records, train

WEEKS = 104
DAYS = [0, 1, 3, 5]
BUDGET_MS = 200
RUNS = 20


def timed(path: str, token: str) -> list[float]:
    out = []
    for _ in range(RUNS):
        request = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
        out.append((time.perf_counter() - start) * 1000)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()
    if get_settings().environment == "production":
        print("Refusing to seed load data into production.", file=sys.stderr)
        return 1

    user_id, token = account(args.email, args.password, "Load Test", "powerlifter")
    with Session(engine) as db:
        uid = uuid.UUID(user_id)
        for back in range(WEEKS, 0, -1):
            monday = NOW - dt.timedelta(days=NOW.weekday() + 7 * back)
            for i, offset in enumerate(DAYS):
                name, lifts = PLAN[i % len(PLAN)]
                train(db, uid, monday + dt.timedelta(days=offset), name, lifts, 1 + (WEEKS - back) * 0.004)
        rebuild_records(db, uid)
        db.commit()
    print(f"seeded {WEEKS * len(DAYS)} workouts")

    exercise = call("GET", "/me/exercises?limit=1", token=token)["items"][0]["exercise_id"]
    paths = ["/analytics/snapshot", "/analytics/series?metric=volume&range=All",
             "/analytics/series?metric=points&range=All", "/analytics/muscles", "/analytics/calendar",
             "/analytics/recovery", "/history", "/me/exercises", f"/exercises/{exercise}/stats?range=All",
             "/workouts/suggested", "/library?filter=routines"]
    over = []
    for path in paths:
        ms = sorted(timed(path, token))
        p95 = ms[int(len(ms) * 0.95) - 1]
        print(f"{path:48s} p50 {statistics.median(ms):6.1f} ms   p95 {p95:6.1f} ms")
        if p95 > BUDGET_MS:
            over.append(path)
    if over:
        print("over budget:", ", ".join(over))
        return 1
    print(f"every read under {BUDGET_MS} ms p95")
    return 0


if __name__ == "__main__":
    sys.exit(main())
