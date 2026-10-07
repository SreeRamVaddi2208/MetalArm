"""Curated programs (Explore -> Programs): plans shipped with the app, in
app/data/programs.json, built from library exercises.

Kept as data rather than rows because their routines would have no owner.
Saving one copies it into the user's Library - a Program they own, with its
routines in order - which they can then change freely.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROGRAMS_FILE = Path(__file__).resolve().parents[1] / "data" / "programs.json"


@lru_cache(maxsize=1)
def definitions() -> tuple[dict, ...]:
    return tuple(json.loads(PROGRAMS_FILE.read_text()))


def by_slug(slug: str) -> dict | None:
    return next((p for p in definitions() if p["slug"] == slug), None)


def slugs_used() -> set[str]:
    return {e["slug"] for p in definitions() for r in p["routines"] for e in r["exercises"]}
