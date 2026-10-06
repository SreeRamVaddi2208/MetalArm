"""Exercise aliases: the shipped set, seeding it, and resolving a user's view.

One file, app/data/exercise_aliases.json, says what "bench" or "rdl" means.
It serves two readers: the Strong/Hevy importer (app/core/importer.py), which
matches an export's exercise name to the library, and natural-language set
logging (app/core/nl_parser.py), which matches what someone said. Keeping one
table means an alias added for one is never missing from the other.
"""

import json
import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exercise_names import name_key, slugify
from app.models.nl_log import AliasSource, ExerciseAlias
from app.models.workout import Exercise

ALIAS_FILE = Path(__file__).resolve().parents[1] / "data" / "exercise_aliases.json"


@lru_cache(maxsize=1)
def definitions() -> dict[str, tuple[str, ...]]:
    """Library slug -> its aliases, as shipped."""
    raw = json.loads(ALIAS_FILE.read_text())
    return {slug: tuple(name_key(a) for a in aliases) for slug, aliases in raw.items()}


def slug_map() -> dict[str, str]:
    """slugify(alias) -> library slug: the importer's lookup, which works in
    slugs because export names arrive as "Squat (Barbell)"-style strings."""
    return {slugify(alias): slug for slug, aliases in definitions().items() for alias in aliases}


def seed(db: Session) -> int:
    """Insert any shipped alias the database lacks. Returns how many were
    added. Idempotent; never deletes, so an alias removed from the file must
    be deleted by hand (sets do not point at aliases, so that is safe)."""
    library = {
        slug: exercise_id
        for slug, exercise_id in db.execute(
            select(Exercise.slug, Exercise.id).where(Exercise.is_custom.is_(False))
        )
    }
    rows = [
        {"exercise_id": library[slug], "alias": alias, "source": AliasSource.SEED.value}
        for slug, aliases in definitions().items()
        if slug in library
        for alias in aliases
    ]
    if not rows:
        return 0
    result = db.execute(
        insert(ExerciseAlias)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_exercise_aliases_alias")
        .returning(ExerciseAlias.id)
    )
    return len(result.all())


def for_user(db: Session, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """alias -> exercise id as this user sees it: the global set, overridden
    by their own. Archived exercises are left out - a voice log must not
    resurrect one."""
    rows = db.execute(
        select(ExerciseAlias.alias, ExerciseAlias.exercise_id, ExerciseAlias.user_id)
        .join(Exercise, Exercise.id == ExerciseAlias.exercise_id)
        .where(
            or_(ExerciseAlias.user_id.is_(None), ExerciseAlias.user_id == user_id),
            Exercise.is_archived.is_(False),
        )
    ).all()
    out: dict[str, uuid.UUID] = {}
    for alias, exercise_id, owner in sorted(rows, key=lambda r: r.user_id is not None):
        out[alias] = exercise_id  # personal rows sort last and win
    return out
