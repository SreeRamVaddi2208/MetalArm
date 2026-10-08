"""The Library catalog as content: the shipped file is valid against the
training paths, the validator catches each kind of mistake by slug, schedules
expand as written, and importing is idempotent."""

import copy
from collections import Counter

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import catalog_validator as cv
from app.models.library import LibraryProgram, LibraryProgramDay, LibraryWorkout, LibraryWorkoutExercise
from scripts.import_library import exercise_facts, import_library, path_profiles


@pytest.fixture
def facts(db: Session):
    return exercise_facts(db), path_profiles(db)


def _catalog() -> dict:
    return copy.deepcopy(cv.load())


def _workout(catalog: dict, slug: str) -> dict:
    return next(w for w in catalog["workouts"] if w["slug"] == slug)


def _program(catalog: dict, slug: str) -> dict:
    return next(p for p in catalog["programs"] if p["slug"] == slug)


def test_the_shipped_catalog_is_valid(facts) -> None:
    assert cv.validate(cv.load(), *facts) == []


def test_three_programs_and_four_workouts_per_path(db: Session) -> None:
    programs = Counter(db.scalars(select(LibraryProgram.category).where(LibraryProgram.is_published.is_(True))))
    workouts = Counter(db.scalars(
        select(LibraryWorkout.category)
        .where(LibraryWorkout.is_published.is_(True), LibraryWorkout.is_standalone.is_(True))
    ))
    assert programs == {"athlete": 3, "bodybuilder": 3, "powerlifter": 3}
    assert workouts == {"athlete": 4, "bodybuilder": 4, "powerlifter": 4}


def test_legacy_content_is_imported_but_hidden(db: Session) -> None:
    hidden = list(db.scalars(select(LibraryWorkout).where(LibraryWorkout.legacy_source.is_not(None))))
    assert hidden and not any(w.is_published for w in hidden)
    assert db.scalar(select(func.count()).select_from(LibraryProgram)
                     .where(LibraryProgram.legacy_source == "curated", LibraryProgram.is_published)) == 0


@pytest.mark.parametrize(
    ("break_it", "expected"),
    [
        (lambda c: _workout(c, "squat-day")["exercises"][0].update(reps=[8, 10]),
         "squat-day #1 back-squat: 8-10 reps is outside the powerlifter primary band"),
        (lambda c: _workout(c, "chest-and-triceps")["exercises"][0].update(reps=[15, 20]),
         "chest-and-triceps #1 incline-barbell-bench-press: 15-20 reps is outside the bodybuilder"),
        (lambda c: _workout(c, "engine")["exercises"][1].update(rest=90),
         "engine #2 burpee: 90s rest is outside the athlete working band"),
        (lambda c: _workout(c, "bench-day")["exercises"][0].update(rest=90),
         "bench-day #1 barbell-bench-press: 90s rest is outside the powerlifter primary band"),
        (lambda c: _workout(c, "plyometric-power-circuit")["exercises"].pop(0),
         "plyometric-power-circuit: an athletic session needs a mobility exercise"),
        (lambda c: _workout(c, "bench-day")["exercises"][2].update(slug="not-an-exercise"),
         "bench-day #3 not-an-exercise: not in the exercise library"),
        (lambda c: _workout(c, "squat-day")["exercises"].extend(
            [{"slug": "leg-press", "sets": 3, "reps": [8, 10], "rest": 90}] * 2),
         "squat-day: 2 main lifts and 5 accessories"),
        (lambda c: _program(c, "meet-prep-peak").update(days_per_week=5),
         "meet-prep-peak: week 1 has 4 training days, not 5"),
        (lambda c: _program(c, "upper-lower-8wk")["schedule"]["week_pattern"][0].update(workout="ghost"),
         "upper-lower-8wk: week 1 day 1 names 'ghost', which is not a workout"),
        (lambda c: _program(c, "upper-lower-8wk")["schedule"]["week_pattern"][0].update(workout="squat-day"),
         "upper-lower-8wk: week 1 day 1 is a powerlifter workout"),
        (lambda c: c["workouts"].append(copy.deepcopy(_workout(c, "engine"))),
         "engine: more than one workout has this slug"),
    ],
)
def test_the_validator_names_the_offending_slug(facts, break_it, expected) -> None:
    catalog = _catalog()
    break_it(catalog)
    problems = cv.validate(catalog, *facts)
    assert any(expected in p for p in problems), problems
    with pytest.raises(cv.CatalogError):
        cv.check(catalog, *facts)


def test_an_accessory_role_lets_a_heavy_lift_take_accessory_reps(facts) -> None:
    catalog = _catalog()
    row = _workout(catalog, "heavy-accessory-session")["exercises"][1]
    assert row["slug"] == "barbell-row" and row["role"] == "accessory"
    assert cv.validate(catalog, *facts) == []
    row.pop("role")
    assert any("barbell-row" in p for p in cv.validate(catalog, *facts))


def test_legacy_content_is_held_to_structure_not_bands(facts) -> None:
    catalog = _catalog()
    legacy = _workout(catalog, "athletic-power-day")
    assert legacy["legacy_source"] == "preset"
    legacy["exercises"][0]["rest"] = 600          # outside every band: allowed
    assert cv.validate(catalog, *facts) == []
    legacy["exercises"][0]["slug"] = "missing"    # but it must still exist
    assert any("athletic-power-day" in p for p in cv.validate(catalog, *facts))


def test_week_patterns_overrides_and_rotations_expand() -> None:
    pattern = {"weeks": 2, "schedule": {"week_pattern": [{"day": 1, "workout": "a"}, {"day": 4, "workout": "b"}],
                                        "overrides": {"2": [{"day": 2, "workout": "c"}]}}}
    days = cv.schedule_days(pattern)
    assert len(days) == 14
    assert [(w, d, x) for w, d, x in days if x] == [(1, 1, "a"), (1, 4, "b"), (2, 2, "c")]
    rotation = {"weeks": 2, "schedule": {"rotation": {"workouts": ["a", "b"], "training_days": [1, 3, 5]}}}
    assert [x for _, _, x in cv.schedule_days(rotation) if x] == ["a", "b", "a", "b", "a", "b"]


def test_a_program_stores_every_day_rest_days_included(db: Session) -> None:
    program = db.scalar(select(LibraryProgram).where(LibraryProgram.slug == "linear-strength-base"))
    days = db.scalars(select(LibraryProgramDay).where(LibraryProgramDay.program_id == program.id)).all()
    assert len(days) == program.weeks * 7
    assert sum(1 for d in days if d.workout_id) == program.weeks * program.days_per_week


def test_importing_twice_changes_nothing(db: Session) -> None:
    def counts() -> tuple:
        return tuple(db.scalar(select(func.count()).select_from(m)) for m in
                     (LibraryWorkout, LibraryWorkoutExercise, LibraryProgram, LibraryProgramDay))
    before = counts()
    report = import_library(db, cv.load())
    assert report.workouts_inserted == report.programs_inserted == 0
    assert counts() == before


def test_a_workout_dropped_from_the_file_is_unpublished_not_deleted(db: Session) -> None:
    catalog = _catalog()
    catalog["workouts"] = [w for w in catalog["workouts"] if w["slug"] != "full-body-mobility-flow"]
    report = import_library(db, catalog)
    assert report.unpublished == 1
    row = db.scalar(select(LibraryWorkout).where(LibraryWorkout.slug == "full-body-mobility-flow"))
    assert row is not None and row.is_published is False
