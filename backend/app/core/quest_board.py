"""Generated quests: handing them out, keeping their progress, paying them.

The rules live in quest_engine.py, which never touches a database; this is the
layer that loads its inputs and persists what it decides. Nothing here
commits, and every writer must already hold the level_progress lock
(progression.lock_progress) - the same contract as workout_store.py.

**Generated lazily.** A period's quests are created by the first request that
needs them, chosen deterministically from the user and the period, so a
refresh never reshuffles them and two racing requests choose the same ones
(uq_quest_assignments_once takes the loser's insert).

**Paid through the ledger, like everything else a workout earns.** A
completion writes a `quest_completed` row; finishing all of a week's quests
writes a `quest_bonus` row. Neither passes through points_engine, so neither
touches the per-session set or PR caps.

**When a completion can be taken back.** A completion made while a workout is
live is attached to that workout's ledger, exactly like a set award: XP moves
now, shop points are credited when the workout is finished. Until then the
sets behind it can still be deleted, so if progress drops back below target
the award is reversed and the quest reopens - and abandoning the workout
reverses it along with everything else the workout earned. A completion made
with no workout live counts only finished workouts, whose sets can no longer
change, so it is final and credited straight away.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import activity, social
from app.core import points_engine as pe
from app.core import quest_engine as engine
from app.core import workout_rules as rules
from app.core import workout_store as store
from app.core.periods import local_date, period_key, resolve_timezone
from app.core.personal_records import PrEvent
from app.models.duel import ActivityType
from app.models.quest_board import (
    AssignmentStatus,
    QuestAssignment,
    QuestObjective,
    QuestPeriod,
    QuestReroll,
    QuestTemplate,
)
from app.models.user import User
from app.models.workout import (
    Exercise,
    PersonalRecord,
    PointsLedgerEntry,
    SetEntry,
    WorkoutSession,
)
from app.models.workout_enums import LedgerSource, RecordType, SessionStatus

_COUNTS = {QuestPeriod.DAILY: rules.DAILY_QUESTS, QuestPeriod.WEEKLY: rules.WEEKLY_QUESTS}
_QUEST_SOURCES = (LedgerSource.QUEST_COMPLETED.value, LedgerSource.QUEST_BONUS.value)


class RerollError(Exception):
    """A reroll the rules do not allow. The message is safe to show."""


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Window:
    period: QuestPeriod
    key: str
    start: dt.datetime
    end: dt.datetime


def window(period: QuestPeriod, now: dt.datetime, tz_name: str) -> Window:
    """The period `now` falls in, bounded at the user's local midnights."""
    tz = resolve_timezone(tz_name)
    day = local_date(now, tz_name)
    if period is QuestPeriod.WEEKLY:
        day -= dt.timedelta(days=day.weekday())
        length = dt.timedelta(days=7)
    else:
        length = dt.timedelta(days=1)
    start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    end = dt.datetime.combine(day + length, dt.time.min, tzinfo=tz)
    return Window(period, period_key(period.value, now, tz_name), start, end)


# ---------------------------------------------------------------------------
# Handing quests out
# ---------------------------------------------------------------------------


def _pool(db: Session, period: QuestPeriod, category: str) -> list[engine.Candidate]:
    rows = db.execute(
        select(QuestTemplate.code, QuestTemplate.eligible_categories).where(
            QuestTemplate.period == period.value, QuestTemplate.is_active.is_(True)
        )
    ).all()
    return engine.eligible(
        [engine.Candidate(code, tuple(categories)) for code, categories in rows], category
    )


def _assignment_values(user: User, win: Window, template: QuestTemplate) -> dict:
    return {
        "user_id": user.id,
        "template_code": template.code,
        "period": win.period.value,
        "period_key": win.key,
        "period_start": win.start,
        "period_end": win.end,
        "title": template.title,
        "description": template.description,
        "objective_type": template.objective_type,
        "objective_params": template.objective_params,
        "target_value": template.target_value,
        "reward_points": template.reward_points,
    }


def _current(db: Session, user: User, win: Window) -> list[QuestAssignment]:
    return list(
        db.scalars(
            select(QuestAssignment)
            .where(
                QuestAssignment.user_id == user.id,
                QuestAssignment.period_key == win.key,
                QuestAssignment.period == win.period.value,
                QuestAssignment.status != AssignmentStatus.REROLLED.value,
            )
            .order_by(QuestAssignment.created_at, QuestAssignment.template_code)
        )
    )


def ensure_assignments(
    db: Session, user: User, now: dt.datetime, *, created: set[uuid.UUID] | None = None
) -> list[QuestAssignment]:
    """This period's daily and weekly quests, generating any that are missing.
    The ids of any generated by THIS call are added to `created`."""
    db.flush()
    out: list[QuestAssignment] = []
    for period in (QuestPeriod.DAILY, QuestPeriod.WEEKLY):
        win = window(period, now, user.timezone)
        rows = _current(db, user, win)
        if not rows:
            codes = engine.choose(
                _pool(db, period, user.character_class),
                seed=f"{user.id}:{win.key}",
                count=_COUNTS[period],
            )
            if codes:
                templates = db.scalars(select(QuestTemplate).where(QuestTemplate.code.in_(codes)))
                made = db.execute(
                    insert(QuestAssignment)
                    .values([_assignment_values(user, win, t) for t in templates])
                    .on_conflict_do_nothing()
                    .returning(QuestAssignment.id)
                ).scalars()
                if created is not None:
                    created.update(made)
                rows = _current(db, user, win)
        out.extend(rows)
    return out


def rerolls_used(db: Session, user: User, now: dt.datetime) -> int:
    day = window(QuestPeriod.DAILY, now, user.timezone).key
    return int(
        db.execute(
            select(func.count(QuestReroll.id)).where(
                QuestReroll.user_id == user.id, QuestReroll.day_key == day
            )
        ).scalar_one()
    )


def rerolls_left(db: Session, user: User, now: dt.datetime) -> int:
    return max(0, rules.QUEST_REROLLS_PER_DAY - rerolls_used(db, user, now))


def reroll(
    db: Session, user: User, assignment: QuestAssignment, now: dt.datetime
) -> QuestAssignment:
    """Swap one of today's active daily quests for another. Raises RerollError."""
    win = window(QuestPeriod.DAILY, now, user.timezone)
    if assignment.period != QuestPeriod.DAILY.value:
        raise RerollError("Only daily quests can be rerolled")
    if assignment.period_key != win.key:
        raise RerollError("That quest has expired")
    if assignment.status != AssignmentStatus.ACTIVE.value:
        raise RerollError(f"That quest is already {assignment.status}")
    used = rerolls_used(db, user, now)
    if used >= rules.QUEST_REROLLS_PER_DAY:
        raise RerollError("No rerolls left today")

    # Everything handed out today, rerolled ones included - a reroll must not
    # be able to hand back the quest it just took away.
    taken = set(
        db.scalars(
            select(QuestAssignment.template_code).where(
                QuestAssignment.user_id == user.id, QuestAssignment.period_key == win.key
            )
        )
    )
    codes = engine.choose(
        _pool(db, QuestPeriod.DAILY, user.character_class),
        seed=f"{user.id}:{win.key}:reroll:{used + 1}",
        count=1,
        exclude=taken,
    )
    if not codes:
        raise RerollError("There are no other quests to swap in today")

    assignment.status = AssignmentStatus.REROLLED.value
    db.flush()
    template = db.get(QuestTemplate, codes[0])
    fresh = QuestAssignment(**_assignment_values(user, win, template))  # type: ignore[arg-type]
    db.add(fresh)
    db.flush()
    # uq_quest_rerolls_slot is the real limit; the caller turns a conflict here
    # (two taps racing past the count above) into the same "none left" answer.
    db.add(QuestReroll(user_id=user.id, day_key=win.key, ordinal=used + 1, assignment_id=assignment.id))
    db.flush()
    return fresh


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


def load_facts(
    db: Session, user: User, win: Window, *, with_e1rm: bool
) -> engine.PeriodFacts:
    sets = tuple(
        engine.SetFact(
            session_id=row.session_id,
            exercise_id=row.exercise_id,
            weight_kg=row.weight_kg,
            reps=row.reps,
            is_warmup=row.is_warmup,
            tags=frozenset(row.tags or ()),
        )
        for row in db.execute(
            select(
                SetEntry.session_id,
                SetEntry.exercise_id,
                SetEntry.weight_kg,
                SetEntry.reps,
                SetEntry.is_warmup,
                Exercise.tags,
            )
            .join(WorkoutSession, WorkoutSession.id == SetEntry.session_id)
            .join(Exercise, Exercise.id == SetEntry.exercise_id)
            .where(
                SetEntry.user_id == user.id,
                SetEntry.completed_at >= win.start,
                SetEntry.completed_at < win.end,
                WorkoutSession.status != SessionStatus.ABANDONED.value,
                # Imported history is history, not this week's training.
                WorkoutSession.import_id.is_(None),
            )
        )
    )
    qualified = frozenset(
        db.scalars(
            select(WorkoutSession.id).where(
                WorkoutSession.user_id == user.id,
                WorkoutSession.status == SessionStatus.COMPLETED.value,
                WorkoutSession.qualified.is_(True),
                WorkoutSession.ended_at >= win.start,
                WorkoutSession.ended_at < win.end,
            )
        )
    )
    # Only records the PR bonus would pay for: one more set for more volume,
    # or a hair over an old best, is not "beating yourself" - the same line
    # points_engine.bonus_eligible draws for the bonus itself.
    prs: dict[tuple, engine.PrFact] = {}
    for row in db.execute(
        select(
            PersonalRecord.exercise_id,
            PersonalRecord.set_id,
            PersonalRecord.session_id,
            PersonalRecord.record_type,
            PersonalRecord.value,
            PersonalRecord.weight_kg,
            PersonalRecord.previous_value,
            PersonalRecord.is_baseline,
            Exercise.tags,
        )
        .join(Exercise, Exercise.id == PersonalRecord.exercise_id)
        .join(WorkoutSession, WorkoutSession.id == PersonalRecord.session_id)
        .where(
            PersonalRecord.user_id == user.id,
            WorkoutSession.import_id.is_(None),
            PersonalRecord.is_baseline.is_(False),
            PersonalRecord.achieved_at >= win.start,
            PersonalRecord.achieved_at < win.end,
        )
    ):
        event = PrEvent(
            RecordType(row.record_type), row.value, row.weight_kg, row.previous_value,
            row.is_baseline,
        )
        if not pe.bonus_eligible(event):
            continue
        # One set beating three record types is one PR, not three.
        key = (row.set_id,) if row.set_id else (row.session_id, row.exercise_id)
        prs[key] = engine.PrFact(row.exercise_id, frozenset(row.tags or ()))

    e1rm: dict[uuid.UUID, object] = {}
    if with_e1rm:
        e1rm = {
            exercise_id: best
            for exercise_id, best in db.execute(
                select(PersonalRecord.exercise_id, func.max(PersonalRecord.value))
                .where(
                    PersonalRecord.user_id == user.id,
                    PersonalRecord.record_type == RecordType.EST_1RM.value,
                    PersonalRecord.achieved_at < win.start,
                )
                .group_by(PersonalRecord.exercise_id)
            )
        }
    return engine.PeriodFacts(
        sets=sets, qualified_sessions=qualified, prs=tuple(prs.values()), e1rm_before=e1rm  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Progress and rewards
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class QuestUpdate:
    assignment: QuestAssignment
    before: int
    after: int
    completed_now: bool

    @property
    def advanced(self) -> bool:
        return self.after > self.before


@dataclasses.dataclass(frozen=True)
class Refresh:
    updates: tuple[QuestUpdate, ...]
    # Net XP the caller must apply: rewards made minus rewards reversed.
    xp: int
    # Shop points the caller must credit now - rewards with no live workout to
    # be credited through (see the module docstring).
    points_now: int

    @property
    def completed(self) -> list[QuestAssignment]:
        return [u.assignment for u in self.updates if u.completed_now]


def _active_session_id(db: Session, user: User) -> uuid.UUID | None:
    return db.execute(
        select(WorkoutSession.id).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == SessionStatus.IN_PROGRESS.value,
        )
    ).scalar_one_or_none()


def _standing(db: Session, user: User, ids: list[uuid.UUID]) -> list[PointsLedgerEntry]:
    """Quest ledger rows for these assignments that have not been reversed."""
    if not ids:
        return []
    rows = list(
        db.scalars(
            select(PointsLedgerEntry).where(
                PointsLedgerEntry.user_id == user.id,
                PointsLedgerEntry.source_type.in_(_QUEST_SOURCES),
                PointsLedgerEntry.source_id.in_(ids),
            )
        )
    )
    if not rows:
        return []
    reversed_ids = set(
        db.scalars(
            select(PointsLedgerEntry.source_id).where(
                PointsLedgerEntry.source_type == LedgerSource.REVERSAL.value,
                PointsLedgerEntry.source_id.in_([r.id for r in rows]),
            )
        )
    )
    return [r for r in rows if r.id not in reversed_ids]


def refresh(
    db: Session,
    user: User,
    now: dt.datetime,
    *,
    session: WorkoutSession | None = None,
) -> Refresh:
    """Recompute every current quest's progress, completing and reopening as
    the sets now say. `session` is the workout a new award is attached to;
    without one, the user's live workout is used if there is one.

    Idempotent: re-running it with nothing changed writes nothing, because a
    quest is only completed from `active` and only reopened from `completed`.
    """
    fresh: set[uuid.UUID] = set()
    assignments = ensure_assignments(db, user, now, created=fresh)
    if not assignments:
        return Refresh((), 0, 0)
    db.flush()

    live_id = _active_session_id(db, user)
    attach_id = session.id if session is not None else live_id

    facts: dict[str, engine.PeriodFacts] = {}
    for period in (QuestPeriod.DAILY, QuestPeriod.WEEKLY):
        mine = [a for a in assignments if a.period == period.value]
        if mine:
            facts[period.value] = load_facts(
                db,
                user,
                window(period, now, user.timezone),
                with_e1rm=any(
                    a.objective_type == QuestObjective.INTENSITY_SETS.value for a in mine
                ),
            )

    standing = _standing(db, user, [a.id for a in assignments])
    awards: dict[uuid.UUID, list[PointsLedgerEntry]] = defaultdict(list)
    bonuses: list[PointsLedgerEntry] = []
    for row in standing:
        (bonuses if row.source_type == LedgerSource.QUEST_BONUS.value else awards[row.source_id]).append(row)

    xp = 0
    points_now = 0

    def pay(source: LedgerSource, points: int, source_id: uuid.UUID, reason: str) -> None:
        nonlocal xp, points_now
        db.add(
            PointsLedgerEntry(
                user_id=user.id,
                source_type=source.value,
                source_id=source_id,
                points=points,
                session_id=attach_id,
                reason=reason[:120],
            )
        )
        xp += points
        if attach_id is None:
            points_now += points

    def take_back(rows: list[PointsLedgerEntry], reason: str) -> None:
        nonlocal xp
        for row in rows:
            xp -= store.reverse(
                db, user_id=user.id, session_id=row.session_id, entries=[row], reason=reason  # type: ignore[arg-type]
            )

    updates: list[QuestUpdate] = []
    for a in assignments:
        raw = engine.progress(
            QuestObjective(a.objective_type), a.objective_params, facts[a.period]
        )
        # A quest handed out by this very call has no "before": progress it
        # already had from earlier workouts was not made by this action.
        before = min(raw, a.target_value) if a.id in fresh else a.progress_value
        a.progress_value = min(raw, a.target_value)
        completed_now = False

        if a.status == AssignmentStatus.COMPLETED.value:
            rows = awards.get(a.id, [])
            if not rows:
                # Its award was reversed from outside - the workout it was
                # attached to was abandoned. Reopen; it may complete again
                # below from what is left.
                a.status, a.completed_at = AssignmentStatus.ACTIVE.value, None
            elif raw < a.target_value and live_id is not None and any(
                r.session_id == live_id for r in rows
            ):
                take_back(rows, "Quest progress lost")
                a.status, a.completed_at = AssignmentStatus.ACTIVE.value, None

        if a.status == AssignmentStatus.ACTIVE.value and raw >= a.target_value:
            a.status, a.completed_at = AssignmentStatus.COMPLETED.value, now
            pay(LedgerSource.QUEST_COMPLETED, a.reward_points, a.id, f"Quest: {a.title}")
            completed_now = True

        updates.append(QuestUpdate(a, before, a.progress_value, completed_now))

    weekly = [a for a in assignments if a.period == QuestPeriod.WEEKLY.value]
    all_done = len(weekly) >= rules.WEEKLY_QUESTS and all(
        a.status == AssignmentStatus.COMPLETED.value for a in weekly
    )
    if all_done and not bonuses:
        last = max(weekly, key=lambda a: a.completed_at)  # type: ignore[arg-type,return-value]
        pay(LedgerSource.QUEST_BONUS, rules.ALL_WEEKLY_QUESTS_BONUS, last.id, "All weekly quests done")
    elif not all_done and bonuses:
        take_back([b for b in bonuses if live_id is not None and b.session_id == live_id], "Weekly quests reopened")

    db.flush()
    for update in updates:
        if update.completed_now:
            activity.record(
                db,
                user_id=user.id,
                event_type=ActivityType.QUEST_COMPLETED,
                headline=f"Completed {update.assignment.title}",
                source_id=update.assignment.id,
                at=now,
            )
            social.notify(db, user.id, "quest_complete", target_type="quest",
                          target_id=update.assignment.id, detail=update.assignment.title, now=now)
    return Refresh(tuple(updates), xp, points_now)

