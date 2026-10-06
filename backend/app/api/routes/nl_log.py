"""Natural-language set logging: parse, feedback, and exercise aliases.

POST /log/parse proposes sets and NEVER logs them. The client shows the
proposal, the user confirms with one tap, and each set goes through POST
/workouts/sessions/{id}/sets like a tapped-in one - so points, records and
quests are judged exactly as for any other set. The only write here is the
ParseLog row (text only; audio never reaches the server).

Mounted BEFORE routes/exercises.py: `/exercises/aliases` must not be parsed
as `/exercises/{exercise_id}`.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core import nl_log
from app.core import workout_store as store
from app.core.exercise_names import name_key
from app.models.nl_log import AliasSource, ExerciseAlias, ParseLog
from app.models.workout import Exercise
from app.schemas.nl_log import (
    AliasCreate,
    AliasOut,
    AlternativeOut,
    ParseFeedback,
    ParseFeedbackResponse,
    ParseRequest,
    ParseResponse,
    ProposedSetOut,
)

router = APIRouter(tags=["natural-language logging"])


@router.post("/log/parse", response_model=ParseResponse)
def parse_text(payload: ParseRequest, current_user: CurrentUser, db: DbSession) -> ParseResponse:
    """Turn "bench 80 for 8" into proposed sets. Side-effect free apart from
    the parse log. `problem` is set, and `proposed_sets` empty, when nothing
    could be understood - a normal answer, not an error."""
    session = nl_log.live_session(db, current_user, payload.session_id)
    if payload.session_id is not None and session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    ctx = nl_log.context(db, current_user, session=session, exercise_id=payload.exercise_id)
    log, result = nl_log.run(db, current_user, payload.text.strip(), ctx)

    names = {c.id: c.name for c in ctx.candidates}
    response = ParseResponse(
        parse_id=log.id,
        parser_used=log.parser_used,
        proposed_sets=[
            ProposedSetOut(
                exercise_id=s.exercise_id,  # type: ignore[arg-type]
                exercise_name=names.get(s.exercise_id, ""),  # type: ignore[arg-type]
                weight=s.weight,
                unit=s.unit,
                reps=s.reps,
                rpe=s.rpe,
                is_warmup=s.is_warmup,
            )
            for s in result.sets
        ],
        set_count=len(result.sets),
        exercise_confidence=result.exercise_confidence,
        exercise_alternatives=[
            AlternativeOut(exercise_id=a.exercise_id, name=a.name, confidence=a.confidence)
            for a in result.alternatives
        ],
        unparsed_fragments=list(result.unparsed),
        problem=result.problem or None,
    )
    db.commit()
    return response


@router.post("/log/parse/{parse_id}/feedback", response_model=ParseFeedbackResponse)
def parse_feedback(
    parse_id: uuid.UUID, payload: ParseFeedback, current_user: CurrentUser, db: DbSession
) -> ParseFeedbackResponse:
    """Whether the proposal was logged as-is or edited first. Edits teach:
    a phrase corrected to the same exercise twice becomes the user's alias."""
    log = db.execute(
        select(ParseLog).where(ParseLog.id == parse_id, ParseLog.user_id == current_user.id)
    ).scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parse not found")
    if log.accepted is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feedback already recorded")
    log.accepted = payload.accepted
    if payload.corrected_result is not None:
        log.corrected_result = payload.corrected_result.model_dump(mode="json")
    learned = nl_log.learn(db, current_user, log)
    db.commit()
    return ParseFeedbackResponse(alias_learned=learned)


def _alias_out(row: ExerciseAlias, name: str) -> AliasOut:
    return AliasOut(
        id=row.id, alias=row.alias, exercise_id=row.exercise_id, exercise_name=name, source=row.source
    )


@router.get("/exercises/aliases", response_model=list[AliasOut])
def list_aliases(current_user: CurrentUser, db: DbSession) -> list[AliasOut]:
    """Every alias the parser will use for this user: the shipped ones and
    their own (which win on a clash)."""
    rows = db.execute(
        select(ExerciseAlias, Exercise.name)
        .join(Exercise, Exercise.id == ExerciseAlias.exercise_id)
        .where(
            or_(ExerciseAlias.user_id.is_(None), ExerciseAlias.user_id == current_user.id),
            store.visible_to(current_user.id),
        )
        .order_by(ExerciseAlias.alias, ExerciseAlias.source)
    ).all()
    return [_alias_out(row, name) for row, name in rows]


@router.post("/exercises/aliases", response_model=AliasOut, status_code=status.HTTP_201_CREATED)
def create_alias(payload: AliasCreate, current_user: CurrentUser, db: DbSession) -> AliasOut:
    """A personal alias: "flat bb" means Barbell Bench Press, for this user."""
    exercise = store.get_visible_exercise(db, payload.exercise_id, current_user.id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    alias = name_key(payload.alias)
    row = ExerciseAlias(
        exercise_id=exercise.id, alias=alias, source=AliasSource.USER.value, user_id=current_user.id
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f'You already use "{alias}" for an exercise'
        ) from None
    out = _alias_out(row, exercise.name)
    db.commit()
    return out
