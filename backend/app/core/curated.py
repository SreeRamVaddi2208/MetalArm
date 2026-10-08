"""Curated programs (the original six, served by GET /programs/curated):
plans shipped with the app, built from library exercises.

They now live in the Library catalog (app/data/library_catalog.json) as
entries with `"legacy_source": "curated"`, alongside the Library's own
programs, and are rebuilt here into exactly the shape the old endpoint has
always served - so iOS and anything else reading it sees no change. A legacy
program's routines are its rotation's workouts, in order.

Saving one copies it into the user's Library - a Program they own, with its
routines in order - which they can then change freely.
"""

from __future__ import annotations

from functools import lru_cache

from app.core import catalog_validator as cv


def _routine(workout: dict) -> dict:
    exercises = []
    for slot in workout["exercises"]:
        item = {"slug": slot["slug"], "sets": slot["sets"], "reps_low": slot["reps"][0],
                "reps_high": slot["reps"][1], "rest_seconds": slot["rest"]}
        if "superset" in slot:
            item["superset"] = slot["superset"]
        exercises.append(item)
    return {"name": workout["name"], "exercises": exercises}


@lru_cache(maxsize=1)
def definitions() -> tuple[dict, ...]:
    catalog = cv.load()
    workouts = {w["slug"]: w for w in catalog["workouts"]}
    return tuple(
        {
            "slug": p["slug"],
            "name": p["name"],
            "category": p["category"],
            "level": p["difficulty"],
            "weeks": p["weeks"],
            "sessions_per_week": p["days_per_week"],
            "description": p["description"],
            "routines": [_routine(workouts[slug]) for slug in p["schedule"]["rotation"]["workouts"]],
        }
        for p in catalog["programs"]
        if p.get("legacy_source") == "curated"
    )


def by_slug(slug: str) -> dict | None:
    return next((p for p in definitions() if p["slug"] == slug), None)


def slugs_used() -> set[str]:
    return {e["slug"] for p in definitions() for r in p["routines"] for e in r["exercises"]}
