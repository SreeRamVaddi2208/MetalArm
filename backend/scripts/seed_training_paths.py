#!/usr/bin/env python3
"""Upsert the training paths from app/data/training_categories.json.

Run on every deploy, beside the exercise library:

    docker compose run --rm tests python -m scripts.seed_training_paths

The rows are tuning - rep ranges, load, volume, rest - so editing the file and
deploying is how they change. Idempotent: a run that changes nothing writes
nothing, and a path is never deleted here, because users point at it.
"""

import sys

from sqlalchemy.orm import Session

from app.core import training_categories
from app.db.session import engine


def main() -> int:
    with Session(engine) as db:
        written = training_categories.seed(db)
        db.commit()
    total = len(training_categories.definitions())
    print(f"training paths: {written} written, {total - written} already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
