"""Reading and seeding the exercise taxonomy (app/models/taxonomy.py).

Config shipped with the image, like the training paths: seeded on deploy by
scripts.import_exercises (the taxonomy goes first, because exercises are
validated against it), read from the database afterwards.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.taxonomy import EquipmentInfo, MuscleGroupInfo

TAXONOMY_FILE = Path(__file__).resolve().parents[1] / "data" / "taxonomy.json"


def definitions() -> dict[str, list[dict]]:
    return json.loads(TAXONOMY_FILE.read_text())


def _upsert(db: Session, model, rows: list[dict]) -> int:
    existing = {row.code: row for row in db.scalars(select(model))}
    written = 0
    for record in rows:
        row = existing.get(record["code"])
        if row is None:
            db.add(model(**record))
            written += 1
        elif any(getattr(row, k) != v for k, v in record.items()):
            for k, v in record.items():
                setattr(row, k, v)
            written += 1
    return written


def seed(db: Session) -> int:
    """Upsert the shipped taxonomy. Idempotent; never deletes a code, since
    exercises store them."""
    data = definitions()
    written = _upsert(db, MuscleGroupInfo, data["muscle_groups"])
    written += _upsert(db, EquipmentInfo, data["equipment"])
    db.flush()
    return written


def muscles(db: Session) -> list[MuscleGroupInfo]:
    return list(db.scalars(select(MuscleGroupInfo).order_by(MuscleGroupInfo.sort_order)))


def equipment(db: Session) -> list[EquipmentInfo]:
    return list(db.scalars(select(EquipmentInfo).order_by(EquipmentInfo.sort_order)))
