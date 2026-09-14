"""Workout sessions: start, log sets, finish, abandon - and the points, XP and
personal records they produce.

Transaction shape, shared by every write here and by routes/quests.py:

1. Lock level_progress FOR UPDATE before touching any workout row. Every
   writer takes this lock first, so one user's concurrent requests run one at
   a time: the per-session caps are computed from a ledger nothing else can be
   writing to, and a double-tapped submit waits, then finds the first set.
2. Write the workout rows, then the ledger rows, then apply XP.
3. Commit once. A failure anywhere rolls back everything, so no award exists
   without the set that earned it.

Why XP and shop points are applied at different times
-----------------------------------------------------
XP moves as each award is made, so the XP bar and level-up animation respond
to every logged set. Shop points are credited once, at finish, as the session's
net ledger total. Sets can be edited or deleted only while a session is in
progress, and editing reverses awards - if shop points were credited live, a
user could spend them in the rewards shop and then delete the set, and the
reversal would have to debit points already spent
(ck_progress_points_non_negative would reject it). Crediting at finish, when
the sets become immutable, means a reversal only ever touches XP.
"""

import dataclasses
import datetime as dt
import logging
import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import personal_records as prs
from app.core import points_engine as pe
from app.core import workout_rules as rules
from app.core import workout_store as store
from app.core import raids
from app.core import workout_streaks as streaks
from app.core.periods import local_now, resolve_timezone
from app.core.progression import (
    ProgressionDelta,
    apply_completion,
    apply_xp,
    lock_progress,
)
from app.models.user import User
from app.models.workout import (
    Exercise,
    PersonalRecord,
    PointsLedgerEntry,
    Routine,
    SetEntry,
    WorkoutSession,
)
from app.models.workout_enums import LedgerSource, RecordType, SessionStatus
from app.schemas.quest import ProgressionDeltaOut
from app.schemas.workout import (
    AbandonResponse,
    ActiveSessionOut,
    AwardOut,
    ExerciseOut,
    FinishResponse,
    LedgerEntryOut,
    PointsBreakdownOut,
    PointsSummaryOut,
    PrEventOut,
    RecordOut,
    SessionExerciseOut,
    SessionOut,
    SessionStart,
    SessionSummaryOut,
    SessionTargetOut,
    SetCreate,
    SetDeleteResponse,
    SetLogResponse,
    SetOut,
    SetUpdate,
    StreakOut,
    to_kg,
)

logger = logging.getLogger("metalarm.workouts")

router = APIRouter(prefix="/workouts", tags=["workouts"])

_TENTH = Decimal("0.1")
_CENTS = Decimal("0.01")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _rpe(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(_TENTH, ROUND_HALF_UP)


def _distance(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(_CENTS, ROUND_HALF_UP)


def _delta_out(delta: ProgressionDelta) -> ProgressionDeltaOut:
    return ProgressionDeltaOut(
        **{**delta.__dict__, "leveled_up": delta.leveled_up, "ranked_up": delta.ranked_up}
    )


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def _get_owned_session(db: Session, session_id: uuid.UUID, user: User) -> WorkoutSession:
    """404 rather than 403 for another user's session - a 403 would confirm the
    id exists. Same rule as quests."""
    session = db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id, WorkoutSession.user_id == user.id
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    return session


def _require_live(session: WorkoutSession) -> None:
    if session.status != SessionStatus.IN_PROGRESS.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This workout is already {session.status}",
        )


def _get_set(db: Session, session: WorkoutSession, set_id: uuid.UUID) -> SetEntry:
    entry = db.execute(
        select(SetEntry).where(SetEntry.id == set_id, SetEntry.session_id == session.id)
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")
    return entry


def _active_session(db: Session, user: User) -> WorkoutSession | None:
    return db.execute(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == SessionStatus.IN_PROGRESS.value,
        )
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _duration_seconds(session: WorkoutSession) -> int:
    end = session.ended_at or _now()
    return max(0, int((end - session.started_at).total_seconds()))


def _working(sets: list[SetEntry]) -> list[SetEntry]:
    return [s for s in sets if not s.is_warmup]


def _volume(sets: list[SetEntry]) -> Decimal:
    return prs.session_volume(store.lift_of(s) for s in sets)


def _pr_events_out(
    rows: list[PersonalRecord],
    names: dict[uuid.UUID, str],
    bonus_set_ids: set[uuid.UUID],
) -> list[PrEventOut]:
    """Records as the UI sees them, flagging the one each PR bonus paid for.

    The flag is recomputed with the engine's own pick_bonus_record, so it
    always marks the record the award was actually made for.
    """
    by_set: dict[uuid.UUID | None, list[PersonalRecord]] = defaultdict(list)
    for row in rows:
        by_set[row.set_id].append(row)

    paid: set[uuid.UUID] = set()
    for set_id, set_rows in by_set.items():
        if set_id is None or set_id not in bonus_set_ids:
            continue
        chosen = pe.pick_bonus_record([store.as_event(r) for r in set_rows])
        if chosen is not None:
            paid |= {
                r.id for r in set_rows if r.record_type == chosen.record_type.value
            }

    return [
        PrEventOut(
            exercise_id=r.exercise_id,
            exercise_name=names.get(r.exercise_id, ""),
            record_type=r.record_type,
            value=r.value,
            weight_kg=r.weight_kg,
            previous_value=r.previous_value,
            is_baseline=r.is_baseline,
            bonus_awarded=r.id in paid,
            set_id=r.set_id,
        )
        for r in rows
    ]


def _session_out(db: Session, session: WorkoutSession, user: User) -> SessionOut:
    sets = list(
        db.scalars(
            select(SetEntry)
            .where(SetEntry.session_id == session.id)
            .order_by(SetEntry.completed_at, SetEntry.set_number)
        )
    )

    # Planned exercises first, in routine order, then anything added ad hoc in
    # the order it was first logged.
    targets: dict[uuid.UUID, SessionTargetOut] = {}
    if session.routine_id is not None:
        routine = db.get(Routine, session.routine_id)
        for slot in routine.exercises if routine else []:
            targets.setdefault(
                slot.exercise_id,
                SessionTargetOut(
                    target_sets=slot.target_sets,
                    target_reps=slot.target_reps,
                    target_weight_kg=slot.target_weight_kg,
                    rest_seconds=slot.rest_seconds,
                ),
            )
    order = list(targets)
    for entry in sets:
        if entry.exercise_id not in targets and entry.exercise_id not in order:
            order.append(entry.exercise_id)

    exercises = {
        e.id: e for e in db.scalars(select(Exercise).where(Exercise.id.in_(order)))
    } if order else {}
    previous = store.previous_sets(db, user.id, order, exclude_session_id=session.id)

    grouped: dict[uuid.UUID, list[SetEntry]] = defaultdict(list)
    for entry in sets:
        grouped[entry.exercise_id].append(entry)

    working = _working(sets)
    return SessionOut(
        id=session.id,
        name=session.name,
        status=session.status,
        routine_id=session.routine_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=_duration_seconds(session),
        working_sets=len(working),
        total_volume_kg=_volume(sets),
        points_total=store.session_ledger(db, session.id).total,
        points_credited=session.points_credited,
        qualified=session.qualified,
        exercises=[
            SessionExerciseOut(
                exercise=ExerciseOut.model_validate(exercises[ex_id]),
                target=targets.get(ex_id),
                sets=[SetOut.model_validate(s) for s in grouped.get(ex_id, [])],
                previous_sets=[
                    SetOut.model_validate(s) for s in previous.get(ex_id, (None, []))[1]
                ],
            )
            for ex_id in order
            if ex_id in exercises
        ],
    )


def _summaries(db: Session, sessions: list[WorkoutSession]) -> list[SessionSummaryOut]:
    """History rows. A fixed number of grouped queries for the whole page,
    rather than several per session."""
    ids = [s.id for s in sessions]
    sets_by_session: dict[uuid.UUID, list[SetEntry]] = defaultdict(list)
    points: dict[uuid.UUID, int] = {}
    prs_count: dict[uuid.UUID, int] = {}
    if ids:
        for entry in db.scalars(select(SetEntry).where(SetEntry.session_id.in_(ids))):
            sets_by_session[entry.session_id].append(entry)
        points = {
            row[0]: int(row[1])
            for row in db.execute(
                select(PointsLedgerEntry.session_id, func.sum(PointsLedgerEntry.points))
                .where(PointsLedgerEntry.session_id.in_(ids))
                .group_by(PointsLedgerEntry.session_id)
            )
        }
        prs_count = {
            row[0]: int(row[1])
            for row in db.execute(
                select(PersonalRecord.session_id, func.count(PersonalRecord.id))
                .where(
                    PersonalRecord.session_id.in_(ids),
                    PersonalRecord.is_baseline.is_(False),
                )
                .group_by(PersonalRecord.session_id)
            )
        }

    out = []
    for s in sessions:
        sets = sets_by_session.get(s.id, [])
        out.append(
            SessionSummaryOut(
                id=s.id,
                name=s.name,
                status=s.status,
                started_at=s.started_at,
                ended_at=s.ended_at,
                duration_seconds=_duration_seconds(s),
                working_sets=len(_working(sets)),
                exercise_count=len({e.exercise_id for e in sets}),
                total_volume_kg=_volume(sets),
                points_total=points.get(s.id, 0),
                pr_count=prs_count.get(s.id, 0),
            )
        )
    return out


def _streak_out(state: streaks.WeeklyStreak) -> StreakOut:
    return StreakOut(
        weeks=state.weeks,
        this_week_sessions=state.this_week_sessions,
        target=state.target,
        this_week_done=state.this_week_done,
        sessions_to_go=state.sessions_to_go,
    )


def _current_streak(db: Session, user: User) -> streaks.WeeklyStreak:
    return streaks.weekly_streak(
        store.qualified_weeks(db, user.id), streaks.week_key(_now(), user.timezone)
    )


# ---------------------------------------------------------------------------
# Awarding a set - shared by logging and editing
# ---------------------------------------------------------------------------


def _award_set(
    db: Session,
    *,
    user: User,
    session: WorkoutSession,
    entry: SetEntry,
    events: list[prs.PrEvent],
) -> pe.SetOutcome:
    ledger = store.session_ledger(db, session.id)
    same_exercise = set(
        db.scalars(
            select(SetEntry.id).where(
                SetEntry.session_id == session.id,
                SetEntry.exercise_id == entry.exercise_id,
                SetEntry.id != entry.id,
            )
        )
    )
    bonus_sets = ledger.pr_bonus_set_ids()
    outcome = pe.award_for_set(
        pe.SetContext(
            is_warmup=entry.is_warmup,
            session_set_points=ledger.net(LedgerSource.SET_LOGGED),
            session_pr_bonuses=len(bonus_sets),
            exercise_has_pr_bonus=bool(bonus_sets & same_exercise),
            pr_events=tuple(events),
        )
    )
    for award in outcome.awards:
        store.add_award(
            db, user_id=user.id, session_id=session.id, award=award, source_id=entry.id
        )
    return outcome


def _set_response(
    db: Session,
    *,
    session: WorkoutSession,
    entry: SetEntry,
    exercise: Exercise,
    outcome: pe.SetOutcome | None,
    points: int,
    delta: ProgressionDelta,
    duplicate: bool = False,
) -> SetLogResponse:
    ledger = store.session_ledger(db, session.id)
    rows = list(db.scalars(select(PersonalRecord).where(PersonalRecord.set_id == entry.id)))
    return SetLogResponse(
        set=SetOut.model_validate(entry),
        pr_events=_pr_events_out(rows, {exercise.id: exercise.name}, ledger.pr_bonus_set_ids()),
        awards=[
            AwardOut(source_type=a.source_type.value, points=a.points, reason=a.reason)
            for a in (outcome.awards if outcome else ())
        ],
        points_awarded=points,
        session_points=ledger.total,
        set_cap_reached=(
            ledger.net(LedgerSource.SET_LOGGED) >= rules.SET_POINTS_CAP_PER_SESSION
        ),
        progression=_delta_out(delta),
        is_duplicate=duplicate,
    )


# ---------------------------------------------------------------------------
# Sessions. Literal paths are declared before /sessions/{session_id} so they
# are not parsed as a UUID.
# ---------------------------------------------------------------------------


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(payload: SessionStart, current_user: CurrentUser, db: DbSession) -> SessionOut:
    """Start a workout, blank or from a routine. 409 if one is already live -
    finish or abandon it first (GET /workouts/sessions/active returns it)."""
    routine = None
    if payload.routine_id is not None:
        routine = db.execute(
            select(Routine).where(
                Routine.id == payload.routine_id, Routine.user_id == current_user.id
            )
        ).scalar_one_or_none()
        if routine is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found")

    session = WorkoutSession(
        user_id=current_user.id,
        routine_id=routine.id if routine else None,
        name=payload.name or (routine.name if routine else None),
        started_at=_now(),
        status=SessionStatus.IN_PROGRESS.value,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError:
        # uq_workout_sessions_one_active: the database, not a Python check, is
        # what stops two concurrent "start" taps both succeeding.
        db.rollback()
        active = _active_session(db, current_user)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A workout is already in progress"
                + (f" ({active.id})" if active else "")
                + " - finish or abandon it first"
            ),
        ) from None
    db.commit()
    db.refresh(session)
    return _session_out(db, session, current_user)


@router.get("/sessions/active", response_model=ActiveSessionOut)
def read_active_session(current_user: CurrentUser, db: DbSession) -> ActiveSessionOut:
    """The in-progress workout, or `session: null`. What the UI calls on load
    to rehydrate a workout after a refresh."""
    session = _active_session(db, current_user)
    return ActiveSessionOut(session=_session_out(db, session, current_user) if session else None)


@router.get("/sessions", response_model=list[SessionSummaryOut])
def list_sessions(
    current_user: CurrentUser,
    db: DbSession,
    session_status: SessionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    before: dt.datetime | None = Query(
        default=None, description="Cursor: only sessions started before this instant."
    ),
) -> list[SessionSummaryOut]:
    """Workout history, newest first."""
    query = select(WorkoutSession).where(WorkoutSession.user_id == current_user.id)
    if session_status is not None:
        query = query.where(WorkoutSession.status == session_status.value)
    if before is not None:
        query = query.where(WorkoutSession.started_at < before)
    sessions = list(db.scalars(query.order_by(WorkoutSession.started_at.desc()).limit(limit)))
    return _summaries(db, sessions)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def read_session(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> SessionOut:
    return _session_out(db, _get_owned_session(db, session_id, current_user), current_user)


@router.post(
    "/sessions/{session_id}/sets",
    response_model=SetLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def log_set(
    session_id: uuid.UUID, payload: SetCreate, current_user: CurrentUser, db: DbSession
) -> SetLogResponse:
    """Log a set. Records and points are settled before this returns, so the
    response alone tells the UI whether to celebrate a PR or a level-up."""
    progress = lock_progress(db, current_user.id)
    session = _get_owned_session(db, session_id, current_user)
    _require_live(session)

    now = _now()
    if now - session.started_at > dt.timedelta(hours=rules.MAX_SESSION_HOURS):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This workout has been open for over {rules.MAX_SESSION_HOURS} hours"
                " - finish or abandon it and start a new one"
            ),
        )

    exercise = store.get_visible_exercise(db, payload.exercise_id, current_user.id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    if payload.client_set_id is not None:
        existing = db.execute(
            select(SetEntry).where(
                SetEntry.session_id == session.id,
                SetEntry.client_set_id == payload.client_set_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            # A retry of a submit that already landed. The lock above means the
            # original has committed, so it is found here and not re-awarded.
            delta = apply_xp(progress, xp=0, at=now, tz_name=current_user.timezone)
            response = _set_response(
                db,
                session=session,
                entry=existing,
                exercise=db.get(Exercise, existing.exercise_id) or exercise,
                outcome=None,
                points=0,
                delta=delta,
                duplicate=True,
            )
            db.rollback()
            return response

    if exercise.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That exercise has been archived"
        )

    set_number = (
        db.execute(
            select(func.count(SetEntry.id)).where(
                SetEntry.session_id == session.id, SetEntry.exercise_id == exercise.id
            )
        ).scalar_one()
        + 1
    )
    entry = SetEntry(
        session_id=session.id,
        user_id=current_user.id,
        exercise_id=exercise.id,
        set_number=set_number,
        weight_kg=payload.weight_kg,
        reps=payload.reps,
        rpe=_rpe(payload.rpe),
        duration_seconds=payload.duration_seconds,
        distance_m=_distance(payload.distance_m),
        is_warmup=payload.is_warmup,
        completed_at=now,
        client_set_id=payload.client_set_id,
    )
    db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That set was already logged"
        ) from None

    events = prs.detect(store.load_bests(db, current_user.id, exercise.id), store.lift_of(entry))
    store.add_records(
        db,
        user_id=current_user.id,
        exercise_id=exercise.id,
        session_id=session.id,
        set_id=entry.id,
        events=events,
        at=now,
    )
    # A first-ever baseline is recorded but is not a PR - the UI must not
    # badge a set "PR" in the same breath as calling it a baseline.
    entry.is_pr = any(not e.is_baseline for e in events)

    outcome = _award_set(db, user=current_user, session=session, entry=entry, events=events)
    delta = apply_xp(progress, xp=outcome.total, at=now, tz_name=current_user.timezone)

    response = _set_response(
        db, session=session, entry=entry, exercise=exercise, outcome=outcome,
        points=outcome.total, delta=delta,
    )
    db.commit()

    if outcome.bonus_record is not None:
        logger.info("user %s PR on %s", current_user.id, exercise.name)
    return response


@router.patch("/sessions/{session_id}/sets/{set_id}", response_model=SetLogResponse)
def update_set(
    session_id: uuid.UUID,
    set_id: uuid.UUID,
    payload: SetUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> SetLogResponse:
    """Fix a typo in a set while the workout is live.

    Implemented as reverse-then-re-award: the set's standing awards are
    reversed, the exercise's records are rebuilt from history, and the edited
    set is judged afresh. Other sets' awards are not revisited.
    """
    progress = lock_progress(db, current_user.id)
    session = _get_owned_session(db, session_id, current_user)
    _require_live(session)
    entry = _get_set(db, session, set_id)

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("weight") is not None:
        kg = to_kg(payload.weight, payload.unit)  # type: ignore[arg-type]
        if kg > rules.MAX_WEIGHT_KG:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"weight must be at most {rules.MAX_WEIGHT_KG} kg",
            )
        entry.weight_kg = kg
    if "reps" in changes:
        entry.reps = payload.reps
    if "duration_seconds" in changes:
        entry.duration_seconds = payload.duration_seconds
    if "distance_m" in changes:
        entry.distance_m = _distance(payload.distance_m)
    if "rpe" in changes:
        entry.rpe = _rpe(payload.rpe)
    if changes.get("is_warmup") is not None:
        entry.is_warmup = bool(payload.is_warmup)

    if entry.reps is None and entry.duration_seconds is None and entry.distance_m is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="a set needs reps, a duration, or a distance",
        )

    now = _now()
    ledger = store.session_ledger(db, session.id)
    reversed_points = store.reverse(
        db,
        user_id=current_user.id,
        session_id=session.id,
        entries=ledger.active_for_set(entry.id),
        reason="Set edited",
    )
    store.replay_exercise(db, current_user.id, entry.exercise_id)
    outcome = _award_set(
        db,
        user=current_user,
        session=session,
        entry=entry,
        events=store.events_for_set(db, entry.id),
    )
    net = outcome.total - reversed_points
    delta = apply_xp(progress, xp=net, at=now, tz_name=current_user.timezone)

    exercise = db.get(Exercise, entry.exercise_id)
    response = _set_response(
        db, session=session, entry=entry, exercise=exercise, outcome=outcome,  # type: ignore[arg-type]
        points=net, delta=delta,
    )
    db.commit()
    return response


@router.delete("/sessions/{session_id}/sets/{set_id}", response_model=SetDeleteResponse)
def delete_set(
    session_id: uuid.UUID, set_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> SetDeleteResponse:
    """Remove a set from a live workout. Its awards are reversed and the
    exercise's records rebuilt without it."""
    progress = lock_progress(db, current_user.id)
    session = _get_owned_session(db, session_id, current_user)
    _require_live(session)
    entry = _get_set(db, session, set_id)

    ledger = store.session_ledger(db, session.id)
    reversed_points = store.reverse(
        db,
        user_id=current_user.id,
        session_id=session.id,
        entries=ledger.active_for_set(entry.id),
        reason="Set deleted",
    )
    exercise_id, number = entry.exercise_id, entry.set_number
    db.delete(entry)
    db.flush()
    # Close the gap so the UI never shows "set 1, set 3".
    db.execute(
        update(SetEntry)
        .where(
            SetEntry.session_id == session.id,
            SetEntry.exercise_id == exercise_id,
            SetEntry.set_number > number,
        )
        .values(set_number=SetEntry.set_number - 1)
    )
    store.replay_exercise(db, current_user.id, exercise_id)

    delta = apply_xp(progress, xp=-reversed_points, at=_now(), tz_name=current_user.timezone)
    session_points = store.session_ledger(db, session.id).total
    db.commit()
    return SetDeleteResponse(
        points_awarded=-reversed_points,
        session_points=session_points,
        progression=_delta_out(delta),
    )


@router.post("/sessions/{session_id}/finish", response_model=FinishResponse)
def finish_session(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> FinishResponse:
    """Finish a workout: judge session-volume records, pay the session and
    streak bonuses, and credit the session's points to the wallet."""
    progress = lock_progress(db, current_user.id)
    session = _get_owned_session(db, session_id, current_user)
    _require_live(session)

    now = _now()
    tz = current_user.timezone
    minutes = (now - session.started_at).total_seconds() / 60
    sets = list(
        db.scalars(
            select(SetEntry).where(SetEntry.session_id == session.id).order_by(SetEntry.completed_at)
        )
    )
    working = _working(sets)
    qualified = pe.session_qualifies(minutes, len(working))
    week = streaks.week_key(now, tz)

    session.status = SessionStatus.COMPLETED.value
    session.ended_at = now
    session.qualified = qualified
    session.week_key = week
    db.flush()

    by_exercise: dict[uuid.UUID, list[SetEntry]] = defaultdict(list)
    for entry in sets:
        by_exercise[entry.exercise_id].append(entry)
    for exercise_id, exercise_sets in by_exercise.items():
        event = prs.detect_volume(
            store.load_bests(db, current_user.id, exercise_id), _volume(exercise_sets)
        )
        if event is not None:
            store.add_records(
                db,
                user_id=current_user.id,
                exercise_id=exercise_id,
                session_id=session.id,
                set_id=None,
                events=[event],
                at=now,
            )

    state = streaks.weekly_streak(store.qualified_weeks(db, current_user.id), week)
    awards = pe.award_for_completion(
        pe.CompletionContext(
            duration_minutes=minutes,
            working_sets=len(working),
            week_sessions=state.this_week_sessions,
            streak_weeks=state.weeks,
            streak_bonus_paid_this_week=store.streak_paid(db, current_user.id, week),
        )
    )
    for award in awards:
        store.add_award(
            db,
            user_id=current_user.id,
            session_id=session.id,
            award=award,
            source_id=session.id,
            period_key=week if award.source_type is LedgerSource.STREAK_BONUS else None,
        )

    ledger = store.session_ledger(db, session.id)
    credit = max(0, ledger.total)
    session.points_credited = credit
    completion_xp = sum(a.points for a in awards)

    if qualified:
        # A real workout also advances the global daily streak that gates the
        # A and S ranks - exactly as completing a quest does.
        delta = apply_completion(
            progress, xp=completion_xp, points=credit, completed_at=now, tz_name=tz
        )
    else:
        progress.points_balance += credit
        delta = dataclasses.replace(
            apply_xp(progress, xp=completion_xp, at=now, tz_name=tz), points_awarded=credit
        )

    # A real workout hits the boss of every party the user is in.
    raid_hits = (
        raids.hit_parties(
            db, user_id=current_user.id, session_id=session.id, volume=_volume(working), now=now
        )
        if qualified
        else []
    )

    records = list(
        db.scalars(
            select(PersonalRecord)
            .where(PersonalRecord.session_id == session.id)
            .order_by(PersonalRecord.achieved_at)
        )
    )
    names = {
        e.id: e.name
        for e in db.scalars(select(Exercise).where(Exercise.id.in_(list(by_exercise))))
    } if by_exercise else {}
    summary = _summaries(db, [session])[0]
    breakdown = PointsBreakdownOut(
        set_points=ledger.gross(LedgerSource.SET_LOGGED),
        pr_bonus=ledger.gross(LedgerSource.PR_ACHIEVED),
        session_bonus=ledger.gross(LedgerSource.SESSION_COMPLETED),
        streak_bonus=ledger.gross(LedgerSource.STREAK_BONUS),
        reversals=ledger.gross(LedgerSource.REVERSAL),
        total=ledger.total,
    )
    response = FinishResponse(
        session=summary,
        qualified=qualified,
        awards=[
            AwardOut(source_type=a.source_type.value, points=a.points, reason=a.reason)
            for a in awards
        ],
        breakdown=breakdown,
        points_credited=credit,
        pr_events=_pr_events_out(records, names, ledger.pr_bonus_set_ids()),
        streak=_streak_out(state),
        progression=_delta_out(delta),
        raids=raid_hits,
    )
    db.commit()
    return response


@router.post("/sessions/{session_id}/abandon", response_model=AbandonResponse)
def abandon_session(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> AbandonResponse:
    """Discard a live workout. Every award it earned is reversed and its sets
    stop counting toward records - otherwise log-then-abandon would be a way to
    bank XP without ever finishing a workout."""
    progress = lock_progress(db, current_user.id)
    session = _get_owned_session(db, session_id, current_user)
    _require_live(session)

    ledger = store.session_ledger(db, session.id)
    reversed_points = store.reverse(
        db,
        user_id=current_user.id,
        session_id=session.id,
        entries=ledger.active(),
        reason="Workout abandoned",
    )
    now = _now()
    session.status = SessionStatus.ABANDONED.value
    session.ended_at = now
    db.flush()

    exercise_ids = set(
        db.scalars(select(SetEntry.exercise_id).where(SetEntry.session_id == session.id))
    )
    for exercise_id in exercise_ids:
        store.replay_exercise(db, current_user.id, exercise_id)

    delta = apply_xp(progress, xp=-reversed_points, at=now, tz_name=current_user.timezone)
    summary = _summaries(db, [session])[0]
    db.commit()
    return AbandonResponse(
        session=summary, points_reversed=reversed_points, progression=_delta_out(delta)
    )


# ---------------------------------------------------------------------------
# Records and points
# ---------------------------------------------------------------------------

_RECORD_ORDER = [t.value for t in RecordType]


@router.get("/records", response_model=list[RecordOut])
def list_records(
    current_user: CurrentUser,
    db: DbSession,
    exercise_id: uuid.UUID | None = Query(default=None),
) -> list[RecordOut]:
    """Current personal records. One row per record type per exercise, except
    rep records, which return every undominated (weight, reps) point - "best
    reps at each weight" is a list, not a single number."""
    query = (
        select(PersonalRecord, Exercise.name)
        .join(Exercise, Exercise.id == PersonalRecord.exercise_id)
        .where(PersonalRecord.user_id == current_user.id)
        .order_by(PersonalRecord.achieved_at, PersonalRecord.id)
    )
    if exercise_id is not None:
        query = query.where(PersonalRecord.exercise_id == exercise_id)

    best: dict[tuple[uuid.UUID, str], tuple[PersonalRecord, str]] = {}
    rep_rows: dict[uuid.UUID, list[tuple[PersonalRecord, str]]] = defaultdict(list)
    for row, name in db.execute(query):
        if row.record_type == RecordType.MAX_REPS_AT_WEIGHT.value:
            rep_rows[row.exercise_id].append((row, name))
            continue
        key = (row.exercise_id, row.record_type)
        # Strictly greater, walking in time order: a tie keeps the FIRST time
        # the record was reached.
        if key not in best or row.value > best[key][0].value:
            best[key] = (row, name)

    chosen = list(best.values())
    for rows in rep_rows.values():
        frontier = set(
            prs.bests_from_records(
                (r.record_type, r.value, r.weight_kg) for r, _ in rows
            ).frontier
        )
        seen: set[tuple[Decimal, int]] = set()
        for row, name in rows:
            point = (row.weight_kg, int(row.value))
            if point in frontier and point not in seen:
                seen.add(point)  # type: ignore[arg-type]
                chosen.append((row, name))

    chosen.sort(
        key=lambda item: (
            item[1].casefold(),
            _RECORD_ORDER.index(item[0].record_type),
            -(item[0].weight_kg or 0),
        )
    )
    return [
        RecordOut(
            exercise_id=row.exercise_id,
            exercise_name=name,
            record_type=row.record_type,
            value=row.value,
            weight_kg=row.weight_kg,
            achieved_at=row.achieved_at,
            session_id=row.session_id,
            set_id=row.set_id,
        )
        for row, name in chosen
    ]


@router.get("/points", response_model=PointsSummaryOut)
def points_summary(current_user: CurrentUser, db: DbSession) -> PointsSummaryOut:
    """Workout points totals and the weekly streak."""
    local = local_now(current_user.timezone)
    monday = local.date() - dt.timedelta(days=local.weekday())
    week_start = dt.datetime.combine(
        monday, dt.time.min, tzinfo=resolve_timezone(current_user.timezone)
    )

    def _sum(*conditions) -> int:
        return int(
            db.execute(
                select(func.coalesce(func.sum(PointsLedgerEntry.points), 0)).where(
                    PointsLedgerEntry.user_id == current_user.id, *conditions
                )
            ).scalar_one()
        )

    completed = db.execute(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.status == SessionStatus.COMPLETED.value,
        )
    ).scalar_one()

    return PointsSummaryOut(
        total_points=_sum(),
        this_week_points=_sum(PointsLedgerEntry.created_at >= week_start),
        sessions_completed=int(completed),
        streak=_streak_out(_current_streak(db, current_user)),
    )


@router.get("/points/ledger", response_model=list[LedgerEntryOut])
def list_ledger(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    before: dt.datetime | None = Query(
        default=None, description="Cursor: only entries created before this instant."
    ),
) -> list[LedgerEntryOut]:
    """The points ledger, newest first. Reversals appear as their own negative
    rows - nothing is ever edited or removed."""
    query = select(PointsLedgerEntry).where(PointsLedgerEntry.user_id == current_user.id)
    if before is not None:
        query = query.where(PointsLedgerEntry.created_at < before)
    rows = db.scalars(
        query.order_by(PointsLedgerEntry.created_at.desc(), PointsLedgerEntry.id).limit(limit)
    )
    return [LedgerEntryOut.model_validate(r) for r in rows]
