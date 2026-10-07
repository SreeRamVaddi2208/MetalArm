"""Routines: reusable workout templates a session can be started from."""

import datetime as dt
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, DbSession
from app.core import workout_store as store
from app.models.user import User
from app.models.program import Program
from app.models.workout import (
    Exercise, Routine, RoutineExercise, SessionExercise, SetEntry, WorkoutSession,
)
from app.models.workout_enums import SessionStatus
from pydantic import BaseModel, Field
from app.schemas.workout import (
    ExerciseOut,
    RoutineExerciseIn,
    RoutineExerciseOut,
    RoutineIn,
    RoutineOut,
)

router = APIRouter(prefix="/routines", tags=["routines"])


def _get_owned(db: Session, routine_id: uuid.UUID, user: User) -> Routine:
    routine = db.execute(
        select(Routine)
        .where(Routine.id == routine_id, Routine.user_id == user.id)
        .options(selectinload(Routine.exercises).selectinload(RoutineExercise.exercise))
    ).scalar_one_or_none()
    if routine is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")
    return routine


def _check_exercises(db: Session, user: User, slots: list[RoutineExerciseIn]) -> None:
    """Every slot must name an exercise the caller can see and has not
    archived. A 422 naming the bad ids, rather than a foreign-key 500 - and a
    guard against referencing another user's private exercise by id."""
    wanted = {slot.exercise_id for slot in slots}
    if not wanted:
        return
    usable = set(
        db.scalars(
            select(Exercise.id).where(
                Exercise.id.in_(wanted),
                store.visible_to(user.id),
                Exercise.is_archived.is_(False),
            )
        )
    )
    missing = wanted - usable
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown or archived exercise(s): " + ", ".join(sorted(map(str, missing))),
        )


def _slots(slots: list[RoutineExerciseIn]) -> list[RoutineExercise]:
    return [
        RoutineExercise(
            position=index,
            exercise_id=slot.exercise_id,
            target_sets=slot.target_sets,
            # A range wins; the single figure is then its top.
            target_reps=slot.target_reps_high or slot.target_reps,
            target_reps_low=slot.target_reps_low or slot.target_reps,
            target_reps_high=slot.target_reps_high or slot.target_reps,
            superset_group=slot.superset_group,
            notes=slot.notes,
            target_weight_kg=(
                Decimal(str(slot.target_weight_kg)).quantize(Decimal("0.01"))
                if slot.target_weight_kg is not None
                else None
            ),
            rest_seconds=slot.rest_seconds,
        )
        for index, slot in enumerate(slots)
    ]


def last_performed(db: Session, routine_ids: list[uuid.UUID]) -> dict[uuid.UUID, dt.datetime]:
    """When a workout from each routine was last finished."""
    if not routine_ids:
        return {}
    return dict(db.execute(
        select(WorkoutSession.routine_id, func.max(WorkoutSession.ended_at))
        .where(WorkoutSession.routine_id.in_(routine_ids),
               WorkoutSession.status == SessionStatus.COMPLETED.value)
        .group_by(WorkoutSession.routine_id)
    ).tuples().all())


def _check_program(db: Session, user: User, program_id: uuid.UUID | None) -> None:
    if program_id is None:
        return
    owned = db.execute(
        select(Program.id).where(Program.id == program_id, Program.owner_user_id == user.id)
    ).first()
    if owned is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")


def _out(routine: Routine, last: dt.datetime | None = None) -> RoutineOut:
    return RoutineOut(
        id=routine.id,
        name=routine.name,
        notes=routine.notes,
        program_id=routine.program_id,
        order_in_program=routine.order_in_program,
        color=routine.color,
        last_performed_at=last,
        exercises=[
            RoutineExerciseOut(
                position=slot.position,
                exercise=ExerciseOut.model_validate(slot.exercise),
                target_sets=slot.target_sets,
                target_reps=slot.target_reps,
                target_reps_low=slot.target_reps_low,
                target_reps_high=slot.target_reps_high,
                target_weight_kg=slot.target_weight_kg,
                rest_seconds=slot.rest_seconds,
                superset_group=slot.superset_group,
                notes=slot.notes,
            )
            for slot in routine.exercises
        ],
        created_at=routine.created_at,
        updated_at=routine.updated_at,
    )


@router.get("", response_model=list[RoutineOut])
def list_routines(current_user: CurrentUser, db: DbSession) -> list[RoutineOut]:
    rows = db.scalars(
        select(Routine)
        .where(Routine.user_id == current_user.id)
        .options(selectinload(Routine.exercises).selectinload(RoutineExercise.exercise))
        .order_by(Routine.updated_at.desc())
    ).all()
    last = last_performed(db, [r.id for r in rows])
    return [_out(r, last.get(r.id)) for r in rows]


@router.post("", response_model=RoutineOut, status_code=status.HTTP_201_CREATED)
def create_routine(payload: RoutineIn, current_user: CurrentUser, db: DbSession) -> RoutineOut:
    _check_exercises(db, current_user, payload.exercises)
    _check_program(db, current_user, payload.program_id)
    routine = Routine(
        user_id=current_user.id, name=payload.name.strip(), notes=payload.notes,
        program_id=payload.program_id, order_in_program=payload.order_in_program,
        color=payload.color,
    )
    routine.exercises = _slots(payload.exercises)
    db.add(routine)
    db.commit()
    return _out(_get_owned(db, routine.id, current_user))


class FromSessionIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)


@router.post("/from-session/{session_id}", response_model=RoutineOut,
             status_code=status.HTTP_201_CREATED)
def routine_from_session(
    session_id: uuid.UUID, payload: FromSessionIn, current_user: CurrentUser, db: DbSession
) -> RoutineOut:
    """"Save as routine" on the workout summary: the session's cards, in
    order, with their supersets, notes and rest. Each slot's target is what
    was done - the working-set count and the top working set's reps and
    weight - so the routine starts where this workout left off."""
    session = db.get(WorkoutSession, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found")
    if session.status != SessionStatus.COMPLETED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the workout first")
    cards = db.scalars(
        select(SessionExercise).where(SessionExercise.session_id == session.id)
        .order_by(SessionExercise.position)
    ).all()
    sets = db.scalars(
        select(SetEntry).where(SetEntry.session_id == session.id, SetEntry.is_warmup.is_(False))
    ).all()
    by_card: dict[uuid.UUID, list[SetEntry]] = {}
    for entry in sets:
        by_card.setdefault(entry.session_exercise_id, []).append(entry)
    slots = []
    for card in cards:
        done = by_card.get(card.id, [])
        if not done:
            continue
        top = max(done, key=lambda e: (e.weight_kg or 0, e.reps or 0))
        slots.append(RoutineExerciseIn(
            exercise_id=card.exercise_id, target_sets=min(len(done), 50),
            target_reps=top.reps or None,
            target_weight_kg=float(top.weight_kg) if top.weight_kg else None,
            rest_seconds=card.rest_seconds, superset_group=card.superset_group, notes=card.notes,
        ))
    if not slots:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This workout has no working sets")
    routine = Routine(user_id=current_user.id,
                      name=(payload.name or session.name or "Saved workout").strip()[:80])
    routine.exercises = _slots(slots[:40])
    db.add(routine)
    db.commit()
    return _out(_get_owned(db, routine.id, current_user))


@router.get("/{routine_id}", response_model=RoutineOut)
def read_routine(routine_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> RoutineOut:
    routine = _get_owned(db, routine_id, current_user)
    return _out(routine, last_performed(db, [routine.id]).get(routine.id))


@router.put("/{routine_id}", response_model=RoutineOut)
def replace_routine(
    routine_id: uuid.UUID, payload: RoutineIn, current_user: CurrentUser, db: DbSession
) -> RoutineOut:
    """Full replace. The ordered exercise list is swapped as a whole."""
    routine = _get_owned(db, routine_id, current_user)
    _check_exercises(db, current_user, payload.exercises)
    _check_program(db, current_user, payload.program_id)
    routine.name = payload.name.strip()
    routine.notes = payload.notes
    routine.program_id = payload.program_id
    routine.order_in_program = payload.order_in_program
    routine.color = payload.color
    routine.exercises.clear()
    # Flush the deletions BEFORE adding the new slots: uq_routine_exercise_
    # position would otherwise see old and new rows at the same position.
    db.flush()
    routine.exercises.extend(_slots(payload.exercises))
    db.commit()
    db.expire_all()
    return _out(_get_owned(db, routine_id, current_user))


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(routine_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Workouts started from it keep their history (routine_id is SET NULL)."""
    db.delete(_get_owned(db, routine_id, current_user))
    db.commit()
