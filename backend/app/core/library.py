"""Which routines somebody actually reaches for.

Only the pin is stored (`routines.pinned_at`). How often a routine has been
used, and how recently, are counted from the sessions that name it - the same
rule leagues, raids and duels follow, and for the same reason: a stored counter
can disagree with the rows behind it, and a deleted session would leave it
overstating.

Pinned first, then most-used, then most-recent, then by name so the order is
stable rather than arbitrary when two routines tie.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.workout import Routine, RoutineExercise, WorkoutSession
from app.models.workout_enums import SessionStatus


@dataclasses.dataclass(frozen=True)
class LibraryRow:
    routine: Routine
    exercise_count: int
    use_count: int
    last_used_at: dt.datetime | None

    @property
    def is_pinned(self) -> bool:
        return self.routine.pinned_at is not None


def ranked(db: Session, user_id: uuid.UUID) -> list[LibraryRow]:
    """Every routine the user has, in the order the Library shows them."""
    routines = list(
        db.scalars(select(Routine).where(Routine.user_id == user_id).order_by(Routine.name))
    )
    if not routines:
        return []

    ids = [routine.id for routine in routines]
    # Finished sessions only: abandoning a workout is not using a routine.
    usage = {
        routine_id: (count, last)
        for routine_id, count, last in db.execute(
            select(
                WorkoutSession.routine_id,
                func.count(WorkoutSession.id),
                func.max(WorkoutSession.ended_at),
            )
            .where(WorkoutSession.routine_id.in_(ids))
            .where(WorkoutSession.status == SessionStatus.COMPLETED.value)
            .group_by(WorkoutSession.routine_id)
        ).all()
    }
    sizes = {
        routine_id: count
        for routine_id, count in db.execute(
            select(RoutineExercise.routine_id, func.count(RoutineExercise.id))
            .where(RoutineExercise.routine_id.in_(ids))
            .group_by(RoutineExercise.routine_id)
        ).all()
    }

    rows = [
        LibraryRow(
            routine=routine,
            exercise_count=sizes.get(routine.id, 0),
            use_count=usage.get(routine.id, (0, None))[0],
            last_used_at=usage.get(routine.id, (0, None))[1],
        )
        for routine in routines
    ]
    # Sorted in Python rather than SQL: the list is one user's routines, so it
    # is small, and the tie-breaking reads as the rule it is.
    epoch = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    rows.sort(key=lambda row: (
        not row.is_pinned,
        -row.use_count,
        -(row.last_used_at or epoch).timestamp(),
        row.routine.name.lower(),
    ))
    return rows
