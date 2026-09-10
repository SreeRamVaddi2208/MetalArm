#!/usr/bin/env python3
"""Load the exercise library from a JSON or CSV seed file.

Idempotent: library exercises are keyed by `slug`, so re-running updates them
in place and inserting only what is new. Running it on every start (the compose
`migrate` service does) therefore costs nothing once the library is loaded.

    docker compose run --rm tests python -m scripts.import_exercises --dry-run
    docker compose run --rm tests python -m scripts.import_exercises
    docker compose run --rm tests python -m scripts.import_exercises --file big.csv

JSON: a list of objects with keys
    slug (optional - derived from name), name, category, primary_muscle_groups,
    equipment, instructions (optional), media_url (optional)
CSV: the same columns, with primary_muscle_groups separated by ';'.

Exercises in the database but missing from the file are REPORTED, never
deleted: sets and routines point at them, and a smaller seed file must not
erase anyone's history.

Every row is validated against the same enums the API uses before anything is
written, and the whole file is rejected if any row is bad - a half-imported
library is harder to reason about than none.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import pathlib
import sys

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exercise_names import clean_name, name_key, slugify
from app.db.session import engine
from app.models.workout import Exercise
from app.models.workout_enums import Equipment, ExerciseCategory, MuscleGroup

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_FILE = BACKEND_ROOT / "app" / "data" / "exercises.json"

_FIELDS = (
    "name",
    "name_key",
    "category",
    "primary_muscle_groups",
    "equipment",
    "instructions",
    "media_url",
)


class LibraryExercise(BaseModel):
    slug: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    category: ExerciseCategory
    primary_muscle_groups: list[MuscleGroup] = Field(min_length=1, max_length=6)
    equipment: Equipment
    instructions: str | None = None
    media_url: str | None = Field(default=None, max_length=500)

    def columns(self) -> dict[str, object]:
        return {
            "slug": self.slug or slugify(self.name),
            "name": clean_name(self.name),
            "name_key": name_key(self.name),
            "category": self.category.value,
            "primary_muscle_groups": [m.value for m in self.primary_muscle_groups],
            "equipment": self.equipment.value,
            "instructions": self.instructions or None,
            "media_url": self.media_url or None,
        }


@dataclasses.dataclass
class ImportReport:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    not_in_file: int = 0


def read_file(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("JSON seed must be a list of exercise objects")
        return data
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for row in rows:
            raw = row.get("primary_muscle_groups") or ""
            row["primary_muscle_groups"] = [m.strip() for m in raw.split(";") if m.strip()]
        return rows
    raise ValueError(f"unsupported seed file type: {path.suffix} (use .json or .csv)")


def parse(records: list[dict]) -> list[dict[str, object]]:
    """Validate every record and check the file against itself.

    Raises ValueError naming each bad row, rather than stopping at the first.
    """
    errors: list[str] = []
    rows: list[dict[str, object]] = []
    for index, record in enumerate(records, start=1):
        try:
            rows.append(LibraryExercise.model_validate(record).columns())
        except ValidationError as exc:
            label = record.get("name") or record.get("slug") or f"row {index}"
            errors.append(f"  {label}: {exc.errors()[0]['msg']} ({exc.errors()[0]['loc']})")

    for key in ("slug", "name_key"):
        seen: set[object] = set()
        for row in rows:
            if row[key] in seen:
                errors.append(f"  duplicate {key}: {row[key]}")
            seen.add(row[key])

    if errors:
        raise ValueError("seed file rejected:\n" + "\n".join(errors))
    return rows


def import_exercises(db: Session, records: list[dict]) -> ImportReport:
    """Upsert library exercises. Does not commit - the caller owns that."""
    rows = parse(records)
    existing = {
        ex.slug: ex
        for ex in db.execute(select(Exercise).where(Exercise.is_custom.is_(False))).scalars()
    }

    report = ImportReport()
    for row in rows:
        current = existing.get(row["slug"])
        if current is None:
            db.add(Exercise(is_custom=False, **row))
            report.inserted += 1
            continue
        changed = False
        for field in _FIELDS:
            if getattr(current, field) != row[field]:
                setattr(current, field, row[field])
                changed = True
        if changed:
            report.updated += 1
        else:
            report.unchanged += 1

    file_slugs = {row["slug"] for row in rows}
    report.not_in_file = sum(1 for slug in existing if slug not in file_slugs)
    db.flush()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", type=pathlib.Path, default=DEFAULT_FILE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        records = read_file(args.file)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    with Session(engine) as db:
        try:
            report = import_exercises(db, records)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    prefix = "DRY RUN - would have: " if args.dry_run else ""
    print(
        f"{prefix}exercise library from {args.file.name}: "
        f"{report.inserted} inserted, {report.updated} updated, "
        f"{report.unchanged} unchanged"
        + (f", {report.not_in_file} in database but not in file (kept)" if report.not_in_file else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
