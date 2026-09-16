#!/usr/bin/env python3
"""Recompute cached level and rank for every user.

level_progress.current_level and .rank are CACHES of the curve in
app/core/leveling.py. total_xp is the source of truth, so retuning the curve
re-derives everyone correctly - but only once this has run. Until then the
cached columns still describe the old curve.

RUN THIS AFTER ANY CHANGE TO app/core/leveling.py.

    docker compose run --rm tests python -m scripts.recompute_progression --dry-run
    docker compose run --rm tests python -m scripts.recompute_progression

Lives under backend/ rather than the repo-root scripts/ because it imports the
app and talks to Postgres over the compose network. Root scripts/ holds
host-run tooling that only speaks HTTP (generate_api_contract.py).

Rank additionally depends on the user's streak, which is judged against their
LOCAL date - hence the join to users.timezone rather than a bare UPDATE -
and on the strength trials passed, read from level_progress.trials_passed.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import leveling
from app.core.periods import local_now
from app.db.session import engine
from app.models.user import LevelProgress, User


def recompute(dry_run: bool = False) -> int:
    changed = 0
    examined = 0

    with Session(engine) as db:
        rows = db.execute(
            select(LevelProgress, User).join(User, User.id == LevelProgress.user_id)
        ).all()

        for progress, user in rows:
            examined += 1
            today = local_now(user.timezone).date()

            new_level = leveling.level_for_xp(progress.total_xp)
            new_rank = leveling.rank_for(
                new_level,
                leveling.effective_streak(
                    progress.current_streak, progress.last_completed_on, today
                ),
                # Trials depend on lifts and bodyweight, not the curve, so the
                # stored letters stay valid (app/core/rank_trials.py).
                progress.trials_passed,
            )

            if new_level == progress.current_level and new_rank == progress.rank:
                continue

            print(
                f"  {user.email_normalized:<40} "
                f"level {progress.current_level:>4} -> {new_level:<4} "
                f"rank {progress.rank.value} -> {new_rank.value}"
            )
            changed += 1

            if not dry_run:
                progress.current_level = new_level
                progress.rank = new_rank

        if dry_run:
            db.rollback()
            print(f"\nDRY RUN - {changed} of {examined} rows would change. Nothing written.")
        else:
            db.commit()
            print(f"\nUpdated {changed} of {examined} rows.")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = parser.parse_args()

    print(
        f"Curve: BASE={leveling.XP_BASE} EXPONENT={leveling.XP_EXPONENT}  "
        f"ranks={[(lvl, r.value) for lvl, r in leveling.RANK_THRESHOLDS]}"
    )
    print(f"Streak gate: {({r.value: d for r, d in leveling.RANK_STREAK_REQUIREMENTS.items()})}\n")
    recompute(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
