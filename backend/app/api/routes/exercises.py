"""The exercise library: search, custom exercises, and per-exercise progress.

Library exercises are shared and read-only here - they come from
scripts/import_exercises.py. Custom exercises belong to one user and are
invisible to everyone else.
"""

import uuid
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import personal_records as prs
from app.core import progression_hints as hints
from app.core import workout_store as store
from app.core.exercise_names import clean_name, name_key
from app.models.user import User
from app.models.workout import Exercise, RoutineExercise, SetEntry, WorkoutSession
from app.models.workout_enums import (
    Equipment,
    ExerciseCategory,
    MeasurementMetric,
    MeasurementUnit,
    MuscleGroup,
    SessionStatus,
    WeightUnit,
    values,
)
from app.schemas.workout import (
    HintOut,
    ExerciseCreate,
    ExerciseHistoryPoint,
    ExerciseMetaOut,
    ExerciseOut,
    ExerciseUpdate,
    LastPerformanceOut,
    SetOut,
)

router = APIRouter(prefix="/exercises", tags=["exercises"])


class ExerciseDeleteOut(BaseModel):
    """`archived` is true when the exercise was hidden rather than deleted,
    because sets or routines still reference it."""

    archived: bool


def _get_visible(db: Session, exercise_id: uuid.UUID, user: User) -> Exercise:
    exercise = store.get_visible_exercise(db, exercise_id, user.id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return exercise


def _get_own_custom(db: Session, exercise_id: uuid.UUID, user: User) -> Exercise:
    """For writes. Another user's custom exercise is a 404 (it is invisible);
    a library exercise is a 403, since it is visible but not editable."""
    exercise = _get_visible(db, exercise_id, user)
    if not exercise.is_custom:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Library exercises cannot be changed",
        )
    return exercise


def _name_taken() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="You already have an exercise with that name",
    )


# ---------------------------------------------------------------------------
# Literal paths first - see the note in routes/rewards.py.
# ---------------------------------------------------------------------------


@router.get("/meta", response_model=ExerciseMetaOut)
def exercise_meta(current_user: CurrentUser) -> ExerciseMetaOut:
    """The allowed vocabularies, for filter chips and pickers."""
    return ExerciseMetaOut(
        categories=list(values(ExerciseCategory)),
        equipment=list(values(Equipment)),
        muscle_groups=list(values(MuscleGroup)),
        weight_units=list(values(WeightUnit)),
        measurement_metrics=list(values(MeasurementMetric)),
        measurement_units=list(values(MeasurementUnit)),
    )


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    current_user: CurrentUser,
    db: DbSession,
    q: str | None = Query(default=None, max_length=120, description="Name contains."),
    category: ExerciseCategory | None = None,
    equipment: Equipment | None = None,
    muscle: MuscleGroup | None = Query(default=None, description="Primary muscle group."),
    custom_only: bool = False,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ExerciseOut]:
    """Search the library plus the caller's own exercises, by name."""
    query = select(Exercise).where(store.visible_to(current_user.id))
    if q:
        # Escape LIKE wildcards so a search for "50%" is literal.
        pattern = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Exercise.name.ilike(f"%{pattern}%", escape="\\"))
    if category is not None:
        query = query.where(Exercise.category == category.value)
    if equipment is not None:
        query = query.where(Exercise.equipment == equipment.value)
    if muscle is not None:
        query = query.where(Exercise.primary_muscle_groups.contains([muscle.value]))
    if custom_only:
        query = query.where(Exercise.is_custom.is_(True))
    if not include_archived:
        query = query.where(Exercise.is_archived.is_(False))

    rows = db.scalars(query.order_by(Exercise.name_key).limit(limit).offset(offset))
    return [ExerciseOut.model_validate(e) for e in rows]


@router.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(
    payload: ExerciseCreate, current_user: CurrentUser, db: DbSession
) -> ExerciseOut:
    exercise = Exercise(
        name=clean_name(payload.name),
        name_key=name_key(payload.name),
        category=payload.category.value,
        primary_muscle_groups=[m.value for m in payload.primary_muscle_groups],
        equipment=payload.equipment.value,
        instructions=payload.instructions,
        media_url=payload.media_url,
        is_custom=True,
        created_by_user_id=current_user.id,
    )
    db.add(exercise)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _name_taken() from None
    db.commit()
    db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.get("/{exercise_id}", response_model=ExerciseOut)
def read_exercise(exercise_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ExerciseOut:
    return ExerciseOut.model_validate(_get_visible(db, exercise_id, current_user))


@router.patch("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(
    exercise_id: uuid.UUID,
    payload: ExerciseUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ExerciseOut:
    exercise = _get_own_custom(db, exercise_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        exercise.name = clean_name(payload.name)  # type: ignore[arg-type]
        exercise.name_key = name_key(payload.name)  # type: ignore[arg-type]
    if changes.get("category") is not None:
        exercise.category = payload.category.value  # type: ignore[union-attr]
    if changes.get("equipment") is not None:
        exercise.equipment = payload.equipment.value  # type: ignore[union-attr]
    if changes.get("primary_muscle_groups") is not None:
        exercise.primary_muscle_groups = [m.value for m in payload.primary_muscle_groups]  # type: ignore[union-attr]
    if "instructions" in changes:
        exercise.instructions = payload.instructions
    if "media_url" in changes:
        exercise.media_url = payload.media_url
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise _name_taken() from None
    db.commit()
    db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.delete("/{exercise_id}", response_model=ExerciseDeleteOut)
def delete_exercise(
    exercise_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> ExerciseDeleteOut:
    """Delete a custom exercise - or archive it, if any set or routine still
    references it, so history is never orphaned."""
    exercise = _get_own_custom(db, exercise_id, current_user)
    referenced = db.execute(
        select(
            exists().where(SetEntry.exercise_id == exercise.id)
            | exists().where(RoutineExercise.exercise_id == exercise.id)
        )
    ).scalar_one()
    if referenced:
        exercise.is_archived = True
    else:
        db.delete(exercise)
    db.commit()
    return ExerciseDeleteOut(archived=bool(referenced))


@router.get("/{exercise_id}/history", response_model=list[ExerciseHistoryPoint])
def exercise_history(
    exercise_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=90, ge=1, le=365, description="Most recent N sessions."),
) -> list[ExerciseHistoryPoint]:
    """Per completed session: top weight, best estimated 1RM, volume. Oldest
    first, ready to plot."""
    exercise = _get_visible(db, exercise_id, current_user)

    sessions = db.execute(
        select(WorkoutSession.id, WorkoutSession.started_at)
        .join(SetEntry, SetEntry.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.status == SessionStatus.COMPLETED.value,
            SetEntry.exercise_id == exercise.id,
        )
        .group_by(WorkoutSession.id, WorkoutSession.started_at)
        .order_by(WorkoutSession.started_at.desc())
        .limit(limit)
    ).all()
    if not sessions:
        return []

    sets_by_session: dict[uuid.UUID, list[SetEntry]] = defaultdict(list)
    for entry in db.scalars(
        select(SetEntry).where(
            SetEntry.session_id.in_([s.id for s in sessions]),
            SetEntry.exercise_id == exercise.id,
        )
    ):
        sets_by_session[entry.session_id].append(entry)

    points = []
    for session_id, started_at in reversed(sessions):
        working = [s for s in sets_by_session[session_id] if not s.is_warmup and s.reps]
        top = max(working, key=lambda s: (s.weight_kg, s.reps), default=None)
        estimates = [
            e for e in (prs.est_1rm(s.weight_kg, s.reps) for s in working) if e is not None  # type: ignore[arg-type]
        ]
        points.append(
            ExerciseHistoryPoint(
                session_id=session_id,
                performed_at=started_at,
                top_weight_kg=top.weight_kg if top and top.weight_kg > 0 else None,
                top_weight_reps=top.reps if top and top.weight_kg > 0 else None,
                best_est_1rm=max(estimates) if estimates else None,
                volume_kg=prs.session_volume(store.lift_of(s) for s in working),
                working_sets=len(working),
                total_reps=sum(s.reps or 0 for s in working),
            )
        )
    return points


@router.get("/{exercise_id}/last-performance", response_model=LastPerformanceOut)
def last_performance(
    exercise_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> LastPerformanceOut:
    """The previous completed session's sets - ghost values for an exercise
    added mid-workout. Empty `sets` when it has never been done."""
    exercise = _get_visible(db, exercise_id, current_user)
    hint = hints.suggest(
        store.recent_top_sets(db, current_user.id, [exercise.id]).get(exercise.id, []),
        equipment=exercise.equipment,
        unit=current_user.weight_unit,
    )
    found = store.previous_sets(db, current_user.id, [exercise.id]).get(exercise.id)
    if found is None:
        return LastPerformanceOut(
            exercise_id=exercise.id,
            session_id=None,
            performed_at=None,
            sets=[],
            hint=HintOut.from_hint(hint),
        )
    session, sets = found
    return LastPerformanceOut(
        exercise_id=exercise.id,
        session_id=session.id,
        performed_at=session.started_at,
        sets=[SetOut.model_validate(s) for s in sets],
        hint=HintOut.from_hint(hint),
    )
