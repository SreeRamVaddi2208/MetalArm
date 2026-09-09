"""Quest CRUD and the completion endpoint."""

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core.periods import period_key
from app.core.progression import apply_completion, lock_progress
from app.models.enums import QuestStatus
from app.models.quest import Quest, QuestCompletion
from app.models.user import User
from app.schemas.quest import (
    CompleteQuestResponse,
    CompletionOut,
    ProgressionDeltaOut,
    QuestCreate,
    QuestOut,
    QuestUpdate,
)

logger = logging.getLogger("levelforge.quests")

router = APIRouter(prefix="/quests", tags=["quests"])


def _get_owned_quest(db: Session, quest_id: uuid.UUID, user: User) -> Quest:
    """Fetch a quest the caller owns, or 404.

    404 rather than 403 for someone else's quest: a 403 would confirm that the
    ID exists, letting a caller enumerate other users' quests.
    """
    quest = db.execute(
        select(Quest).where(Quest.id == quest_id, Quest.owner_id == user.id)
    ).scalar_one_or_none()
    if quest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found"
        )
    return quest


def _serialize(quest: Quest, *, current_key: str, done: bool) -> QuestOut:
    return QuestOut(
        id=quest.id,
        title=quest.title,
        description=quest.description,
        xp_reward=quest.xp_reward,
        points_reward=quest.points_reward,
        recurrence=quest.recurrence,
        status=quest.status.value,
        due_at=quest.due_at,
        created_at=quest.created_at,
        current_period_key=current_key,
        completed_in_current_period=done,
    )


def _serialize_many(
    db: Session, quests: list[Quest], user: User, now: dt.datetime
) -> list[QuestOut]:
    """Attach per-period completion state to a list of quests.

    Uses ONE query for all of them rather than a lookup per quest: the quest
    board renders every active quest at once, and a per-row query would make
    the board's cost grow linearly with a user's quest count.
    """
    keys = {q.id: period_key(q.recurrence, now, user.timezone) for q in quests}
    done: set[tuple[uuid.UUID, str]] = set()

    if keys:
        pairs = list(keys.items())
        rows = db.execute(
            select(QuestCompletion.quest_id, QuestCompletion.period_key).where(
                QuestCompletion.user_id == user.id,
                tuple_(QuestCompletion.quest_id, QuestCompletion.period_key).in_(pairs),
            )
        ).all()
        done = {(r.quest_id, r.period_key) for r in rows}

    return [
        _serialize(q, current_key=keys[q.id], done=(q.id, keys[q.id]) in done)
        for q in quests
    ]


@router.get("", response_model=list[QuestOut])
def list_quests(
    current_user: CurrentUser,
    db: DbSession,
    quest_status: QuestStatus = Query(
        default=QuestStatus.ACTIVE,
        alias="status",
        description="Filter by quest status. Archived quests are hidden by default.",
    ),
) -> list[QuestOut]:
    """The caller's quest board, newest first."""
    quests = list(
        db.execute(
            select(Quest)
            .where(Quest.owner_id == current_user.id, Quest.status == quest_status)
            .order_by(Quest.created_at.desc())
        ).scalars()
    )
    now = dt.datetime.now(dt.timezone.utc)
    return _serialize_many(db, quests, current_user, now)


@router.post("", response_model=QuestOut, status_code=status.HTTP_201_CREATED)
def create_quest(
    payload: QuestCreate, current_user: CurrentUser, db: DbSession
) -> QuestOut:
    quest = Quest(
        owner_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description,
        xp_reward=payload.xp_reward,
        points_reward=payload.points_reward,
        recurrence=payload.recurrence.value,
        status=QuestStatus.ACTIVE,
        due_at=payload.due_at,
    )
    db.add(quest)
    db.commit()
    db.refresh(quest)

    now = dt.datetime.now(dt.timezone.utc)
    return _serialize(
        quest,
        current_key=period_key(quest.recurrence, now, current_user.timezone),
        done=False,  # Freshly created; nothing can have completed it yet.
    )


@router.get("/{quest_id}", response_model=QuestOut)
def get_quest(
    quest_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> QuestOut:
    quest = _get_owned_quest(db, quest_id, current_user)
    now = dt.datetime.now(dt.timezone.utc)
    return _serialize_many(db, [quest], current_user, now)[0]


@router.patch("/{quest_id}", response_model=QuestOut)
def update_quest(
    quest_id: uuid.UUID,
    payload: QuestUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> QuestOut:
    """Partial update.

    Editing xp_reward does NOT rewrite past awards: quest_completions snapshots
    xp_awarded at completion time, so history stays auditable and a user can't
    retroactively inflate earned XP by raising a quest's reward.
    """
    quest = _get_owned_quest(db, quest_id, current_user)
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if field == "recurrence" and value is not None:
            quest.recurrence = value.value
        elif field == "title" and value is not None:
            quest.title = value.strip()
        else:
            setattr(quest, field, value)

    db.commit()
    db.refresh(quest)

    now = dt.datetime.now(dt.timezone.utc)
    return _serialize_many(db, [quest], current_user, now)[0]


@router.delete("/{quest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quest(
    quest_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """Hard-delete a quest and its completion rows (FK ON DELETE CASCADE).

    Already-earned XP is NOT clawed back - total_xp is cumulative and the XP
    was legitimately earned. Callers wanting to keep the audit trail should
    PATCH status='archived' instead.
    """
    quest = _get_owned_quest(db, quest_id, current_user)
    db.delete(quest)
    db.commit()


@router.post("/{quest_id}/complete", response_model=CompleteQuestResponse)
def complete_quest(
    quest_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> CompleteQuestResponse:
    """Complete a quest for the current period, awarding XP and points.

    Ordering inside the transaction is deliberate:

    1. Lock level_progress FOR UPDATE. Every writer takes this lock first, so
       concurrent completions serialize per user and no award is lost - and
       because the order is consistent, no deadlock is possible.
    2. Insert the completion. UNIQUE(quest_id, user_id, period_key) is what
       actually prevents double-awarding; checking "already completed?" in
       Python first would still race between the check and the insert.
    3. Apply XP/points/streak, then commit both together. If the insert fails,
       the whole transaction rolls back and no XP is granted.
    """
    quest = _get_owned_quest(db, quest_id, current_user)

    if quest.status != QuestStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot complete an archived quest",
        )

    now = dt.datetime.now(dt.timezone.utc)
    key = period_key(quest.recurrence, now, current_user.timezone)

    progress = lock_progress(db, current_user.id)

    completion = QuestCompletion(
        quest_id=quest.id,
        user_id=current_user.id,
        period_key=key,
        completed_at=now,
        # Snapshot the reward as it stands right now.
        xp_awarded=quest.xp_reward,
        points_awarded=quest.points_reward,
    )
    db.add(completion)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quest already completed for this period ({key})",
        ) from None

    delta = apply_completion(
        progress,
        xp=quest.xp_reward,
        points=quest.points_reward,
        completed_at=now,
        tz_name=current_user.timezone,
    )

    db.commit()
    db.refresh(completion)

    if delta.leveled_up:
        logger.info(
            "user %s leveled %s -> %s", current_user.id, delta.level_before, delta.level_after
        )

    return CompleteQuestResponse(
        completion=CompletionOut.model_validate(completion),
        progression=ProgressionDeltaOut(
            **{
                **delta.__dict__,
                "leveled_up": delta.leveled_up,
                "ranked_up": delta.ranked_up,
            }
        ),
    )
