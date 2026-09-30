"""Splits, the stretches that match them, and a session's Recommended panel.

The matching rule lives in app/core/splits.py and is pure; this module is the
database work around it. Nothing here touches points, XP or records - a
stretch is a suggestion, and suggesting one must never change a score.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import splits as engine
from app.models.split import SplitType, StretchPhase
from app.models.workout import Exercise, RecommendedStretch, WorkoutSession
from app.schemas.split import (
    AddRecommended,
    RecommendedPanel,
    SetSplit,
    SplitOut,
    StretchOut,
)

router = APIRouter(tags=["splits"])


def _owned_session(db: Session, session_id: uuid.UUID, user: CurrentUser) -> WorkoutSession:
    session = db.get(WorkoutSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    return session


def _stretch_rows(db: Session, user_id: uuid.UUID) -> list[Exercise]:
    """Every stretch this user can see: the shared library plus their own."""
    return list(
        db.scalars(
            select(Exercise)
            .where(Exercise.stretch_phase.is_not(None))
            .where((Exercise.is_custom.is_(False)) | (Exercise.created_by_user_id == user_id))
            .order_by(Exercise.name)
        )
    )


@router.get("/splits", response_model=list[SplitOut])
def list_splits(current_user: CurrentUser, db: DbSession) -> list[SplitOut]:
    """What the picker offers. Signed in, because everything else here is."""
    return [SplitOut.model_validate(row) for row in engine.all_profiles(db)]


@router.get("/stretches", response_model=list[StretchOut])
def list_stretches(
    current_user: CurrentUser,
    db: DbSession,
    split_type: SplitType | None = Query(default=None),
    phase: StretchPhase | None = Query(default=None),
) -> list[StretchOut]:
    """The stretches for a split and phase.

    With no split, every stretch - which is what the "add your own" picker
    browses. With one, only those whose muscle groups overlap it.
    """
    rows = _stretch_rows(db, current_user.id)
    if phase is not None:
        rows = [row for row in rows if row.stretch_phase == phase.value]
    if split_type is not None:
        profile = engine.profile(db, split_type.value)
        groups = profile.target_muscle_groups if profile else []
        rows = [row for row in rows if engine.matches(row.primary_muscle_groups, groups)]
    return [StretchOut.model_validate(row) for row in rows]


@router.post("/workouts/sessions/{session_id}/split", response_model=RecommendedPanel)
def set_split(
    session_id: uuid.UUID, payload: SetSplit, current_user: CurrentUser, db: DbSession
) -> RecommendedPanel:
    """Answer the picker, and get the panel back in one call.

    Recording the auto-matched set here rather than making the client do it
    means the panel is reconstructable from the moment it first appeared - and
    a user's own additions, which arrive later, are distinguishable from it.
    """
    session = _owned_session(db, session_id, current_user)
    session.split_type = payload.split_type.value

    profile = engine.profile(db, payload.split_type.value)
    groups = profile.target_muscle_groups if profile else []
    for row in _stretch_rows(db, current_user.id):
        if not engine.matches(row.primary_muscle_groups, groups):
            continue
        db.add(
            RecommendedStretch(
                session_id=session.id,
                exercise_id=row.id,
                source="auto_matched",
                phase=row.stretch_phase,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        # The split was set twice - the UNIQUE means the panel is a set, so
        # there is nothing to add and nothing to complain about.
        db.rollback()
    return _panel(db, session)


@router.post(
    "/workouts/sessions/{session_id}/recommended-stretches",
    response_model=RecommendedPanel,
    status_code=status.HTTP_201_CREATED,
)
def add_recommended(
    session_id: uuid.UUID, payload: AddRecommended, current_user: CurrentUser, db: DbSession
) -> RecommendedPanel:
    """Put something into the panel by hand.

    Flagged `user_added`, which is what keeps it there: re-matching only ever
    writes `auto_matched` rows, so nothing the user chose is taken away.
    """
    session = _owned_session(db, session_id, current_user)
    exercise = db.get(Exercise, payload.exercise_id)
    if exercise is None or (exercise.is_custom and exercise.created_by_user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")

    db.add(
        RecommendedStretch(
            session_id=session.id,
            exercise_id=exercise.id,
            source="user_added",
            phase=payload.phase.value,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # already in the panel; adding twice is a no-op
    return _panel(db, session)


@router.get("/workouts/sessions/{session_id}/recommended-stretches", response_model=RecommendedPanel)
def get_recommended(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> RecommendedPanel:
    """The panel as it stands, so a reload rebuilds it from the server rather
    than from whatever the client happened to remember."""
    return _panel(db, _owned_session(db, session_id, current_user))


def _panel(db: Session, session: WorkoutSession) -> RecommendedPanel:
    rows = db.execute(
        select(RecommendedStretch, Exercise)
        .join(Exercise, Exercise.id == RecommendedStretch.exercise_id)
        .where(RecommendedStretch.session_id == session.id)
        .order_by(RecommendedStretch.source.desc(), Exercise.name)
    ).all()
    panel = RecommendedPanel(split_type=session.split_type)
    for selection, exercise in rows:
        entry = StretchOut.model_validate(exercise)
        entry.source = selection.source
        (panel.pre if selection.phase == "pre" else panel.post).append(entry)
    return panel
