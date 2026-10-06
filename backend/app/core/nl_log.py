"""Natural-language set logging: loading what the parser needs, running the
two tiers, and remembering what happened.

The parsers (nl_parser.py, nl_llm.py) never touch the database. This module
builds their context - the exercises the user can log, their aliases, the
live session's last set - and writes one ParseLog per request. It never
creates a set: that is the log-set endpoint's job, after the user confirms.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import exercise_aliases
from app.core import nl_llm
from app.core import nl_parser as grammar
from app.core import rate_limit
from app.core import workout_store as store
from app.core.exercise_names import name_key
from app.models.nl_log import AliasSource, ExerciseAlias, ParseLog, ParserUsed
from app.models.user import User
from app.models.workout import Exercise, SetEntry, WorkoutSession
from app.models.workout_enums import Equipment, SessionStatus

# A phrase corrected to the same exercise this many times becomes the user's
# own alias for it.
LEARN_AFTER = 2


def context(
    db: Session,
    user: User,
    *,
    session: WorkoutSession | None,
    exercise_id: uuid.UUID | None,
) -> grammar.ParseContext:
    candidates = [
        grammar.Candidate(row.id, row.name, row.equipment == Equipment.BODYWEIGHT.value)
        for row in db.execute(
            select(Exercise.id, Exercise.name, Exercise.equipment).where(
                store.visible_to(user.id), Exercise.is_archived.is_(False)
            )
        )
    ]
    last = None
    if session is not None:
        entry = db.execute(
            select(SetEntry)
            .where(SetEntry.session_id == session.id)
            .order_by(SetEntry.completed_at.desc(), SetEntry.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if entry is not None:
            last = grammar.LastSet(
                entry.exercise_id, Decimal(entry.weight_kg), entry.reps, entry.rpe, entry.is_warmup
            )
    return grammar.ParseContext(
        candidates=candidates,
        aliases=exercise_aliases.for_user(db, user.id),
        # The card the user is on, else whatever they last logged.
        current_exercise_id=exercise_id or (last.exercise_id if last else None),
        last_set=last,
        unit=user.weight_unit,
    )


def live_session(db: Session, user: User, session_id: uuid.UUID | None) -> WorkoutSession | None:
    if session_id is None:
        return None
    return db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.user_id == user.id,
            WorkoutSession.status == SessionStatus.IN_PROGRESS.value,
        )
    ).scalar_one_or_none()


def run(db: Session, user: User, text: str, ctx: grammar.ParseContext) -> tuple[ParseLog, grammar.ParseResult]:
    """Grammar first; Claude only if the grammar found no set. Writes the
    ParseLog and returns it with the result. Does not commit."""
    started = time.perf_counter()
    result = grammar.parse(text, ctx)
    used = ParserUsed.GRAMMAR
    if not result.ok and nl_llm.enabled():
        try:
            rate_limit.enforce(rate_limit.NL_LLM_PER_USER, str(user.id))
        except HTTPException:
            pass  # over budget: the grammar's answer stands
        else:
            fallback = nl_llm.parse(text, ctx)
            if fallback.ok:
                result, used = fallback, ParserUsed.LLM
    if not result.ok:
        used = ParserUsed.NONE
    elapsed = int((time.perf_counter() - started) * 1000)

    log = ParseLog(
        user_id=user.id,
        raw_text=text[:500],
        parser_used=used.value,
        result=serialise(result),
        latency_ms=elapsed,
    )
    db.add(log)
    db.flush()
    return log, result


def serialise(result: grammar.ParseResult) -> dict:
    """The ParseLog copy of a result: enough to compare against a correction."""
    first = result.sets[0] if result.sets else None
    return {
        "exercise_id": str(first.exercise_id) if first and first.exercise_id else None,
        "weight": first.weight if first else None,
        "unit": first.unit if first else None,
        "reps": first.reps if first else None,
        "rpe": first.rpe if first else None,
        "is_warmup": first.is_warmup if first else None,
        "set_count": len(result.sets),
        "phrase": result.phrase,
        "problem": result.problem,
    }


def learn(db: Session, user: User, log: ParseLog) -> bool:
    """After a correction: if this phrase has now been corrected to the same
    exercise LEARN_AFTER times, make it the user's alias. Returns whether one
    was added."""
    corrected = (log.corrected_result or {}).get("exercise_id")
    phrase = name_key((log.result or {}).get("phrase") or "")
    if not corrected or not phrase or corrected == (log.result or {}).get("exercise_id"):
        return False
    try:
        exercise_id = uuid.UUID(str(corrected))
    except ValueError:
        return False
    if store.get_visible_exercise(db, exercise_id, user.id) is None:
        return False
    db.flush()
    times = db.execute(
        select(func.count(ParseLog.id)).where(
            ParseLog.user_id == user.id,
            ParseLog.result["phrase"].astext == phrase,
            ParseLog.corrected_result["exercise_id"].astext == str(exercise_id),
        )
    ).scalar_one()
    if times < LEARN_AFTER:
        return False
    added = db.execute(
        insert(ExerciseAlias)
        .values(
            exercise_id=exercise_id,
            alias=phrase[:60],
            source=AliasSource.LEARNED.value,
            user_id=user.id,
        )
        .on_conflict_do_nothing(constraint="uq_exercise_aliases_alias")
        .returning(ExerciseAlias.id)
    ).first()
    return added is not None
