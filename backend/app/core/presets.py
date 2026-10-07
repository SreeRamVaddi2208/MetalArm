"""Ready-made workouts, one per training style.

Athletic, powerlifting and bodybuilding: a user picks one and starts lifting
without building a routine first. They are DEFINITIONS, not rows - the file is
part of the image, like the exercise library - and a preset becomes real only
when someone starts it, as a routine of their own (see start_session), which is
what gives the session its targets, its planned order and its ghost values.

The original three now live in the Library catalog
(app/data/library_catalog.json) as workouts with `"legacy_source": "preset"`,
rebuilt here into exactly the shape GET /workouts/presets has always served.
New ready-made workouts are added to the Library, not here; the catalog
validator checks every exercise slug on import.
"""

from functools import lru_cache

from pydantic import BaseModel, Field

from app.core import catalog_validator as cv
from app.core import workout_rules as rules


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
    """Every preset, in catalog order. Cached: the file ships with the image."""
    presets = [
        Preset.model_validate({
            "slug": w["slug"], "category": w["category"], "name": w["name"], "summary": w["description"],
            "exercises": [
                {"slug": s["slug"], "target_sets": s["sets"], "target_reps": s["reps"][1],
                 "rest_seconds": s["rest"]}
                for s in w["exercises"]
            ],
        })
        for w in cv.load()["workouts"]
        if w.get("legacy_source") == "preset"
    ]
    slugs = [preset.slug for preset in presets]
    if len(set(slugs)) != len(slugs):
        raise ValueError("the library catalog has duplicate preset slugs")
    return presets


def by_slug(slug: str) -> Preset | None:
    return next((preset for preset in all_presets() if preset.slug == slug), None)
