"""The social graph's rules, in one place: who follows whom, who are friends
(mutual follows), who may see a workout, and writing notifications.

Visibility of a finished workout:
    public     anyone signed in
    followers  its owner's followers (a one-way follow is enough)
    private    its owner only
A workout in progress or abandoned is its owner's only, whatever it says.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.core import leveling
from app.core.periods import local_now
from app.models.party import PartyMembership
from app.models.social import Follow, Notification
from app.models.user import LevelProgress, User
from app.models.workout import WorkoutSession
from app.models.workout_enums import SessionStatus, Visibility


def following_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    return set(db.scalars(select(Follow.followee_id).where(Follow.follower_id == user_id)))


def follower_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    return set(db.scalars(select(Follow.follower_id).where(Follow.followee_id == user_id)))


def follows(db: Session, follower: uuid.UUID, followee: uuid.UUID) -> bool:
    return db.get(Follow, (follower, followee)) is not None


def friend_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Mutual follows."""
    return following_ids(db, user_id) & follower_ids(db, user_id)


def are_friends(db: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    return follows(db, a, b) and follows(db, b, a)


def party_mates(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    parties = select(PartyMembership.party_id).where(PartyMembership.user_id == user_id)
    return set(db.scalars(select(PartyMembership.user_id).where(
        PartyMembership.party_id.in_(parties), PartyMembership.user_id != user_id)))


def can_see(db: Session, viewer_id: uuid.UUID, session: WorkoutSession) -> bool:
    if session.user_id == viewer_id:
        return True
    if session.status != SessionStatus.COMPLETED.value:
        return False
    if session.visibility == Visibility.PUBLIC.value:
        return True
    if session.visibility == Visibility.FOLLOWERS.value:
        return follows(db, viewer_id, session.user_id)
    return False


def visible_to(viewer_id: uuid.UUID):
    """The same rule as a SQL condition on WorkoutSession (completed ones)."""
    from sqlalchemy import or_

    following = exists().where(Follow.follower_id == viewer_id, Follow.followee_id == WorkoutSession.user_id)
    return and_(
        WorkoutSession.status == SessionStatus.COMPLETED.value,
        or_(
            WorkoutSession.user_id == viewer_id,
            WorkoutSession.visibility == Visibility.PUBLIC.value,
            and_(WorkoutSession.visibility == Visibility.FOLLOWERS.value, following),
        ),
    )


def ranks(db: Session, users: Iterable[User]) -> dict[uuid.UUID, tuple[str, int]]:
    """(rank letter, level) per user - derived as /auth/me derives it, so a
    lapsed streak shows the rank actually held."""
    users = list(users)
    progress = {p.user_id: p for p in db.scalars(
        select(LevelProgress).where(LevelProgress.user_id.in_([u.id for u in users])))}
    out = {}
    for u in users:
        p = progress.get(u.id)
        if p is None:
            out[u.id] = ("E", 1)
            continue
        streak = leveling.effective_streak(p.current_streak, p.last_completed_on, local_now(u.timezone).date())
        out[u.id] = (leveling.rank_for(p.current_level, streak, p.trials_passed).value, p.current_level)
    return out


def notify(db: Session, user_id: uuid.UUID, kind: str, *, actor_id: uuid.UUID | None = None,
           target_type: str | None = None, target_id: uuid.UUID | None = None,
           detail: str | None = None, now: dt.datetime | None = None) -> None:
    """Write one notification. Nobody is told about their own action, and a
    repeat of an UNREAD one (follow, unfollow, follow again) is not stacked."""
    if actor_id is not None and actor_id == user_id:
        return
    dupe = db.scalar(select(Notification.id).where(
        Notification.user_id == user_id, Notification.type == kind,
        Notification.actor_user_id.is_(None) if actor_id is None else Notification.actor_user_id == actor_id,
        Notification.target_id.is_(None) if target_id is None else Notification.target_id == target_id,
        Notification.read_at.is_(None)).limit(1))
    if dupe is not None:
        return
    db.add(Notification(user_id=user_id, type=kind, actor_user_id=actor_id, target_type=target_type,
                        target_id=target_id, detail=(detail or None) and detail[:160],
                        created_at=now or dt.datetime.now(dt.timezone.utc)))
