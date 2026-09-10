"""Database operations shared by the workout routes: exercise visibility,
personal-record rows, the points ledger, and record replay.

The RULES live in personal_records.py and points_engine.py, which never touch a
database; this module is the thin layer that loads their inputs and persists
their outputs. Nothing here commits - the route owns the transaction, and the
caller must already hold the level_progress lock (progression.lock_progress)
before calling anything that writes.

The session uses autoflush=False, so every helper that queries after a write
flushes explicitly first. Forgetting that would compute caps from a ledger that
is missing the row just added.
"""

import dataclasses
import datetime as dt
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.core import personal_records as prs
from app.core import points_engine as pe
from app.models.workout import (
    Exercise,
    PersonalRecord,
    PointsLedgerEntry,
    SetEntry,
    WorkoutSession,
)
from app.models.workout_enums import LedgerSource, RecordType, SessionStatus

_SET_LEVEL = (LedgerSource.SET_LOGGED.value, LedgerSource.PR_ACHIEVED.value)


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


def visible_to(user_id: uuid.UUID):
    """WHERE clause: the shared library plus the caller's own exercises."""
    return or_(Exercise.is_custom.is_(False), Exercise.created_by_user_id == user_id)


def get_visible_exercise(
    db: Session, exercise_id: uuid.UUID, user_id: uuid.UUID
) -> Exercise | None:
    return db.execute(
        select(Exercise).where(Exercise.id == exercise_id, visible_to(user_id))
    ).scalar_one_or_none()


def lift_of(entry: SetEntry) -> prs.LiftSet:
    return prs.LiftSet(entry.weight_kg, entry.reps, entry.is_warmup)


def previous_sets(
    db: Session,
    user_id: uuid.UUID,
    exercise_ids: Sequence[uuid.UUID],
    exclude_session_id: uuid.UUID | None = None,
) -> dict[uuid.UUID, tuple[WorkoutSession, list[SetEntry]]]:
    """Per exercise, the most recent COMPLETED session's sets - the ghost values.

    Two queries for any number of exercises: DISTINCT ON picks the latest
    session per exercise, then one fetch loads all of their sets.
    """
    if not exercise_ids:
        return {}
    latest = select(SetEntry.exercise_id, SetEntry.session_id).join(
        WorkoutSession, WorkoutSession.id == SetEntry.session_id
    ).where(
        SetEntry.user_id == user_id,
        SetEntry.exercise_id.in_(exercise_ids),
        WorkoutSession.status == SessionStatus.COMPLETED.value,
    )
    if exclude_session_id is not None:
        latest = latest.where(WorkoutSession.id != exclude_session_id)
    pairs = db.execute(
        latest.order_by(SetEntry.exercise_id, WorkoutSession.started_at.desc()).distinct(
            SetEntry.exercise_id
        )
    ).all()
    if not pairs:
        return {}

    keys = [(p.exercise_id, p.session_id) for p in pairs]
    sessions = {
        s.id: s
        for s in db.scalars(
            select(WorkoutSession).where(WorkoutSession.id.in_({k[1] for k in keys}))
        )
    }
    result: dict[uuid.UUID, tuple[WorkoutSession, list[SetEntry]]] = {
        ex_id: (sessions[sess_id], []) for ex_id, sess_id in keys
    }
    for entry in db.scalars(
        select(SetEntry)
        .where(tuple_(SetEntry.exercise_id, SetEntry.session_id).in_(keys))
        .order_by(SetEntry.set_number)
    ):
        result[entry.exercise_id][1].append(entry)
    return result


# ---------------------------------------------------------------------------
# Personal records
# ---------------------------------------------------------------------------


def load_bests(
    db: Session, user_id: uuid.UUID, exercise_id: uuid.UUID
) -> prs.ExerciseBests:
    db.flush()
    rows = db.execute(
        select(
            PersonalRecord.record_type, PersonalRecord.value, PersonalRecord.weight_kg
        ).where(
            PersonalRecord.user_id == user_id, PersonalRecord.exercise_id == exercise_id
        )
    ).all()
    return prs.bests_from_records((r.record_type, r.value, r.weight_kg) for r in rows)


def add_records(
    db: Session,
    *,
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    session_id: uuid.UUID,
    set_id: uuid.UUID | None,
    events: Iterable[prs.PrEvent],
    at: dt.datetime,
) -> list[PersonalRecord]:
    rows = [
        PersonalRecord(
            user_id=user_id,
            exercise_id=exercise_id,
            record_type=e.record_type.value,
            value=e.value,
            weight_kg=e.weight_kg,
            previous_value=e.previous,
            is_baseline=e.is_baseline,
            achieved_at=at,
            session_id=session_id,
            set_id=set_id,
        )
        for e in events
    ]
    db.add_all(rows)
    return rows


def as_event(row: PersonalRecord) -> prs.PrEvent:
    return prs.PrEvent(
        RecordType(row.record_type),
        row.value,
        row.weight_kg,
        row.previous_value,
        row.is_baseline,
    )


def events_for_set(db: Session, set_id: uuid.UUID) -> list[prs.PrEvent]:
    db.flush()
    return [
        as_event(r)
        for r in db.scalars(select(PersonalRecord).where(PersonalRecord.set_id == set_id))
    ]


def replay_exercise(db: Session, user_id: uuid.UUID, exercise_id: uuid.UUID) -> None:
    """Rebuild every record row for one exercise from the surviving sets.

    Called after a set is edited or deleted, or a session abandoned. Abandoned
    sessions' sets are excluded, and every set's is_pr flag is recomputed -
    including sets that only become records because a better one is gone.
    """
    db.flush()
    rows = db.execute(
        select(SetEntry, WorkoutSession.status, WorkoutSession.ended_at)
        .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
        .where(SetEntry.user_id == user_id, SetEntry.exercise_id == exercise_id)
        .order_by(WorkoutSession.started_at, SetEntry.completed_at, SetEntry.id)
    ).all()

    db.execute(
        delete(PersonalRecord).where(
            PersonalRecord.user_id == user_id, PersonalRecord.exercise_id == exercise_id
        )
    )

    sets_by_id: dict[uuid.UUID, SetEntry] = {}
    grouped: dict[uuid.UUID, list[tuple[uuid.UUID, prs.LiftSet]]] = {}
    completed: dict[uuid.UUID, dt.datetime | None] = {}
    for entry, session_status, ended_at in rows:
        entry.is_pr = False
        if session_status == SessionStatus.ABANDONED.value:
            continue
        sets_by_id[entry.id] = entry
        grouped.setdefault(entry.session_id, []).append((entry.id, lift_of(entry)))
        if session_status == SessionStatus.COMPLETED.value:
            completed[entry.session_id] = ended_at

    result = prs.replay(
        [
            prs.ReplaySession(key=sid, completed=sid in completed, sets=sets)
            for sid, sets in grouped.items()
        ]
    )

    for set_id, event in result.set_events:
        entry = sets_by_id[set_id]  # type: ignore[index]
        entry.is_pr = True
        add_records(
            db,
            user_id=user_id,
            exercise_id=exercise_id,
            session_id=entry.session_id,
            set_id=entry.id,
            events=[event],
            at=entry.completed_at,
        )
    for session_id, event in result.volume_events:
        add_records(
            db,
            user_id=user_id,
            exercise_id=exercise_id,
            session_id=session_id,  # type: ignore[arg-type]
            set_id=None,
            events=[event],
            at=completed[session_id] or dt.datetime.now(dt.timezone.utc),  # type: ignore[index]
        )
    db.flush()


# ---------------------------------------------------------------------------
# Points ledger
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SessionLedger:
    """One session's ledger rows, with reversals resolved."""

    entries: tuple[PointsLedgerEntry, ...]

    @property
    def _reversed_ids(self) -> set[uuid.UUID]:
        return {
            e.source_id for e in self.entries if e.source_type == LedgerSource.REVERSAL.value
        }

    def active(self) -> list[PointsLedgerEntry]:
        """Awards that still stand: not reversals, and not reversed."""
        reversed_ids = self._reversed_ids
        return [
            e
            for e in self.entries
            if e.source_type != LedgerSource.REVERSAL.value and e.id not in reversed_ids
        ]

    @property
    def total(self) -> int:
        return sum(e.points for e in self.entries)

    def net(self, source: LedgerSource) -> int:
        return sum(e.points for e in self.active() if e.source_type == source.value)

    def active_for_set(self, set_id: uuid.UUID) -> list[PointsLedgerEntry]:
        return [
            e for e in self.active() if e.source_id == set_id and e.source_type in _SET_LEVEL
        ]

    def pr_bonus_set_ids(self) -> set[uuid.UUID]:
        return {
            e.source_id
            for e in self.active()
            if e.source_type == LedgerSource.PR_ACHIEVED.value
        }

    def gross(self, source: LedgerSource) -> int:
        return sum(e.points for e in self.entries if e.source_type == source.value)


def session_ledger(db: Session, session_id: uuid.UUID) -> SessionLedger:
    db.flush()
    return SessionLedger(
        tuple(
            db.scalars(
                select(PointsLedgerEntry)
                .where(PointsLedgerEntry.session_id == session_id)
                .order_by(PointsLedgerEntry.created_at, PointsLedgerEntry.id)
            )
        )
    )


def add_award(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    award: pe.Award,
    source_id: uuid.UUID,
    period_key: str | None = None,
) -> PointsLedgerEntry:
    row = PointsLedgerEntry(
        user_id=user_id,
        source_type=award.source_type.value,
        source_id=source_id,
        points=award.points,
        session_id=session_id,
        period_key=period_key,
        reason=award.reason[:120],
    )
    db.add(row)
    return row


def reverse(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    entries: Iterable[PointsLedgerEntry],
    reason: str,
) -> int:
    """Append a reversal row per entry. Returns the (positive) total reversed.

    uq_points_ledger_once makes a second reversal of the same entry impossible,
    so a retried request cannot claw back twice.
    """
    total = 0
    for entry in entries:
        db.add(
            PointsLedgerEntry(
                user_id=user_id,
                source_type=LedgerSource.REVERSAL.value,
                source_id=entry.id,
                points=-entry.points,
                session_id=session_id,
                reason=f"{reason}: {entry.reason}"[:120],
            )
        )
        total += entry.points
    return total


def workout_points_credited(db: Session, user_id: uuid.UUID) -> int:
    """Lifetime shop points credited by finished workouts. The wallet and the
    profile add this to quest points so "earned" reconciles with the balance."""
    return int(
        db.execute(
            select(func.coalesce(func.sum(WorkoutSession.points_credited), 0)).where(
                WorkoutSession.user_id == user_id
            )
        ).scalar_one()
    )


# ---------------------------------------------------------------------------
# Weekly streak inputs
# ---------------------------------------------------------------------------


def qualified_weeks(db: Session, user_id: uuid.UUID) -> dict[str, int]:
    db.flush()
    rows = db.execute(
        select(WorkoutSession.week_key, func.count(WorkoutSession.id))
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.status == SessionStatus.COMPLETED.value,
            WorkoutSession.qualified.is_(True),
            WorkoutSession.week_key.is_not(None),
        )
        .group_by(WorkoutSession.week_key)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def streak_paid(db: Session, user_id: uuid.UUID, week: str) -> bool:
    db.flush()
    return (
        db.execute(
            select(PointsLedgerEntry.id).where(
                PointsLedgerEntry.user_id == user_id,
                PointsLedgerEntry.source_type == LedgerSource.STREAK_BONUS.value,
                PointsLedgerEntry.period_key == week,
            )
        ).first()
        is not None
    )
