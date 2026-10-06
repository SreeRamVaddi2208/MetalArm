#!/usr/bin/env python3
"""Upsert the generated-quest templates from app/data/quest_templates.json.

Run on every deploy, beside the exercise library and the training paths:

    docker compose run --rm tests python -m scripts.seed_quest_templates

Idempotent. A template removed from the file is deactivated, not deleted -
quests already handed out from it keep working.
"""

import sys

from sqlalchemy.orm import Session

from app.core import quest_templates
from app.db.session import engine


def main() -> int:
    try:
        total = len(quest_templates.definitions())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    with Session(engine) as db:
        written = quest_templates.seed(db)
        db.commit()
    print(f"quest templates: {written} written, {max(total - written, 0)} already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
