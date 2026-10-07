"""The clarity screens' numbers (overhaul phase 2): the weekly snapshot, the
You tab's chart, muscle map and calendar, recovery, history, the user's
exercises and one exercise's stats.

Routes only LOAD facts - completed sessions' snapshotted totals, working sets,
ledger rows - and convert instants to the user's local dates; every figure is
computed by app/core/analytics.py or app/core/recovery.py. History reads the
totals written at finish, never the raw sets.
"""

from __future__ import annotations

import base64
import datetime as dt
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import analytics, recovery, social
from app.core import personal_records as prs
from app.core import taxonomy
from app.core import workout_store as store
from app.core.periods import local_date, local_now, resolve_timezone
from app.models.user import User
from app.models.workout import (
    Exercise,
    PersonalRecord,
    PointsLedgerEntry,
    SessionExercise,
    SetEntry,
    WorkoutSession,
)
from app.models.workout_enums import RecordType, SessionStatus
from app.models.duel import ActivityEvent, ActivityType, Duel
from app.models.quest import QuestCompletion
from app.models.quest_board import QuestAssignment
from app.schemas.analytics import (
    MonthlyHeroOut,
    MonthlyRecordOut,
    MonthlySummaryOut,
    CalendarDayOut,
    CalendarOut,
    CalendarRunOut,
    ExerciseStatsOut,
    HistoryMonthOut,
    HistoryPage,
    HistoryRowOut,
    MuscleRecoveryOut,
    MusclesOut,
    MuscleVolumeOut,
    MyExerciseOut,
    MyExercisesPage,
    RecoveryOut,
    SeriesOut,
    SeriesPoint,
    SnapshotOut,
    StatsPoint,
    StatsRecord,
    StatsSession,
    StatsSet,
)

router = APIRouter(tags=["analytics"])

RANGES = "^(3M|6M|Year|All)$"
RECOVERY_NOTE = "An estimate from your recent training volume, not a medical measurement."
UNITS = {"duration": "seconds", "volume": "kg", "workouts": "workouts", "points": "points"}


# ---------------------------------------------------------------------------
# Loading facts
# ---------------------------------------------------------------------------


def _today(user: User) -> dt.date:
    return local_now(user.timezone).date()


def _instant(day: dt.date, tz_name: str) -> dt.datetime:
    """Local midnight starting `day`, as an aware instant."""
    return dt.datetime.combine(day, dt.time(), tzinfo=resolve_timezone(tz_name))


def _completed(user: User):
    return and_(WorkoutSession.user_id == user.id,
                WorkoutSession.status == SessionStatus.COMPLETED.value)


def _facts(db: Session, user: User, since: dt.date | None = None) -> list[analytics.SessionFact]:
    query = select(WorkoutSession).where(_completed(user))
    if since is not None:
        # A day early: the local date of an instant can be a day off UTC's.
        query = query.where(WorkoutSession.started_at >= _instant(since - dt.timedelta(days=1), user.timezone))
    out = []
    for s in db.scalars(query):
        duration = s.duration_seconds
        if duration is None:
            duration = int((s.ended_at - s.started_at).total_seconds()) if s.ended_at else 0
        out.append(analytics.SessionFact(
            day=local_date(s.started_at, user.timezone), duration_seconds=max(0, duration),
            volume_kg=s.total_volume_kg or Decimal(0), working_sets=s.total_working_sets or 0,
            prs=s.total_prs or 0,
        ))
    return out


def _first_day(db: Session, user: User) -> dt.date | None:
    first = db.scalar(select(func.min(WorkoutSession.started_at)).where(_completed(user)))
    return local_date(first, user.timezone) if first else None


def _points_by_day(db: Session, user: User, since: dt.date) -> dict[dt.date, int]:
    rows = db.execute(
        select(PointsLedgerEntry.created_at, PointsLedgerEntry.points).where(
            PointsLedgerEntry.user_id == user.id,
            PointsLedgerEntry.created_at >= _instant(since - dt.timedelta(days=1), user.timezone)))
    out: dict[dt.date, int] = defaultdict(int)
    for at, points in rows:
        out[local_date(at, user.timezone)] += points
    return dict(out)


def _working_sets(db: Session, user: User, start: dt.datetime, end: dt.datetime):
    """(completed_at, primary, secondary) for working sets of completed
    sessions in [start, end)."""
    return db.execute(
        select(SetEntry.completed_at, Exercise.primary_muscle_groups, Exercise.secondary_muscle_groups)
        .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
        .join(Exercise, Exercise.id == SetEntry.exercise_id)
        .where(_completed(user), SetEntry.is_warmup.is_(False),
               SetEntry.completed_at >= start, SetEntry.completed_at < end)
    ).all()


def _parse_day(value: str | None, field: str) -> dt.date | None:
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field}: expected YYYY-MM-DD") from None


# ---------------------------------------------------------------------------
# Snapshot, series, muscles, calendar, recovery
# ---------------------------------------------------------------------------


@router.get("/analytics/snapshot", response_model=SnapshotOut)
def snapshot(current_user: CurrentUser, db: DbSession,
             week: str | None = Query(default=None, description="Any date in the week (YYYY-MM-DD); default this week.")
             ) -> SnapshotOut:
    """Workouts, duration and volume for a week, with the change since the
    week before."""
    monday = analytics.monday(_parse_day(week, "week") or _today(current_user))
    snap = analytics.snapshot(_facts(db, current_user, monday - dt.timedelta(days=7)), monday)
    return SnapshotOut(week_start=snap.week, workouts=snap.workouts,
                       duration_seconds=snap.duration_seconds, volume_kg=snap.volume_kg,
                       workouts_delta=snap.workouts_delta, duration_delta=snap.duration_delta,
                       volume_delta=snap.volume_delta)


@router.get("/analytics/series", response_model=SeriesOut)
def series(current_user: CurrentUser, db: DbSession,
           metric: str = Query(default="volume", pattern="^(duration|volume|workouts|points)$"),
           range_: str = Query(default="3M", alias="range", pattern=RANGES)) -> SeriesOut:
    """One value per week over the range, oldest first, empty weeks as 0."""
    today = _today(current_user)
    start = analytics.range_start(range_, today, _first_day(db, current_user))
    facts = _facts(db, current_user, start)
    points = _points_by_day(db, current_user, start) if metric == "points" else None
    values = analytics.weekly_series(facts, metric, start, today, points)
    return SeriesOut(metric=metric, range=range_, unit=UNITS[metric],
                     points=[SeriesPoint(week_start=w, value=v) for w, v in values])


@router.get("/analytics/muscles", response_model=MusclesOut)
def muscles(current_user: CurrentUser, db: DbSession,
            from_: str | None = Query(default=None, alias="from"),
            to: str | None = Query(default=None)) -> MusclesOut:
    """Working sets per muscle group between two local dates (inclusive;
    default this week), with a 0-1 intensity for the body map."""
    today = _today(current_user)
    start = _parse_day(from_, "from") or analytics.monday(today)
    end = _parse_day(to, "to") or today
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "to is before from")
    rows = _working_sets(db, current_user, _instant(start, current_user.timezone),
                         _instant(end + dt.timedelta(days=1), current_user.timezone))
    load, intensity = analytics.muscle_sets((p or [], s or []) for _, p, s in rows)
    info = {m.code: m for m in taxonomy.muscles(db)}
    out = [MuscleVolumeOut(code=c, display_name=info[c].display_name if c in info else c, sets=load[c],
                           intensity=intensity[c], svg_path_ids=list(info[c].svg_path_ids) if c in info else [])
           for c in sorted(load, key=lambda c: -load[c])]
    return MusclesOut(from_date=start, to_date=end, muscles=out)


@router.get("/analytics/calendar", response_model=CalendarOut)
def calendar(current_user: CurrentUser, db: DbSession,
             month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$")) -> CalendarOut:
    """Days with a completed workout in a month, and the runs of consecutive
    training days."""
    first = dt.date.fromisoformat(f"{month}-01") if month else _today(current_user).replace(day=1)
    cal = analytics.calendar(_facts(db, current_user, first), first)
    return CalendarOut(
        month=first.strftime("%Y-%m"),
        days=[CalendarDayOut(date=d, workouts=n) for d, n in sorted(cal.days.items())],
        runs=[CalendarRunOut(start=a, end=b, days=(b - a).days + 1) for a, b in cal.runs],
    )


@router.get("/analytics/recovery", response_model=RecoveryOut)
def recovery_view(current_user: CurrentUser, db: DbSession) -> RecoveryOut:
    """Overall and per-muscle recovery, estimated from recent working sets."""
    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=max(analytics.rules.RECOVERY_OVERALL_DAYS,
                                       analytics.rules.RECOVERY_WINDOW_HOURS / 24))
    rows = _working_sets(db, current_user, since, now + dt.timedelta(minutes=1))
    info = {m.code: m for m in taxonomy.muscles(db)}
    result = recovery.recovery(
        (recovery.WorkingSet(at, p or [], s or []) for at, p, s in rows), now,
        {c: m.size_class for c, m in info.items() if m.size_class})
    return RecoveryOut(
        overall=result.overall,
        muscles=[MuscleRecoveryOut(code=c, display_name=info[c].display_name, percent=pct,
                                   svg_path_ids=list(info[c].svg_path_ids))
                 for c, pct in sorted(result.muscles.items(), key=lambda kv: (kv[1], kv[0]))],
        note=RECOVERY_NOTE,
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def _encode(at: dt.datetime, row_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"t:{at.isoformat()}|{row_id}".encode()).decode()


def _decode(cursor: str) -> tuple[dt.datetime, uuid.UUID]:
    try:
        kind, rest = base64.urlsafe_b64decode(cursor.encode()).decode().split(":", 1)
        at, row_id = rest.rsplit("|", 1)
        if kind != "t":
            raise ValueError
        return dt.datetime.fromisoformat(at), uuid.UUID(row_id)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Bad cursor") from None


@router.get("/history", response_model=HistoryPage)
def history(current_user: CurrentUser, db: DbSession, cursor: str | None = Query(default=None),
            limit: int = Query(default=20, ge=1, le=100)) -> HistoryPage:
    """Completed workouts, newest first, grouped by the local month they were
    done in. Totals are the ones written at finish."""
    query = select(WorkoutSession).where(_completed(current_user))
    if cursor:
        at, row_id = _decode(cursor)
        query = query.where(or_(WorkoutSession.started_at < at,
                                and_(WorkoutSession.started_at == at, WorkoutSession.id < row_id)))
    rows = list(db.scalars(query.order_by(WorkoutSession.started_at.desc(), WorkoutSession.id.desc())
                           .limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    counts = dict(db.execute(
        select(SessionExercise.session_id, func.count(SessionExercise.id))
        .where(SessionExercise.session_id.in_([r.id for r in rows]))
        .group_by(SessionExercise.session_id)).tuples().all()) if rows else {}
    months: list[HistoryMonthOut] = []
    for s in rows:
        key = local_date(s.started_at, current_user.timezone).strftime("%Y-%m")
        if not months or months[-1].month != key:
            months.append(HistoryMonthOut(month=key, sessions=[]))
        duration = s.duration_seconds if s.duration_seconds is not None else (
            int((s.ended_at - s.started_at).total_seconds()) if s.ended_at else 0)
        months[-1].sessions.append(HistoryRowOut(
            id=s.id, name=s.name, started_at=s.started_at, duration_seconds=max(0, duration),
            volume_kg=float(s.total_volume_kg or 0), working_sets=s.total_working_sets or 0,
            exercise_count=counts.get(s.id, 0), pr_count=s.total_prs or 0, points=s.points_credited,
        ))
    return HistoryPage(months=months,
                       next_cursor=_encode(rows[-1].started_at, rows[-1].id) if more else None)


# ---------------------------------------------------------------------------
# The user's exercises, and one exercise's stats
# ---------------------------------------------------------------------------


@router.get("/me/exercises", response_model=MyExercisesPage)
def my_exercises(current_user: CurrentUser, db: DbSession, cursor: str | None = Query(default=None),
                 limit: int = Query(default=30, ge=1, le=100)) -> MyExercisesPage:
    """Every exercise the user has logged in a completed workout, most
    recently done first, with the best set and estimated 1RM on record."""
    last = (
        select(SetEntry.exercise_id, func.max(SetEntry.completed_at).label("last"),
               func.count(func.distinct(SetEntry.session_id)).label("sessions"))
        .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
        .where(_completed(current_user))
        .group_by(SetEntry.exercise_id).subquery()
    )
    query = select(Exercise, last.c.last, last.c.sessions).join(last, last.c.exercise_id == Exercise.id)
    if cursor:
        at, row_id = _decode(cursor)
        query = query.where(or_(last.c.last < at, and_(last.c.last == at, Exercise.id < row_id)))
    rows = db.execute(query.order_by(last.c.last.desc(), Exercise.id.desc()).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    ids = [e.id for e, _, _ in rows]
    best_weight: dict[uuid.UUID, PersonalRecord] = {}
    best_1rm: dict[uuid.UUID, Decimal] = {}
    if ids:
        for r in db.scalars(select(PersonalRecord).where(
                PersonalRecord.user_id == current_user.id, PersonalRecord.exercise_id.in_(ids),
                PersonalRecord.record_type.in_([RecordType.MAX_WEIGHT.value, RecordType.EST_1RM.value]))):
            if r.record_type == RecordType.MAX_WEIGHT.value:
                if r.exercise_id not in best_weight or r.value > best_weight[r.exercise_id].value:
                    best_weight[r.exercise_id] = r
            elif r.value > best_1rm.get(r.exercise_id, Decimal(-1)):
                best_1rm[r.exercise_id] = r.value
    reps = {}
    set_ids = [r.set_id for r in best_weight.values() if r.set_id]
    if set_ids:
        reps = dict(db.execute(select(SetEntry.id, SetEntry.reps).where(SetEntry.id.in_(set_ids))).tuples().all())
    items = []
    for e, at, sessions in rows:
        bw = best_weight.get(e.id)
        items.append(MyExerciseOut(
            exercise_id=e.id, name=e.name, thumbnail_url=e.thumbnail_url,
            primary_muscle_groups=list(e.primary_muscle_groups or []), equipment=e.equipment,
            last_performed_at=at, sessions=sessions,
            best_weight_kg=float(bw.value) if bw else None,
            best_weight_reps=reps.get(bw.set_id) if bw and bw.set_id else None,
            best_est_1rm=float(best_1rm[e.id]) if e.id in best_1rm else None,
        ))
    return MyExercisesPage(items=items, next_cursor=_encode(rows[-1][1], rows[-1][0].id) if more else None)


@router.get("/exercises/{exercise_id}/stats", response_model=ExerciseStatsOut)
def exercise_stats(exercise_id: uuid.UUID, current_user: CurrentUser, db: DbSession,
                   range_: str = Query(default="All", alias="range", pattern=RANGES)) -> ExerciseStatsOut:
    """Exercise Detail's History, Charts and Records: per completed session
    in the range, the best set, estimated 1RM, volume and max reps; the last
    20 sessions' sets; and the current records."""
    exercise = store.get_visible_exercise(db, exercise_id, current_user.id)
    if exercise is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercise not found")
    today = _today(current_user)
    start = analytics.range_start(range_, today, _first_day(db, current_user))
    rows = db.execute(
        select(SetEntry, WorkoutSession.started_at, WorkoutSession.name)
        .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
        .where(_completed(current_user), SetEntry.exercise_id == exercise.id,
               WorkoutSession.started_at >= _instant(start, current_user.timezone))
        .order_by(WorkoutSession.started_at, SetEntry.set_number)
    ).all()
    by_session: dict[uuid.UUID, list[SetEntry]] = defaultdict(list)
    meta: dict[uuid.UUID, tuple[dt.datetime, str | None]] = {}
    for entry, started, name in rows:
        by_session[entry.session_id].append(entry)
        meta[entry.session_id] = (started, name)

    series = []
    for sid, sets in by_session.items():
        working = [s for s in sets if not s.is_warmup and s.reps]
        if not working:
            continue
        top = max(working, key=lambda s: (s.weight_kg, s.reps))
        e1rms = [e for e in (prs.est_1rm(s.weight_kg, s.reps) for s in working) if e is not None]
        series.append(StatsPoint(
            session_id=sid, date=local_date(meta[sid][0], current_user.timezone),
            best_set_weight_kg=float(top.weight_kg), best_set_reps=top.reps,
            est_1rm=float(max(e1rms)) if e1rms else None,
            volume_kg=float(prs.session_volume(store.lift_of(s) for s in working)),
            max_reps=max(s.reps for s in working),
        ))
    sessions = [
        StatsSession(session_id=sid, name=meta[sid][1], started_at=meta[sid][0],
                     sets=[StatsSet(set_number=s.set_number, set_type=s.set_type,
                                    weight_kg=float(s.weight_kg), reps=s.reps, is_pr=s.is_pr)
                           for s in by_session[sid]])
        for sid in sorted(by_session, key=lambda k: meta[k][0], reverse=True)[:20]
    ]
    best: dict[str, PersonalRecord] = {}
    for r in db.scalars(select(PersonalRecord).where(
            PersonalRecord.user_id == current_user.id, PersonalRecord.exercise_id == exercise.id,
            PersonalRecord.record_type != RecordType.MAX_REPS_AT_WEIGHT.value)
            .order_by(PersonalRecord.achieved_at)):
        if r.record_type not in best or r.value > best[r.record_type].value:
            best[r.record_type] = r
    records = [StatsRecord(record_type=r.record_type, value=float(r.value),
                           weight_kg=float(r.weight_kg) if r.weight_kg is not None else None,
                           achieved_at=r.achieved_at) for r in best.values()]
    return ExerciseStatsOut(exercise_id=exercise.id, range=range_, series=series,
                            sessions=sessions, records=records)


# ---------------------------------------------------------------------------
# Monthly Summary
# ---------------------------------------------------------------------------


def _month_param(month: str | None, user: User) -> dt.date:
    if month:
        return dt.date.fromisoformat(f"{month}-01")
    first = _today(user).replace(day=1)
    return (first - dt.timedelta(days=1)).replace(day=1)       # last month


@router.get("/analytics/monthly-summary", response_model=MonthlySummaryOut)
def monthly_summary(current_user: CurrentUser, db: DbSession,
                    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$",
                                              description="Default: last month.")) -> MonthlySummaryOut:
    """Every slide: workouts and time, volume with a comparison, the muscles,
    the records, points and rank, quests and duels - for one local month."""
    first, nxt = analytics.month_bounds(_month_param(month, current_user))
    tz = current_user.timezone
    start, end = _instant(first, tz), _instant(nxt, tz)
    totals = analytics.month_totals(_facts(db, current_user, first), first)

    rows = _working_sets(db, current_user, start, end)
    load, intensity = analytics.muscle_sets((p or [], s or []) for _, p, s in rows)
    info = {m.code: m for m in taxonomy.muscles(db)}
    muscles = [MuscleVolumeOut(code=c, display_name=info[c].display_name if c in info else c, sets=load[c],
                               intensity=intensity[c], svg_path_ids=list(info[c].svg_path_ids) if c in info else [])
               for c in sorted(load, key=lambda c: (-load[c], c))]

    prs = db.execute(
        select(PersonalRecord, Exercise.name).join(Exercise, Exercise.id == PersonalRecord.exercise_id)
        .where(PersonalRecord.user_id == current_user.id, PersonalRecord.is_baseline.is_(False),
               PersonalRecord.achieved_at >= start, PersonalRecord.achieved_at < end)
        .order_by(PersonalRecord.achieved_at)).all()
    points = db.scalar(select(func.coalesce(func.sum(PointsLedgerEntry.points), 0)).where(
        PointsLedgerEntry.user_id == current_user.id,
        PointsLedgerEntry.created_at >= start, PointsLedgerEntry.created_at < end)) or 0
    rank_ups = list(db.scalars(select(ActivityEvent.headline).where(
        ActivityEvent.user_id == current_user.id, ActivityEvent.party_id.is_(None),
        ActivityEvent.event_type == ActivityType.RANK_UP.value,
        ActivityEvent.created_at >= start, ActivityEvent.created_at < end).order_by(ActivityEvent.created_at)))
    quests = (db.scalar(select(func.count(QuestAssignment.id)).where(
        QuestAssignment.user_id == current_user.id, QuestAssignment.completed_at >= start,
        QuestAssignment.completed_at < end)) or 0) + (db.scalar(select(func.count(QuestCompletion.id)).where(
            QuestCompletion.user_id == current_user.id, QuestCompletion.completed_at >= start,
            QuestCompletion.completed_at < end)) or 0)
    duels = list(db.scalars(select(Duel).where(
        or_(Duel.challenger_id == current_user.id, Duel.opponent_id == current_user.id),
        Duel.resolved_at >= start, Duel.resolved_at < end)))
    rank, level = social.ranks(db, [current_user])[current_user.id]
    return MonthlySummaryOut(
        month=first.strftime("%Y-%m"), workouts=totals.workouts, duration_seconds=totals.duration_seconds,
        active_days=totals.active_days, best_week_workouts=totals.best_week_workouts,
        volume_kg=totals.volume_kg, working_sets=totals.working_sets,
        volume_comparison=analytics.volume_comparison(totals.volume_kg), muscles=muscles,
        records=[MonthlyRecordOut(exercise_name=name, record_type=r.record_type, value=float(r.value),
                                  achieved_at=r.achieved_at) for r, name in prs[-5:]],
        record_count=len(prs), points=int(points), rank=rank, level=level, rank_ups=rank_ups,
        quests_completed=quests, duels_played=len(duels),
        duels_won=sum(1 for d in duels if d.winner_id == current_user.id),
    )


@router.get("/analytics/monthly-summary/latest", response_model=MonthlyHeroOut)
def monthly_hero(current_user: CurrentUser, db: DbSession) -> MonthlyHeroOut:
    """Whether Home shows last month's summary card: in the first days of a
    month, when last month had a workout."""
    today = _today(current_user)
    last = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    totals = analytics.month_totals(_facts(db, current_user, last), last)
    return MonthlyHeroOut(month=last.strftime("%Y-%m"), workouts=totals.workouts,
                          show=today.day <= analytics.rules.MONTHLY_HERO_DAYS and totals.workouts > 0)
