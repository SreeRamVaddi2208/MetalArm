"""Matching stretches to what is being trained.

One rule, and it is deliberately the only one: a stretch belongs to a split
when its muscle groups overlap the split's. That is why SplitProfile stores
`target_muscle_groups` - adding an Upper/Lower split later is a row in
app/data/splits.json, not a branch in here.

Pure on purpose. The filtering takes the split's groups and a list of
exercises and returns a list; the database work happens in the route. It is
the same function for the warm-up and the cooldown, which is what stops the
two drifting apart.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.split import SplitProfile, SplitType, StretchPhase

SPLIT_FILE = pathlib.Path(__file__).resolve().parents[1] / "data" / "splits.json"


def matches(exercise_groups: Sequence[str], split_groups: Sequence[str]) -> bool:
    """Whether one stretch suits one split.

    `full_body` matches everything: a world's-greatest-stretch is not wasted on
    a push day, and tagging it with every group individually would be a lie
    about what it works.
    """
    if "full_body" in exercise_groups:
        return True
    return bool(set(exercise_groups) & set(split_groups))


def for_split(
    stretches: Iterable[tuple[str, Sequence[str], str | None]],
    split_groups: Sequence[str],
    phase: StretchPhase | str,
) -> list[str]:
    """The ids of the stretches that suit this split and phase.

    Each entry is (id, muscle_groups, phase). Taking tuples rather than ORM
    rows keeps this testable without a database - the route hands it what it
    read, and gets back what to show.
    """
    wanted = phase.value if isinstance(phase, StretchPhase) else phase
    return [
        identifier
        for identifier, groups, entry_phase in stretches
        if entry_phase == wanted and matches(groups, split_groups)
    ]


def known(split_type: str | None) -> bool:
    """Whether this is a split we have a profile for. An unknown value is not
    an error anywhere - it simply means no panel, rather than a broken one."""
    if not split_type:
        return False
    return split_type in {member.value for member in SplitType}


# --- The shipped definitions ----------------------------------------------
# Same shape as app/core/training_categories.py, and for the same reasons: the
# rows are tuning rather than user data, so editing the file and deploying is
# how they change - and a database that has not been seeded still answers,
# rather than showing an empty picker.


def definitions() -> list[dict]:
    return json.loads(SPLIT_FILE.read_text())


def all_profiles(db: Session) -> list[SplitProfile]:
    """Every split, in picker order, falling back to the shipped file."""
    rows = list(db.scalars(select(SplitProfile)))
    if not rows:
        rows = [SplitProfile(**record) for record in definitions()]
    return sorted(rows, key=lambda row: (row.position, row.split_type))


def profile(db: Session, split_type: str) -> SplitProfile | None:
    return next((row for row in all_profiles(db) if row.split_type == split_type), None)


def seed(db: Session) -> int:
    """Upsert the shipped definitions. Idempotent: run it on every deploy."""
    existing = {row.split_type: row for row in db.scalars(select(SplitProfile))}
    written = 0
    for record in definitions():
        row = existing.get(record["split_type"])
        if row is None:
            db.add(SplitProfile(**record))
            written += 1
            continue
        if any(getattr(row, field) != value for field, value in record.items()):
            for field, value in record.items():
                setattr(row, field, value)
            written += 1
    return written
