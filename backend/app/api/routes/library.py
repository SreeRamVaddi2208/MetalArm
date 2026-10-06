"""The Library tab's API: programs, favourites, one listing for programs /
routines / exercises, and which routine to do next.

Mounted before routes/workouts.py, so /workouts/suggested is never read as a
workouts path parameter.
"""

from __future__ import annotations

import base64
import datetime as dt
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.api.routes.routines import last_performed
from app.core import presets, suggestions
from app.core import workout_store as store
from app.models.program import Favorite, Program
from app.models.user import User
from app.models.workout import Exercise, Routine, RoutineExercise, SetEntry, WorkoutSession
from app.models.workout_enums import SessionStatus
from app.schemas.library import (
    FavoriteIn,
    LibraryItem,
    LibraryPage,
    ProgramIn,
    ProgramOut,
    ProgramRoutineOut,
    SuggestedOut,
)

router = APIRouter(tags=["library"])


# ---------------------------------------------------------------------------
# Cursors: opaque to the client, an offset underneath. Good enough for lists
# of a user's own programs and routines, which are short and stable.
# ---------------------------------------------------------------------------


def _cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"o:{offset}".encode()).decode()


def _offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        kind, value = base64.urlsafe_b64decode(cursor.encode()).decode().split(":", 1)
        if kind != "o":
            raise ValueError
        return max(0, int(value))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Bad cursor") from None


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


def _favorites(db: Session, user: User, target_type: str) -> set[uuid.UUID]:
    return set(db.scalars(select(Favorite.target_id).where(
        Favorite.user_id == user.id, Favorite.target_type == target_type)))


def _program_out(db: Session, user: User, program: Program) -> ProgramOut:
    routines = list(db.scalars(
        select(Routine).where(Routine.program_id == program.id)
        .order_by(Routine.order_in_program.nulls_last(), Routine.created_at)))
    counts = dict(db.execute(
        select(RoutineExercise.routine_id, func.count(RoutineExercise.id))
        .where(RoutineExercise.routine_id.in_([r.id for r in routines]))
        .group_by(RoutineExercise.routine_id)).tuples().all()) if routines else {}
    last = last_performed(db, [r.id for r in routines])
    return ProgramOut(
        id=program.id, name=program.name, description=program.description,
        training_category=program.training_category, level=program.level, weeks=program.weeks,
        sessions_per_week=program.sessions_per_week, is_public=program.is_public,
        cover_color=program.cover_color, owner_user_id=program.owner_user_id,
        routines=[ProgramRoutineOut(id=r.id, name=r.name, order_in_program=r.order_in_program,
                                    exercise_count=counts.get(r.id, 0),
                                    last_performed_at=last.get(r.id)) for r in routines],
        favorite=program.id in _favorites(db, user, "program"),
    )


def _readable_program(db: Session, user: User, program_id: uuid.UUID) -> Program:
    program = db.get(Program, program_id)
    if program is None or not (program.owner_user_id in (None, user.id) or program.is_public):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


def _owned_program(db: Session, user: User, program_id: uuid.UUID) -> Program:
    program = db.get(Program, program_id)
    if program is None or program.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


@router.get("/programs", response_model=list[ProgramOut])
def list_programs(current_user: CurrentUser, db: DbSession,
                  mine: bool = Query(default=True, description="False lists curated programs.")
                  ) -> list[ProgramOut]:
    """The caller's programs, or (mine=false) the curated ones - the user's
    training path first."""
    query = select(Program).where(
        Program.owner_user_id == current_user.id if mine else Program.owner_user_id.is_(None))
    rows = list(db.scalars(query.order_by(Program.updated_at.desc())))
    if not mine:
        rows.sort(key=lambda p: p.training_category != current_user.character_class)
    return [_program_out(db, current_user, p) for p in rows]


@router.post("/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def create_program(payload: ProgramIn, current_user: CurrentUser, db: DbSession) -> ProgramOut:
    program = Program(owner_user_id=current_user.id, **payload.model_dump())
    db.add(program)
    db.commit()
    return _program_out(db, current_user, program)


@router.get("/programs/{program_id}", response_model=ProgramOut)
def read_program(program_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ProgramOut:
    return _program_out(db, current_user, _readable_program(db, current_user, program_id))


@router.put("/programs/{program_id}", response_model=ProgramOut)
def update_program(program_id: uuid.UUID, payload: ProgramIn, current_user: CurrentUser,
                   db: DbSession) -> ProgramOut:
    program = _owned_program(db, current_user, program_id)
    for field, value in payload.model_dump().items():
        setattr(program, field, value)
    db.commit()
    return _program_out(db, current_user, program)


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(program_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Its routines stay, as standalone routines (program_id is SET NULL)."""
    db.delete(_owned_program(db, current_user, program_id))
    db.execute(delete(Favorite).where(Favorite.target_type == "program",
                                      Favorite.target_id == program_id))
    db.commit()


# ---------------------------------------------------------------------------
# Favourites
# ---------------------------------------------------------------------------


def _target_exists(db: Session, user: User, target_type: str, target_id: uuid.UUID) -> bool:
    if target_type == "routine":
        return db.execute(select(Routine.id).where(Routine.id == target_id,
                                                   Routine.user_id == user.id)).first() is not None
    if target_type == "exercise":
        return store.get_visible_exercise(db, target_id, user.id) is not None
    program = db.get(Program, target_id)
    return program is not None and (program.owner_user_id in (None, user.id) or program.is_public)


@router.post("/favorites", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(payload: FavoriteIn, current_user: CurrentUser, db: DbSession) -> None:
    """Star something. Starring it again is not an error."""
    if not _target_exists(db, current_user, payload.target_type, payload.target_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.add(Favorite(user_id=current_user.id, **payload.model_dump()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # already a favourite


@router.delete("/favorites/{target_type}/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(target_type: str, target_id: uuid.UUID, current_user: CurrentUser,
                    db: DbSession) -> None:
    db.execute(delete(Favorite).where(Favorite.user_id == current_user.id,
                                      Favorite.target_type == target_type,
                                      Favorite.target_id == target_id))
    db.commit()


# ---------------------------------------------------------------------------
# The library listing
# ---------------------------------------------------------------------------


@router.get("/library", response_model=LibraryPage)
def library(
    current_user: CurrentUser,
    db: DbSession,
    filter: str = Query(default="programs", pattern="^(programs|routines|exercises|favorites)$"),
    sort: str = Query(default="recents", pattern="^(recents|name|most_used)$"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
) -> LibraryPage:
    """One list for the Library tab. Programs and routines are the caller's;
    exercises are the ones they have logged. Sorted by recent use, name, or
    how often they have been used."""
    fav_routines = _favorites(db, current_user, "routine")
    fav_programs = _favorites(db, current_user, "program")
    fav_exercises = _favorites(db, current_user, "exercise")
    items: list[tuple[LibraryItem, float]] = []

    if filter in ("routines", "favorites"):
        routines = list(db.scalars(select(Routine).where(Routine.user_id == current_user.id)))
        last = last_performed(db, [r.id for r in routines])
        ids = [r.id for r in routines]
        exercise_counts = dict(db.execute(
            select(RoutineExercise.routine_id, func.count(RoutineExercise.id))
            .where(RoutineExercise.routine_id.in_(ids))
            .group_by(RoutineExercise.routine_id)).tuples().all()) if ids else {}
        # "Most used" = workouts actually done from it.
        done = dict(db.execute(
            select(WorkoutSession.routine_id, func.count(WorkoutSession.id))
            .where(WorkoutSession.routine_id.in_(ids),
                   WorkoutSession.status == SessionStatus.COMPLETED.value)
            .group_by(WorkoutSession.routine_id)).tuples().all()) if ids else {}
        for r in routines:
            if filter == "favorites" and r.id not in fav_routines:
                continue
            n = exercise_counts.get(r.id, 0)
            items.append((LibraryItem(type="routine", id=r.id, title=r.name,
                                      subtitle=f"{n} exercise{'s' if n != 1 else ''}", color=r.color,
                                      favorite=r.id in fav_routines, last_used_at=last.get(r.id)),
                          done.get(r.id, 0)))
    if filter in ("programs", "favorites"):
        programs = list(db.scalars(select(Program).where(Program.owner_user_id == current_user.id)))
        counts = dict(db.execute(
            select(Routine.program_id, func.count(Routine.id))
            .where(Routine.program_id.in_([p.id for p in programs]))
            .group_by(Routine.program_id)).tuples().all()) if programs else {}
        for p in programs:
            if filter == "favorites" and p.id not in fav_programs:
                continue
            n = counts.get(p.id, 0)
            items.append((LibraryItem(type="program", id=p.id, title=p.name,
                                      subtitle=f"{n} routine{'s' if n != 1 else ''}",
                                      color=p.cover_color, favorite=p.id in fav_programs,
                                      last_used_at=p.updated_at), n))
    if filter in ("exercises", "favorites"):
        logged = db.execute(
            select(SetEntry.exercise_id, func.count(SetEntry.id), func.max(SetEntry.completed_at))
            .where(SetEntry.user_id == current_user.id)
            .group_by(SetEntry.exercise_id)).all()
        stats = {row[0]: (row[1], row[2]) for row in logged}
        ids = set(stats) | (fav_exercises if filter == "favorites" else set())
        if filter == "favorites":
            ids &= fav_exercises
        exercises = list(db.scalars(select(Exercise).where(Exercise.id.in_(ids)))) if ids else []
        for e in exercises:
            count, when = stats.get(e.id, (0, None))
            muscle = (e.primary_muscle_groups or [""])[0].replace("_", " ").capitalize()
            items.append((LibraryItem(type="exercise", id=e.id, title=e.name,
                                      subtitle=f"{muscle} · {e.equipment.replace('_', ' ').capitalize()}",
                                      image=e.thumbnail_url, favorite=e.id in fav_exercises,
                                      last_used_at=when), count))

    epoch = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    if sort == "name":
        items.sort(key=lambda pair: pair[0].title.casefold())
    elif sort == "most_used":
        items.sort(key=lambda pair: (-pair[1], pair[0].title.casefold()))
    else:
        items.sort(key=lambda pair: pair[0].last_used_at or epoch, reverse=True)

    start = _offset(cursor)
    page = [item for item, _ in items[start:start + limit]]
    return LibraryPage(
        items=page,
        favorite_count=len(fav_routines) + len(fav_programs) + len(fav_exercises),
        next_cursor=_cursor(start + limit) if start + limit < len(items) else None,
    )


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


@router.get("/workouts/suggested", response_model=list[SuggestedOut])
def suggested(current_user: CurrentUser, db: DbSession) -> list[SuggestedOut]:
    """The caller's routines, longest left alone first, nudged toward their
    training path."""
    routines = list(db.scalars(select(Routine).where(Routine.user_id == current_user.id)))
    if not routines:
        return []
    last = last_performed(db, [r.id for r in routines])
    counts = dict(db.execute(
        select(RoutineExercise.routine_id, func.count(RoutineExercise.id))
        .where(RoutineExercise.routine_id.in_([r.id for r in routines]))
        .group_by(RoutineExercise.routine_id)).tuples().all())
    by_id = {r.id: r for r in routines}

    def category(r: Routine) -> str | None:
        preset = presets.by_slug(r.preset_slug) if r.preset_slug else None
        if preset is not None:
            return preset.category
        program = db.get(Program, r.program_id) if r.program_id else None
        return program.training_category if program else None

    ranked = suggestions.rank(
        [suggestions.Candidate(r.id, r.name, last.get(r.id), category(r)) for r in routines],
        path=current_user.character_class, now=dt.datetime.now(dt.timezone.utc),
    )
    return [
        SuggestedOut(
            routine_id=x.candidate.routine_id, name=x.candidate.name,
            abbreviation=suggestions.abbreviation(x.candidate.name),
            color=by_id[x.candidate.routine_id].color,
            exercise_count=counts.get(x.candidate.routine_id, 0),
            last_performed_at=x.candidate.last_performed_at, days_since=x.days_since,
            fits_path=x.fits_path,
        )
        for x in ranked
    ]
