"""The Library tab: ready-made workouts and programs for each training path.

Everything a client needs to lead with the right content is decided here:
each item carries `recommended` (it is for the user's own training path) and
`sort` (its place), so the client renders, never ranks. The rule is
deliberately simple and testable - the user's path first, easiest first, then
fewest days a week (programs) or shortest (workouts) - and a user with no path
sees all three paths with equal weight, never an empty screen.

Starting a workout copies it into a routine of the user's own (the same
mechanism as the ready-made workouts, routes/workouts.py) and starts a
session from it: it scores exactly like any other session. Following a
program is an enrollment (app/core/enrollments.py) that a finished session
moves on.

The catalog itself is imported from app/data/library_catalog.json
(scripts/import_library.py). Entries kept for the old /programs/curated and
/workouts/presets endpoints are unpublished and never appear here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.api.routes import routines as routine_routes
from app.api.routes.workouts import _session_out, routine_from_library_workout, start_session_from
from app.core import enrollments, training_categories
from app.models.library import LibraryProgram, LibraryProgramDay, LibraryWorkout, LibraryWorkoutExercise
from app.models.user import User
from app.models.workout import Exercise, Routine
from app.schemas.library import (
    Category,
    EnrollmentOut,
    LibraryHomeOut,
    LibraryProgramCard,
    LibraryProgramOut,
    LibraryWorkoutCard,
    LibraryWorkoutExerciseOut,
    LibraryWorkoutOut,
    Level,
    PathCountOut,
    ScheduleDayOut,
    ScheduleWeekOut,
    YourProgramOut,
)
from app.schemas.workout import ExerciseOut, RoutineOut, SessionOut

router = APIRouter(prefix="/library", tags=["library"])

DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}
PATH_ORDER = ("athlete", "bodybuilder", "powerlifter")


def _labels(db: Session) -> dict[str, str]:
    return {p.category: p.display_name for p in training_categories.all_profiles(db)}


def _counts(db: Session, ids: list) -> dict:
    if not ids:
        return {}
    return dict(db.execute(
        select(LibraryWorkoutExercise.workout_id, func.count(LibraryWorkoutExercise.id))
        .where(LibraryWorkoutExercise.workout_id.in_(ids))
        .group_by(LibraryWorkoutExercise.workout_id)
    ).tuples().all())


def _rank_key(path: str, category: str, difficulty: str, size: int, sort_order: int) -> tuple:
    """The recommendation order: the user's path, then the other paths in a
    fixed order; within a path, easiest first, then the smallest commitment."""
    own = 0 if category == path else 1
    return (own, PATH_ORDER.index(category), DIFFICULTY_ORDER[difficulty], size, sort_order)


def _workout_cards(db: Session, user: User, workouts: list[LibraryWorkout]) -> list[LibraryWorkoutCard]:
    path, labels = user.character_class, _labels(db)
    counts = _counts(db, [w.id for w in workouts])
    ordered = sorted(
        workouts, key=lambda w: _rank_key(path, w.category, w.difficulty, w.duration_minutes, w.sort_order)
    )
    return [
        LibraryWorkoutCard(
            slug=w.slug, name=w.name, description=w.description, category=w.category,
            category_label=labels.get(w.category, w.category.title()), difficulty=w.difficulty,
            duration_minutes=w.duration_minutes, exercise_count=counts.get(w.id, 0),
            equipment=list(w.equipment or []), focus_tags=list(w.focus_tags or []),
            recommended=bool(path) and w.category == path, sort=index,
        )
        for index, w in enumerate(ordered)
    ]


def _program_cards(db: Session, user: User, programs: list[LibraryProgram]) -> list[LibraryProgramCard]:
    path, labels = user.character_class, _labels(db)
    current = enrollments.active(db, user)
    ordered = sorted(
        programs, key=lambda p: _rank_key(path, p.category, p.difficulty, p.days_per_week, p.sort_order)
    )
    return [
        LibraryProgramCard(
            slug=p.slug, name=p.name, description=p.description, category=p.category,
            category_label=labels.get(p.category, p.category.title()), difficulty=p.difficulty,
            weeks=p.weeks, days_per_week=p.days_per_week, equipment=list(p.equipment or []),
            recommended=bool(path) and p.category == path, sort=index,
            following=current is not None and current.program_id == p.id,
        )
        for index, p in enumerate(ordered)
    ]


def _published_workouts(db: Session):
    return select(LibraryWorkout).where(LibraryWorkout.is_published.is_(True))


def _published_programs(db: Session):
    return select(LibraryProgram).where(LibraryProgram.is_published.is_(True))


def _enrollment_out(db: Session, user: User, enrollment, program: LibraryProgram) -> EnrollmentOut:
    nxt = enrollments.next_workout(db, enrollment) if enrollment.status != enrollments.COMPLETED else None
    return EnrollmentOut(
        id=enrollment.id, program_slug=program.slug, status=enrollment.status,
        started_at=enrollment.started_at, current_week=enrollment.current_week,
        current_day=enrollment.current_day,
        next_workout=_workout_cards(db, user, [nxt])[0] if nxt else None,
    )


def _workout(db: Session, slug: str) -> LibraryWorkout:
    workout = db.scalar(_published_workouts(db).where(LibraryWorkout.slug == slug))
    if workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such workout")
    return workout


def _program(db: Session, slug: str) -> LibraryProgram:
    program = db.scalar(_published_programs(db).where(LibraryProgram.slug == slug))
    if program is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such program")
    return program


@router.get("/home", response_model=LibraryHomeOut)
def library_home(current_user: CurrentUser, db: DbSession) -> LibraryHomeOut:
    """The Library tab, built for this user: the program they follow (with its
    next workout), the programs and workouts for their training path - each
    flagged `recommended`, in `sort` order - and how much each other path
    holds. With no path, `needs_path` is true, nothing is recommended, and
    all three paths are listed."""
    path = current_user.character_class
    labels = _labels(db)
    workouts = list(db.scalars(_published_workouts(db).where(LibraryWorkout.is_standalone.is_(True))))
    programs = list(db.scalars(_published_programs(db)))

    your_program = None
    current = enrollments.active(db, current_user)
    if current is not None:
        program = db.get(LibraryProgram, current.program_id)
        if program is not None:
            your_program = YourProgramOut(
                program=_program_cards(db, current_user, [program])[0],
                enrollment=_enrollment_out(db, current_user, current, program),
            )

    others = [c for c in PATH_ORDER if c != path]
    return LibraryHomeOut(
        path=path,
        needs_path=not path,
        your_program=your_program,
        recommended_programs=_program_cards(db, current_user, [p for p in programs if p.category == path]),
        recommended_workouts=_workout_cards(db, current_user, [w for w in workouts if w.category == path]),
        other_paths=[
            PathCountOut(
                category=c, label=labels.get(c, c.title()),
                programs=sum(1 for p in programs if p.category == c),
                workouts=sum(1 for w in workouts if w.category == c),
            )
            for c in others
        ],
    )


@router.get("/programs", response_model=list[LibraryProgramCard])
def list_programs(
    current_user: CurrentUser,
    db: DbSession,
    category: Category | None = None,
    difficulty: Level | None = None,
    days_per_week: int | None = Query(default=None, ge=1, le=7),
    equipment: list[str] | None = Query(default=None),
) -> list[LibraryProgramCard]:
    """Programs, filtered. `equipment` (repeatable) keeps only what can be done
    with the equipment given. Recommended first."""
    query = _published_programs(db)
    if category:
        query = query.where(LibraryProgram.category == category)
    if difficulty:
        query = query.where(LibraryProgram.difficulty == difficulty)
    if days_per_week:
        query = query.where(LibraryProgram.days_per_week == days_per_week)
    if equipment:
        query = query.where(LibraryProgram.equipment.contained_by(equipment))
    return _program_cards(db, current_user, list(db.scalars(query)))


@router.get("/programs/{slug}", response_model=LibraryProgramOut)
def get_program(slug: str, current_user: CurrentUser, db: DbSession) -> LibraryProgramOut:
    """A program: its weeks and days (rest days included), the workouts in it,
    and the user's enrollment if they follow it."""
    program = _program(db, slug)
    card = _program_cards(db, current_user, [program])[0]
    days = list(db.scalars(
        select(LibraryProgramDay).where(LibraryProgramDay.program_id == program.id)
        .order_by(LibraryProgramDay.week_number, LibraryProgramDay.day_number)
    ))
    used_ids = list(dict.fromkeys(d.workout_id for d in days if d.workout_id))
    used = {w.id: w for w in db.scalars(select(LibraryWorkout).where(LibraryWorkout.id.in_(used_ids)))}
    weeks: dict[int, list[ScheduleDayOut]] = {}
    for d in days:
        w = used.get(d.workout_id)
        weeks.setdefault(d.week_number, []).append(
            ScheduleDayOut(day=d.day_number, workout_slug=w.slug if w else None, workout_name=w.name if w else None)
        )
    enrollment = enrollments.for_program(db, current_user, program)
    # The workouts in the order they first appear in the schedule.
    in_order = [used[i] for i in used_ids if i in used]
    cards = {c.slug: c for c in _workout_cards(db, current_user, in_order)}
    return LibraryProgramOut(
        **card.model_dump(),
        schedule=[ScheduleWeekOut(week=week, days=items) for week, items in sorted(weeks.items())],
        workouts=[cards[w.slug] for w in in_order],
        enrollment=_enrollment_out(db, current_user, enrollment, program) if enrollment else None,
    )


@router.get("/workouts", response_model=list[LibraryWorkoutCard])
def list_workouts(
    current_user: CurrentUser,
    db: DbSession,
    category: Category | None = None,
    difficulty: Level | None = None,
    equipment: list[str] | None = Query(default=None),
    max_minutes: int | None = Query(default=None, ge=1, le=600),
) -> list[LibraryWorkoutCard]:
    """Standalone workouts, filtered. `equipment` (repeatable) keeps only what
    can be done with the equipment given. Recommended first."""
    query = _published_workouts(db).where(LibraryWorkout.is_standalone.is_(True))
    if category:
        query = query.where(LibraryWorkout.category == category)
    if difficulty:
        query = query.where(LibraryWorkout.difficulty == difficulty)
    if equipment:
        query = query.where(LibraryWorkout.equipment.contained_by(equipment))
    if max_minutes:
        query = query.where(LibraryWorkout.duration_minutes <= max_minutes)
    return _workout_cards(db, current_user, list(db.scalars(query)))


@router.get("/workouts/{slug}", response_model=LibraryWorkoutOut)
def get_workout(slug: str, current_user: CurrentUser, db: DbSession) -> LibraryWorkoutOut:
    """A workout: its exercises in order with targets - sets, a rep range and
    rest, never a weight. Program days are workouts too and open here."""
    workout = _workout(db, slug)
    card = _workout_cards(db, current_user, [workout])[0]
    routine = db.scalar(
        select(Routine).where(Routine.user_id == current_user.id, Routine.preset_slug == workout.slug)
    )
    return LibraryWorkoutOut(
        **card.model_dump(),
        exercises=[
            LibraryWorkoutExerciseOut(
                position=slot.position, exercise=ExerciseOut.model_validate(slot_exercise),
                target_sets=slot.target_sets, rep_low=slot.rep_low, rep_high=slot.rep_high,
                rest_seconds=slot.rest_seconds, note=slot.note, superset_group=slot.superset_group,
            )
            for slot, slot_exercise in _slots(db, workout)
        ],
        routine_id=routine.id if routine else None,
    )


def _slots(db: Session, workout: LibraryWorkout):
    exercises = {e.id: e for e in db.scalars(
        select(Exercise).where(Exercise.id.in_([s.exercise_id for s in workout.exercises]))
    )}
    return [(slot, exercises[slot.exercise_id]) for slot in workout.exercises]


@router.post("/workouts/{slug}/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_workout(slug: str, current_user: CurrentUser, db: DbSession) -> SessionOut:
    """Start a session pre-loaded with the workout's exercises, in order, each
    carrying its targets. If it is the next workout of the program the user
    follows, finishing it moves the program on. 409 if a workout is already in
    progress. It scores exactly like any other session."""
    workout = _workout(db, slug)
    routine, _ = routine_from_library_workout(db, current_user, workout)
    enrollment = enrollments.attach_for_start(db, current_user, workout)
    session = start_session_from(
        db, current_user, routine, library_workout_id=workout.id,
        program_enrollment_id=enrollment.id if enrollment else None,
    )
    return _session_out(db, session, current_user)


@router.post("/workouts/{slug}/save-to-routines", response_model=RoutineOut,
             status_code=status.HTTP_201_CREATED)
def save_workout(slug: str, response: Response, current_user: CurrentUser, db: DbSession) -> RoutineOut:
    """Copy the workout into the user's routines (201), or return the copy
    they already have (200). The copy is theirs to edit."""
    workout = _workout(db, slug)
    routine, created = routine_from_library_workout(db, current_user, workout)
    db.commit()
    db.refresh(routine)
    if not created:
        response.status_code = status.HTTP_200_OK
    return routine_routes._out(routine)


@router.post("/programs/{slug}/follow", response_model=EnrollmentOut)
def follow_program(slug: str, current_user: CurrentUser, db: DbSession) -> EnrollmentOut:
    """Follow a program: start it, or resume it where it was left. Following
    another program pauses the one before it; a completed program starts
    again from its first day."""
    program = _program(db, slug)
    enrollment = enrollments.follow(db, current_user, program)
    db.commit()
    db.refresh(enrollment)
    return _enrollment_out(db, current_user, enrollment, program)


@router.delete("/programs/{slug}/follow", response_model=EnrollmentOut)
def unfollow_program(slug: str, current_user: CurrentUser, db: DbSession) -> EnrollmentOut:
    """Pause a program. Its place is kept; following it again resumes there.
    404 if the user has never followed it."""
    program = _program(db, slug)
    enrollment = enrollments.pause(db, current_user, program)
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not following this program")
    db.commit()
    db.refresh(enrollment)
    return _enrollment_out(db, current_user, enrollment, program)
