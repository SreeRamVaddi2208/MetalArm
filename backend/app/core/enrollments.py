"""Following a Library program: which one, and where in it the user is.

An enrollment's (current_week, current_day) always points at the NEXT workout
to do - a training day, never a rest day. Finishing a session started from
that workout moves it on to the next training day; past the last one the
program is complete. Skipping a day breaks nothing: the next workout simply
waits until it is done.

None of this touches points. Advancing is bookkeeping that runs after a
session's points, records and streak are settled (routes/workouts.py
finish_session), and a session started from a program day earns exactly what
any other session earns.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.library import LibraryProgram, LibraryProgramDay, LibraryWorkout, ProgramEnrollment
from app.models.user import User
from app.models.workout import WorkoutSession

ACTIVE, PAUSED, COMPLETED = "active", "paused", "completed"


def training_days(db: Session, program_id) -> list[LibraryProgramDay]:
    """The program's workout days, in order."""
    return list(db.scalars(
        select(LibraryProgramDay)
        .where(LibraryProgramDay.program_id == program_id, LibraryProgramDay.workout_id.is_not(None))
        .order_by(LibraryProgramDay.week_number, LibraryProgramDay.day_number)
    ))


def active(db: Session, user: User) -> ProgramEnrollment | None:
    return db.scalar(
        select(ProgramEnrollment).where(ProgramEnrollment.user_id == user.id, ProgramEnrollment.status == ACTIVE)
    )


def for_program(db: Session, user: User, program: LibraryProgram) -> ProgramEnrollment | None:
    return db.scalar(
        select(ProgramEnrollment).where(
            ProgramEnrollment.user_id == user.id, ProgramEnrollment.program_id == program.id
        )
    )


def next_day(db: Session, enrollment: ProgramEnrollment) -> LibraryProgramDay | None:
    """The training day the enrollment points at: its current position, or the
    first training day after it (a re-import may have moved rest days)."""
    position = (enrollment.current_week, enrollment.current_day)
    return next(
        (d for d in training_days(db, enrollment.program_id) if (d.week_number, d.day_number) >= position),
        None,
    )


def next_workout(db: Session, enrollment: ProgramEnrollment) -> LibraryWorkout | None:
    day = next_day(db, enrollment)
    return db.get(LibraryWorkout, day.workout_id) if day else None


def follow(db: Session, user: User, program: LibraryProgram) -> ProgramEnrollment:
    """Start or resume following a program. Following another pauses the one
    before it; a completed program starts again from its first day."""
    current = active(db, user)
    if current is not None and current.program_id != program.id:
        current.status = PAUSED
        db.flush()
    enrollment = for_program(db, user, program)
    days = training_days(db, program.id)
    first = (days[0].week_number, days[0].day_number) if days else (1, 1)
    if enrollment is None:
        enrollment = ProgramEnrollment(
            user_id=user.id, program_id=program.id, current_week=first[0], current_day=first[1], status=ACTIVE
        )
        db.add(enrollment)
    else:
        if enrollment.status == COMPLETED:
            enrollment.current_week, enrollment.current_day = first
        enrollment.status = ACTIVE
    db.flush()
    return enrollment


def pause(db: Session, user: User, program: LibraryProgram) -> ProgramEnrollment | None:
    enrollment = for_program(db, user, program)
    if enrollment is not None and enrollment.status == ACTIVE:
        enrollment.status = PAUSED
        db.flush()
    return enrollment


def attach_for_start(db: Session, user: User, workout: LibraryWorkout) -> ProgramEnrollment | None:
    """The active enrollment, when the workout being started is its next one -
    so finishing the session moves the program on."""
    enrollment = active(db, user)
    if enrollment is None:
        return None
    day = next_day(db, enrollment)
    return enrollment if day is not None and day.workout_id == workout.id else None


def on_session_finished(db: Session, session: WorkoutSession) -> None:
    """Move the program on, if this session was its next workout. Called once
    a session has finished, after every reward is settled."""
    if session.program_enrollment_id is None or session.library_workout_id is None:
        return
    enrollment = db.scalar(
        select(ProgramEnrollment).where(ProgramEnrollment.id == session.program_enrollment_id).with_for_update()
    )
    if enrollment is None or enrollment.status != ACTIVE:
        return
    day = next_day(db, enrollment)
    if day is None or day.workout_id != session.library_workout_id:
        return
    later = next(
        (d for d in training_days(db, enrollment.program_id)
         if (d.week_number, d.day_number) > (day.week_number, day.day_number)),
        None,
    )
    if later is None:
        enrollment.status = COMPLETED
    else:
        enrollment.current_week, enrollment.current_day = later.week_number, later.day_number
    db.flush()
