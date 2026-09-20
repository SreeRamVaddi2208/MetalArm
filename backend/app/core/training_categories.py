"""Reading the training paths, and seeding them.

The rows are config that ships with the image (app/data/training_categories.json),
so they are seeded on deploy the same way the exercise library is, and read from
the database afterwards - which is what lets them be tuned without a release.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.training_category import TrainingCategoryProfile

CATEGORY_FILE = Path(__file__).resolve().parents[1] / "data" / "training_categories.json"

# The order the paths are offered in: easiest to see yourself in, first.
DISPLAY_ORDER = ["athlete", "bodybuilder", "powerlifter"]


def definitions() -> list[dict]:
    return json.loads(CATEGORY_FILE.read_text())


def all_profiles(db: Session) -> list[TrainingCategoryProfile]:
    """Every path, in display order. Falls back to the shipped definitions if
    the table has not been seeded, so a fresh database still offers the choice
    rather than showing an empty onboarding step."""
    rows = list(db.scalars(select(TrainingCategoryProfile)))
    if not rows:
        rows = [TrainingCategoryProfile(**record) for record in definitions()]
    order = {category: index for index, category in enumerate(DISPLAY_ORDER)}
    return sorted(rows, key=lambda row: order.get(row.category, len(order)))


def seed(db: Session) -> int:
    """Upsert the shipped definitions. Returns how many rows were written.
    Idempotent: run it on every deploy."""
    existing = {row.category: row for row in db.scalars(select(TrainingCategoryProfile))}
    written = 0
    for record in definitions():
        row = existing.get(record["category"])
        if row is None:
            db.add(TrainingCategoryProfile(**record))
            written += 1
            continue
        if any(getattr(row, field) != value for field, value in record.items()):
            for field, value in record.items():
                setattr(row, field, value)
            written += 1
    return written
