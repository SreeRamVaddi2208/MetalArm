"""The Library catalog: read it, expand its schedules, and check it against
the training paths before a byte of it is imported.

The catalog lives in app/data/library_catalog.json. A path's rules come from
its TrainingCategoryProfile (app/data/training_categories.json) - the content
is held to the profile, never the other way round:

    athlete       12+ reps on working sets, 30-60 s rest, a mobility exercise
                  in every session
    bodybuilder   8-15 reps, 60-120 s rest
    powerlifter   primary lifts (tagged big3 or compound_heavy, unless marked
                  "role": "accessory") 1-6 reps at 180-300 s; at most two of
                  them and four accessories, which take 3-15 reps at 60-150 s

The rep bands are the profile's (`rep_range_low/high`; athlete open-ended
above). The rest bands bracket the profile's guidance: the spec asked for
30-45 s on the athletic path where its profile says 60, so its band holds
both. Mobility work (category or tag) is exempt from the rep band - a stretch
is counted in breaths, not working reps.

Entries with a `legacy_source` are the original curated programs and presets,
kept byte-for-byte so their old endpoints answer as before; they are checked
for structure (exercises exist, schedules add up) but not held to the bands
they predate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CATALOG_FILE = Path(__file__).resolve().parents[1] / "data" / "library_catalog.json"

CATEGORIES = ("athlete", "bodybuilder", "powerlifter")
DIFFICULTIES = ("beginner", "intermediate", "advanced")
MAX_SLUG = 60

# Rest seconds, as (low, high), per path and role.
REST = {
    "athlete": (30, 60),
    "bodybuilder": (60, 120),
    ("powerlifter", "primary"): (180, 300),
    ("powerlifter", "accessory"): (60, 150),
}
ACCESSORY_REPS = (3, 15)
MAX_PRIMARY, MAX_ACCESSORIES = 2, 4
MOBILITY_REST_MAX = 60


class CatalogError(ValueError):
    """The catalog failed validation; `problems` names every offending slug."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("library catalog is invalid:\n  " + "\n  ".join(problems))


@dataclass(frozen=True)
class ExerciseFacts:
    """What the validator needs to know about a library exercise."""

    category: str
    tags: tuple[str, ...]
    equipment: str

    @property
    def mobility(self) -> bool:
        return self.category == "mobility" or "mobility" in self.tags

    @property
    def heavy(self) -> bool:
        return "big3" in self.tags or "compound_heavy" in self.tags


@lru_cache(maxsize=1)
def load(path: Path = CATALOG_FILE) -> dict:
    """The catalog file, parsed. Cached: it ships with the image."""
    return json.loads(path.read_text())


def schedule_days(program: dict) -> list[tuple[int, int, str | None]]:
    """(week, day, workout slug or None for rest) for every day of every week.

    A `week_pattern` is the same week repeated, with optional per-week
    `overrides` ({"4": [{"day": 1, "workout": "x"}, ...]} replacing that
    week). A `rotation` cycles its workouts across the training days of
    consecutive weeks: A/B over days 1, 3, 5 gives A B A, then B A B."""
    schedule = program["schedule"]
    weeks = program["weeks"]
    days: list[tuple[int, int, str | None]] = []
    if "rotation" in schedule:
        rotation = schedule["rotation"]
        cycle, training = rotation["workouts"], rotation["training_days"]
        n = 0
        for week in range(1, weeks + 1):
            for day in range(1, 8):
                if day in training:
                    days.append((week, day, cycle[n % len(cycle)]))
                    n += 1
                else:
                    days.append((week, day, None))
        return days
    pattern = {item["day"]: item["workout"] for item in schedule["week_pattern"]}
    overrides = {
        int(week): {item["day"]: item["workout"] for item in items}
        for week, items in (schedule.get("overrides") or {}).items()
    }
    for week in range(1, weeks + 1):
        this_week = overrides.get(week, pattern)
        for day in range(1, 8):
            days.append((week, day, this_week.get(day)))
    return days


def is_primary(slot: dict, facts: ExerciseFacts) -> bool:
    return slot.get("role") != "accessory" and facts.heavy


def _check_workout(workout: dict, exercises: dict[str, ExerciseFacts],
                   profiles: dict[str, dict]) -> list[str]:
    slug = workout.get("slug", "?")
    problems: list[str] = []
    if len(slug) > MAX_SLUG:
        problems.append(f"{slug}: slug longer than {MAX_SLUG} characters")
    if workout.get("category") not in CATEGORIES:
        problems.append(f"{slug}: unknown category {workout.get('category')!r}")
        return problems
    if workout.get("difficulty") not in DIFFICULTIES:
        problems.append(f"{slug}: unknown difficulty {workout.get('difficulty')!r}")
    slots = workout.get("exercises") or []
    if not slots:
        problems.append(f"{slug}: has no exercises")
    for index, slot in enumerate(slots, start=1):
        where = f"{slug} #{index} {slot.get('slug')}"
        if slot.get("slug") not in exercises:
            problems.append(f"{where}: not in the exercise library")
        low, high = slot["reps"]
        if low < 1 or high < low:
            problems.append(f"{where}: rep range {low}-{high} is not a range")
        if slot["sets"] < 1:
            problems.append(f"{where}: needs at least one set")
    if workout.get("legacy_source") or problems:
        return problems

    path = workout["category"]
    profile = profiles[path]
    primaries = accessories = 0
    for index, slot in enumerate(slots, start=1):
        facts = exercises[slot["slug"]]
        where = f"{slug} #{index} {slot['slug']}"
        low, high = slot["reps"]
        rest = slot["rest"]
        if facts.mobility:
            if rest > MOBILITY_REST_MAX:
                problems.append(f"{where}: mobility rest {rest}s is over {MOBILITY_REST_MAX}s")
            continue
        if path == "powerlifter":
            role = "primary" if is_primary(slot, facts) else "accessory"
            primaries += role == "primary"
            accessories += role == "accessory"
            rep_band = (profile["rep_range_low"], profile["rep_range_high"]) if role == "primary" else ACCESSORY_REPS
            rest_band = REST[(path, role)]
        else:
            role = "working"
            rest_band = REST[path]
            rep_band = (profile["rep_range_low"],
                        None if path == "athlete" else profile["rep_range_high"])
        if low < rep_band[0] or (rep_band[1] is not None and high > rep_band[1]):
            band = f"{rep_band[0]}-{rep_band[1]}" if rep_band[1] is not None else f"{rep_band[0]}+"
            problems.append(f"{where}: {low}-{high} reps is outside the {path} {role} band ({band})")
        if not rest_band[0] <= rest <= rest_band[1]:
            problems.append(
                f"{where}: {rest}s rest is outside the {path} {role} band ({rest_band[0]}-{rest_band[1]}s)"
            )
    if path == "powerlifter" and (primaries > MAX_PRIMARY or accessories > MAX_ACCESSORIES):
        problems.append(
            f"{slug}: {primaries} main lifts and {accessories} accessories - a powerlifting session has at"
            f" most {MAX_PRIMARY} and {MAX_ACCESSORIES}"
        )
    if path == "athlete" and not any(exercises[s["slug"]].mobility for s in slots):
        problems.append(f"{slug}: an athletic session needs a mobility exercise")
    return problems


def _check_program(program: dict, workouts: dict[str, dict]) -> list[str]:
    slug = program.get("slug", "?")
    problems: list[str] = []
    if len(slug) > MAX_SLUG:
        problems.append(f"{slug}: slug longer than {MAX_SLUG} characters")
    if program.get("category") not in CATEGORIES:
        problems.append(f"{slug}: unknown category {program.get('category')!r}")
    if program.get("difficulty") not in DIFFICULTIES:
        problems.append(f"{slug}: unknown difficulty {program.get('difficulty')!r}")
    weeks, per_week = program.get("weeks", 0), program.get("days_per_week", 0)
    if not 1 <= weeks <= 52 or not 1 <= per_week <= 7:
        problems.append(f"{slug}: {weeks} weeks of {per_week} days is not a schedule")
        return problems
    try:
        days = schedule_days(program)
    except (KeyError, IndexError, TypeError, ZeroDivisionError) as exc:
        return problems + [f"{slug}: schedule cannot be read ({exc!r})"]
    seen_weeks = {week for week, _, _ in days}
    if len(seen_weeks) != weeks:
        problems.append(f"{slug}: schedule covers {len(seen_weeks)} weeks, not {weeks}")
    for week in sorted(seen_weeks):
        training = [w for wk, _, w in days if wk == week and w]
        if len(training) != per_week:
            problems.append(f"{slug}: week {week} has {len(training)} training days, not {per_week}")
    for week, day, workout in days:
        if workout is None:
            continue
        target = workouts.get(workout)
        if target is None:
            problems.append(f"{slug}: week {week} day {day} names {workout!r}, which is not a workout")
        elif target.get("category") != program.get("category") and not program.get("legacy_source"):
            problems.append(f"{slug}: week {week} day {day} is a {target.get('category')} workout")
    return problems


def validate(catalog: dict, exercises: dict[str, ExerciseFacts], profiles: dict[str, dict]) -> list[str]:
    """Every problem in the catalog, each naming the offending slug. Empty
    means it can be imported."""
    problems: list[str] = []
    workouts = catalog.get("workouts") or []
    programs = catalog.get("programs") or []
    for kind, items in (("workout", workouts), ("program", programs)):
        slugs = [item.get("slug") for item in items]
        for dup in sorted({s for s in slugs if slugs.count(s) > 1}):
            problems.append(f"{dup}: more than one {kind} has this slug")
    by_slug = {w["slug"]: w for w in workouts if "slug" in w}
    for workout in workouts:
        problems += _check_workout(workout, exercises, profiles)
    for program in programs:
        problems += _check_program(program, by_slug)
    return problems


def check(catalog: dict, exercises: dict[str, ExerciseFacts], profiles: dict[str, dict]) -> None:
    """validate(), raising CatalogError when anything is wrong."""
    problems = validate(catalog, exercises, profiles)
    if problems:
        raise CatalogError(problems)
