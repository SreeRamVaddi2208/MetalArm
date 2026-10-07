#!/usr/bin/env python3
"""Load the Library catalog - ready-made workouts and programs - from JSON.

Idempotent: workouts and programs are keyed by `slug`, so re-running updates
them in place and inserts only what is new. Run on every start, after the
exercise library and the training paths it is checked against:

    docker compose run --rm tests python -m scripts.import_library --dry-run
    docker compose run --rm tests python -m scripts.import_library
    docker compose run --rm tests python -m scripts.import_library --file more.json

The whole file is validated first (app/core/catalog_validator.py: exercises
exist, schedules add up, every session fits its training path) and rejected
outright on any problem, each one naming the offending slug. Adding content
later is editing the file - no code change.

A workout or program's own rows (its exercises, its days) are replaced on each
import. That is safe: an enrollment remembers a week and a day number, not a
row. Slugs in the database but missing from the file are UNPUBLISHED, never
deleted - sessions and enrollments point at them.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import catalog_validator as cv
from app.core import training_categories
from app.db.session import engine
from app.models.library import LibraryProgram, LibraryProgramDay, LibraryWorkout, LibraryWorkoutExercise
from app.models.workout import Exercise

DEFAULT_FILE = cv.CATALOG_FILE


@dataclasses.dataclass
class ImportReport:
    workouts_inserted: int = 0
    workouts_updated: int = 0
    programs_inserted: int = 0
    programs_updated: int = 0
    unpublished: int = 0


def read_catalog(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def exercise_facts(db: Session) -> dict[str, cv.ExerciseFacts]:
    """The library exercises, as the validator sees them."""
    return {
        e.slug: cv.ExerciseFacts(e.category, tuple(e.tags or ()), e.equipment)
        for e in db.scalars(select(Exercise).where(Exercise.is_custom.is_(False)))
    }


def path_profiles(db: Session) -> dict[str, dict]:
    return {
        p.category: {"rep_range_low": p.rep_range_low, "rep_range_high": p.rep_range_high}
        for p in training_categories.all_profiles(db)
    }


def import_library(db: Session, catalog: dict) -> ImportReport:
    """Validate, then upsert. Does not commit - the caller owns that."""
    cv.check(catalog, exercise_facts(db), path_profiles(db))
    exercise_ids = {
        e.slug: (e.id, e.equipment)
        for e in db.scalars(select(Exercise).where(Exercise.is_custom.is_(False)))
    }
    report = ImportReport()

    workouts = {w.slug: w for w in db.scalars(select(LibraryWorkout))}
    for entry in catalog["workouts"]:
        row = workouts.get(entry["slug"])
        if row is None:
            row = LibraryWorkout(slug=entry["slug"])
            db.add(row)
            workouts[entry["slug"]] = row
            report.workouts_inserted += 1
        else:
            report.workouts_updated += 1
        row.name = entry["name"]
        row.description = entry.get("description")
        row.category = entry["category"]
        row.difficulty = entry["difficulty"]
        row.duration_minutes = entry["duration_minutes"]
        row.focus_tags = list(entry.get("focus_tags") or [])
        row.is_standalone = bool(entry.get("standalone", True))
        row.legacy_source = entry.get("legacy_source")
        row.is_published = row.legacy_source is None
        row.sort_order = entry.get("sort_order", 0)
        # What the gym needs: every exercise's equipment, in first-use order.
        row.equipment = list(dict.fromkeys(exercise_ids[s["slug"]][1] for s in entry["exercises"]))
        row.exercises.clear()
        db.flush()
        for position, slot in enumerate(entry["exercises"]):
            row.exercises.append(LibraryWorkoutExercise(
                exercise_id=exercise_ids[slot["slug"]][0], position=position, target_sets=slot["sets"],
                rep_low=slot["reps"][0], rep_high=slot["reps"][1], rest_seconds=slot["rest"],
                note=slot.get("note"), superset_group=slot.get("superset", 0),
            ))
    db.flush()

    programs = {p.slug: p for p in db.scalars(select(LibraryProgram))}
    for entry in catalog["programs"]:
        row = programs.get(entry["slug"])
        if row is None:
            row = LibraryProgram(slug=entry["slug"])
            db.add(row)
            programs[entry["slug"]] = row
            report.programs_inserted += 1
        else:
            report.programs_updated += 1
        row.name = entry["name"]
        row.description = entry.get("description")
        row.category = entry["category"]
        row.difficulty = entry["difficulty"]
        row.weeks = entry["weeks"]
        row.days_per_week = entry["days_per_week"]
        row.legacy_source = entry.get("legacy_source")
        row.is_published = row.legacy_source is None
        row.sort_order = entry.get("sort_order", 0)
        days = cv.schedule_days(entry)
        used = [workouts[w] for _, _, w in days if w]
        row.equipment = list(dict.fromkeys(eq for w in used for eq in w.equipment))
        row.days.clear()
        db.flush()
        for week, day, workout in days:
            row.days.append(LibraryProgramDay(
                week_number=week, day_number=day, workout_id=workouts[workout].id if workout else None,
            ))
    db.flush()

    # Gone from the file: hidden, not deleted.
    in_file = {e["slug"] for e in catalog["workouts"]} | {p["slug"] for p in catalog["programs"]}
    for row in [*workouts.values(), *programs.values()]:
        if row.slug not in in_file and row.is_published:
            row.is_published = False
            report.unpublished += 1
    db.flush()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", type=pathlib.Path, default=DEFAULT_FILE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        catalog = read_catalog(args.file)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    with Session(engine) as db:
        try:
            report = import_library(db, catalog)
        except cv.CatalogError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    prefix = "DRY RUN - would have: " if args.dry_run else ""
    print(
        f"{prefix}library catalog from {args.file.name}: workouts {report.workouts_inserted} new, "
        f"{report.workouts_updated} updated; programs {report.programs_inserted} new, "
        f"{report.programs_updated} updated"
        + (f"; {report.unpublished} no longer in the file (unpublished)" if report.unpublished else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
