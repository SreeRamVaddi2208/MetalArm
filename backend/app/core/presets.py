"""Ready-made workouts, one per training style.

Athletic, powerlifting and bodybuilding: a user picks one and starts lifting
without building a routine first. They are DEFINITIONS, not rows - the file is
part of the image, like the exercise library - and a preset becomes real only
when someone starts it, as a routine of their own (see start_session), which is
what gives the session its targets, its planned order and its ghost values.

Adding one is editing app/data/workout_presets.json: every exercise slug is
checked against the library at load, so a typo fails loudly at import rather
than serving a preset nobody can start.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from app.core import workout_rules as rules

PRESET_FILE = Path(__file__).resolve().parents[1] / "data" / "workout_presets.json"


class PresetExercise(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    target_sets: int = Field(ge=1, le=50)
    # Held to the same ceiling as a routine's target, so a preset can never
    # ask for something a routine could not.
    target_reps: int = Field(ge=1, le=rules.MAX_REPS)
    rest_seconds: int = Field(ge=0, le=3600)


class Preset(BaseModel):
    slug: str = Field(min_length=1, max_length=60)
    # Free text rather than an enum: a new style is a file edit, and the
    # clients group by whatever they are given.
    category: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=280)
    exercises: list[PresetExercise] = Field(min_length=1, max_length=20)


@lru_cache(maxsize=1)
def all_presets() -> list[Preset]:
    """Every preset, in file order. Cached: the file ships with the image."""
    records = json.loads(PRESET_FILE.read_text())
    presets = [Preset.model_validate(record) for record in records]
    slugs = [preset.slug for preset in presets]
    if len(set(slugs)) != len(slugs):
        raise ValueError("workout_presets.json has duplicate slugs")
    return presets


def by_slug(slug: str) -> Preset | None:
    return next((preset for preset in all_presets() if preset.slug == slug), None)
