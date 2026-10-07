"""People, follows, the following feed, reactions, notifications, the
friends leaderboard and the game strip (overhaul phase 4).

Every rule about who may see what is in app/core/social.py. Lists are
keyset-paged; feed and profile reads use the totals written at finish.
"""

from __future__ import annotations

import base64
import datetime as dt
import uuid
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import leveling, social
from app.core import quest_board as board
from app.core import streak_freezes as freezes
from app.core.periods import local_now, resolve_timezone
from app.core.progression import lock_progress
from app.models.quest_board import AssignmentStatus
from app.models.social import Follow, Notification, Reaction
from app.models.user import LevelProgress, User
from app.models.workout import Exercise, PointsLedgerEntry, SessionExercise, SetEntry, WorkoutSession
from app.models.workout_enums import SessionStatus
from app.schemas.social import (
    FeedExercise,
    FeedItem,
    FeedPage,
    GameOut,
    LeaderboardOut,
    LeaderboardRow,
    NotificationOut,
    NotificationPage,
    ProfileOut,
    ReactionOut,
    ReadIn,
    ReadOut,
    UserCard,
    UserPage,
)

router = APIRouter(tags=["social"])

FEED_EXERCISES = 6
SUGGESTED = 10


# ---------------------------------------------------------------------------
# Cursors and cards
# ---------------------------------------------------------------------------


def _encode(*parts: object) -> str:
    return base64.urlsafe_b64encode("|".join(str(p) for p in parts).encode()).decode()


def _decode(cursor: str, n: int) -> list[str]:
    try:
        parts = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        if len(parts) != n:
            raise ValueError
        return parts
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Bad cursor") from None


def cards(db: Session, viewer: User, users: list[User], reasons: dict[uuid.UUID, str] | None = None) -> list[UserCard]:
    ids = [u.id for u in users]
    if not ids:
        return []
    i_follow = set(db.scalars(select(Follow.followee_id).where(
        Follow.follower_id == viewer.id, Follow.followee_id.in_(ids))))
    follow_me = set(db.scalars(select(Follow.follower_id).where(
        Follow.followee_id == viewer.id, Follow.follower_id.in_(ids))))
    rank = social.ranks(db, users)
    return [UserCard(id=u.id, display_name=u.display_name, username=u.username, avatar_url=u.avatar_url,
                     rank=rank[u.id][0], level=rank[u.id][1], training_category=u.character_class or None,
                     you_follow=u.id in i_follow, follows_you=u.id in follow_me,
                     reason=(reasons or {}).get(u.id)) for u in users]


def _user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


# ---------------------------------------------------------------------------
# Follows
# ---------------------------------------------------------------------------


@router.post("/follows/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def follow(user_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Follow someone. Following them again is not an error."""
    if user_id == current_user.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "You cannot follow yourself")
    _user(db, user_id)
    if social.follows(db, current_user.id, user_id):
        return
    db.add(Follow(follower_id=current_user.id, followee_id=user_id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return
    social.notify(db, user_id, "follow", actor_id=current_user.id, target_type="user", target_id=current_user.id)
    db.commit()


@router.delete("/follows/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfollow(user_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    db.execute(delete(Follow).where(Follow.follower_id == current_user.id, Follow.followee_id == user_id))
    db.commit()


def _people(db: Session, viewer: User, query, cursor: str | None, limit: int) -> UserPage:
    """A page of users from `query` (a select of User), by name."""
    if cursor:
        name, row_id = _decode(cursor, 2)
        query = query.where(or_(func.lower(User.display_name) > name,
                                and_(func.lower(User.display_name) == name, User.id > uuid.UUID(row_id))))
    rows = list(db.scalars(query.order_by(func.lower(User.display_name), User.id).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    return UserPage(items=cards(db, viewer, rows),
                    next_cursor=_encode(rows[-1].display_name.lower(), rows[-1].id) if more else None)


@router.get("/users/{user_id}/followers", response_model=UserPage)
def followers(user_id: uuid.UUID, current_user: CurrentUser, db: DbSession, cursor: str | None = None,
              limit: int = Query(default=30, ge=1, le=100)) -> UserPage:
    _user(db, user_id)
    query = select(User).join(Follow, Follow.follower_id == User.id).where(Follow.followee_id == user_id)
    return _people(db, current_user, query, cursor, limit)


@router.get("/users/{user_id}/following", response_model=UserPage)
def following(user_id: uuid.UUID, current_user: CurrentUser, db: DbSession, cursor: str | None = None,
              limit: int = Query(default=30, ge=1, le=100)) -> UserPage:
    _user(db, user_id)
    query = select(User).join(Follow, Follow.followee_id == User.id).where(Follow.follower_id == user_id)
    return _people(db, current_user, query, cursor, limit)


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


@router.get("/users/search", response_model=UserPage)
def search_users(current_user: CurrentUser, db: DbSession,
                 q: str = Query(min_length=1, max_length=50), cursor: str | None = None,
                 limit: int = Query(default=20, ge=1, le=50)) -> UserPage:
    """By display name or username. Never yourself; never by email - finding
    out whether an address has an account is not a feature."""
    needle = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    query = select(User).where(User.is_active.is_(True), User.id != current_user.id, or_(
        func.lower(User.display_name).like(f"%{needle}%", escape="\\"),
        User.username_normalized.like(f"%{needle}%", escape="\\")))
    return _people(db, current_user, query, cursor, limit)


@router.get("/users/suggested", response_model=UserPage)
def suggested_users(current_user: CurrentUser, db: DbSession) -> UserPage:
    """People you may know: followed by people you follow, then your party
    mates - never someone you already follow."""
    mine = social.following_ids(db, current_user.id)
    reasons: dict[uuid.UUID, str] = {}
    counts: dict[uuid.UUID, int] = defaultdict(int)
    via: dict[uuid.UUID, uuid.UUID] = {}
    if mine:
        for follower, followee in db.execute(select(Follow.follower_id, Follow.followee_id).where(
                Follow.follower_id.in_(mine))):
            if followee != current_user.id and followee not in mine:
                counts[followee] += 1
                via.setdefault(followee, follower)
    ranked = sorted(counts, key=lambda u: -counts[u])[:SUGGESTED]
    names = {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_(set(via.values()))))} if via else {}
    for uid in ranked:
        others = counts[uid] - 1
        reasons[uid] = f"Followed by {names.get(via[uid], 'a friend')}" + (f" and {others} more" if others else "")
    for uid in social.party_mates(db, current_user.id) - mine - set(ranked):
        if len(ranked) >= SUGGESTED:
            break
        ranked.append(uid)
        reasons[uid] = "In your party"
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ranked), User.is_active.is_(True)))}
    return UserPage(items=cards(db, current_user, [users[u] for u in ranked if u in users], reasons))


@router.get("/users/{user_id}", response_model=ProfileOut)
def profile(user_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ProfileOut:
    user = _user(db, user_id)
    workouts = db.scalar(select(func.count(WorkoutSession.id)).where(
        WorkoutSession.user_id == user.id, social.visible_to(current_user.id))) or 0
    return ProfileOut(
        user=cards(db, current_user, [user])[0], bio=user.bio,
        followers=db.scalar(select(func.count()).select_from(Follow).where(Follow.followee_id == user.id)) or 0,
        following=db.scalar(select(func.count()).select_from(Follow).where(Follow.follower_id == user.id)) or 0,
        workouts=workouts, is_friend=social.are_friends(db, current_user.id, user.id),
        is_me=user.id == current_user.id,
    )


# ---------------------------------------------------------------------------
# The feed
# ---------------------------------------------------------------------------


def _feed_items(db: Session, viewer: User, sessions: list[WorkoutSession]) -> list[FeedItem]:
    if not sessions:
        return []
    ids = [s.id for s in sessions]
    owners = {u.id: u for u in db.scalars(select(User).where(User.id.in_({s.user_id for s in sessions})))}
    owner_cards = {c.id: c for c in cards(db, viewer, list(owners.values()))}
    exercises: dict[uuid.UUID, list[FeedExercise]] = defaultdict(list)
    count: dict[uuid.UUID, int] = defaultdict(int)
    working = dict(db.execute(
        select(SetEntry.session_exercise_id, func.count(SetEntry.id))
        .where(SetEntry.session_id.in_(ids), SetEntry.is_warmup.is_(False))
        .group_by(SetEntry.session_exercise_id)).tuples().all())
    for card, ex in db.execute(
            select(SessionExercise, Exercise).join(Exercise, Exercise.id == SessionExercise.exercise_id)
            .where(SessionExercise.session_id.in_(ids)).order_by(SessionExercise.position)):
        sets = working.get(card.id, 0)
        if not sets:
            continue
        count[card.session_id] += 1
        if len(exercises[card.session_id]) < FEED_EXERCISES:
            exercises[card.session_id].append(FeedExercise(name=ex.name, thumbnail_url=ex.thumbnail_url, sets=sets))
    spotted = dict(db.execute(select(Reaction.session_id, func.count(Reaction.id))
                              .where(Reaction.session_id.in_(ids)).group_by(Reaction.session_id)).tuples().all())
    mine = set(db.scalars(select(Reaction.session_id).where(Reaction.session_id.in_(ids),
                                                            Reaction.user_id == viewer.id)))
    out = []
    for s in sessions:
        duration = s.duration_seconds if s.duration_seconds is not None else int(
            (s.ended_at - s.started_at).total_seconds())
        out.append(FeedItem(
            session_id=s.id, user=owner_cards[s.user_id], name=s.name, started_at=s.started_at,
            ended_at=s.ended_at, visibility=s.visibility, duration_seconds=max(0, duration),
            volume_kg=float(s.total_volume_kg or 0), working_sets=s.total_working_sets or 0,
            records=s.total_prs or 0, points=s.points_credited, exercises=exercises[s.id],
            more_exercises=max(0, count[s.id] - len(exercises[s.id])), spotted=spotted.get(s.id, 0),
            spotted_by_me=s.id in mine,
        ))
    return out


def _session_page(db: Session, viewer: User, query, cursor: str | None, limit: int) -> FeedPage:
    if cursor:
        at, row_id = _decode(cursor, 2)
        when = dt.datetime.fromisoformat(at)
        query = query.where(or_(WorkoutSession.ended_at < when,
                                and_(WorkoutSession.ended_at == when, WorkoutSession.id < uuid.UUID(row_id))))
    rows = list(db.scalars(query.order_by(WorkoutSession.ended_at.desc(), WorkoutSession.id.desc()).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    return FeedPage(items=_feed_items(db, viewer, rows),
                    next_cursor=_encode(rows[-1].ended_at.isoformat(), rows[-1].id) if more else None)


@router.get("/feed/following", response_model=FeedPage)
def following_feed(current_user: CurrentUser, db: DbSession, cursor: str | None = None,
                   limit: int = Query(default=10, ge=1, le=50)) -> FeedPage:
    """Finished workouts by you and the people you follow, newest first, each
    as its owner's visibility allows."""
    people = social.following_ids(db, current_user.id) | {current_user.id}
    query = select(WorkoutSession).where(WorkoutSession.user_id.in_(people), social.visible_to(current_user.id))
    return _session_page(db, current_user, query, cursor, limit)


@router.get("/users/{user_id}/sessions", response_model=FeedPage)
def user_sessions(user_id: uuid.UUID, current_user: CurrentUser, db: DbSession, cursor: str | None = None,
                  limit: int = Query(default=10, ge=1, le=50)) -> FeedPage:
    _user(db, user_id)
    query = select(WorkoutSession).where(WorkoutSession.user_id == user_id, social.visible_to(current_user.id))
    return _session_page(db, current_user, query, cursor, limit)


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------


def _visible_session(db: Session, viewer: User, session_id: uuid.UUID) -> WorkoutSession:
    session = db.get(WorkoutSession, session_id)
    if session is None or not social.can_see(db, viewer.id, session) or session.status != SessionStatus.COMPLETED.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workout not found")
    return session


def _reaction_out(db: Session, viewer: User, session_id: uuid.UUID) -> ReactionOut:
    return ReactionOut(
        spotted=db.scalar(select(func.count(Reaction.id)).where(Reaction.session_id == session_id)) or 0,
        spotted_by_me=db.scalar(select(Reaction.id).where(Reaction.session_id == session_id,
                                                          Reaction.user_id == viewer.id)) is not None)


@router.get("/workouts/sessions/{session_id}/reactions", response_model=ReactionOut)
def reactions(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ReactionOut:
    return _reaction_out(db, current_user, _visible_session(db, current_user, session_id).id)


@router.post("/workouts/sessions/{session_id}/reactions", response_model=ReactionOut)
def spot(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ReactionOut:
    """"Spotted": a nod to a workout you can see. Once per person."""
    session = _visible_session(db, current_user, session_id)
    if db.scalar(select(Reaction.id).where(Reaction.session_id == session.id,
                                           Reaction.user_id == current_user.id)) is None:
        db.add(Reaction(user_id=current_user.id, session_id=session.id, type="spotted"))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
        else:
            social.notify(db, session.user_id, "reaction", actor_id=current_user.id, target_type="session",
                          target_id=session.id, detail=session.name)
            db.commit()
    return _reaction_out(db, current_user, session.id)


@router.delete("/workouts/sessions/{session_id}/reactions", response_model=ReactionOut)
def unspot(session_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ReactionOut:
    session = _visible_session(db, current_user, session_id)
    db.execute(delete(Reaction).where(Reaction.session_id == session.id, Reaction.user_id == current_user.id))
    db.commit()
    return _reaction_out(db, current_user, session.id)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def _unread(db: Session, user: User) -> int:
    return db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0


@router.get("/notifications", response_model=NotificationPage)
def notifications(current_user: CurrentUser, db: DbSession, cursor: str | None = None,
                  limit: int = Query(default=30, ge=1, le=100)) -> NotificationPage:
    query = select(Notification).where(Notification.user_id == current_user.id)
    if cursor:
        at, row_id = _decode(cursor, 2)
        when = dt.datetime.fromisoformat(at)
        query = query.where(or_(Notification.created_at < when,
                                and_(Notification.created_at == when, Notification.id < uuid.UUID(row_id))))
    rows = list(db.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    actors = {u.id: u for u in db.scalars(select(User).where(
        User.id.in_({n.actor_user_id for n in rows if n.actor_user_id})))}
    actor_cards = {c.id: c for c in cards(db, current_user, list(actors.values()))}
    return NotificationPage(
        items=[NotificationOut(id=n.id, type=n.type, actor=actor_cards.get(n.actor_user_id),
                               target_type=n.target_type, target_id=n.target_id, detail=n.detail,
                               read=n.read_at is not None, created_at=n.created_at) for n in rows],
        unread=_unread(db, current_user),
        next_cursor=_encode(rows[-1].created_at.isoformat(), rows[-1].id) if more else None,
    )


@router.post("/notifications/read", response_model=ReadOut)
def mark_read(payload: ReadIn, current_user: CurrentUser, db: DbSession) -> ReadOut:
    """Mark the given notifications read - or all of them."""
    from sqlalchemy import update

    query = update(Notification).where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
    if payload.ids:
        query = query.where(Notification.id.in_(payload.ids))
    db.execute(query.values(read_at=dt.datetime.now(dt.timezone.utc)))
    db.commit()
    return ReadOut(unread=_unread(db, current_user))


# ---------------------------------------------------------------------------
# The game strip and the friends leaderboard
# ---------------------------------------------------------------------------


def _week_start(user: User) -> dt.datetime:
    today = local_now(user.timezone).date()
    monday = today - dt.timedelta(days=today.weekday())
    return dt.datetime.combine(monday, dt.time(), tzinfo=resolve_timezone(user.timezone))


def _points(db: Session, user_ids: set[uuid.UUID], since: dt.datetime | None) -> dict[uuid.UUID, int]:
    query = select(PointsLedgerEntry.user_id, func.coalesce(func.sum(PointsLedgerEntry.points), 0)).where(
        PointsLedgerEntry.user_id.in_(user_ids))
    if since is not None:
        query = query.where(PointsLedgerEntry.created_at >= since)
    return {uid: int(total) for uid, total in db.execute(query.group_by(PointsLedgerEntry.user_id))}


@router.get("/me/game", response_model=GameOut)
def game(current_user: CurrentUser, db: DbSession) -> GameOut:
    """Home's game strip: rank and the XP to the next one, points this week,
    quests done, the weekly streak, unread notifications."""
    now = dt.datetime.now(dt.timezone.utc)
    progress = lock_progress(db, current_user.id)
    streak_state, _ = freezes.current_streak(db, current_user, now)
    quests = board.ensure_assignments(db, current_user, now)
    today = local_now(current_user.timezone).date()
    day_streak = leveling.effective_streak(progress.current_streak, progress.last_completed_on, today)
    rank = leveling.rank_for(progress.current_level, day_streak, progress.trials_passed)
    nxt = leveling.next_rank_requirement(progress.current_level, day_streak, progress.trials_passed)
    out = GameOut(
        rank=rank.value, level=progress.current_level, next_rank=nxt[0].value if nxt else None,
        xp=progress.total_xp, xp_next_rank=leveling.xp_for_level(nxt[1]) if nxt else None,
        points_this_week=_points(db, {current_user.id}, _week_start(current_user)).get(current_user.id, 0),
        quests_done=sum(1 for a in quests if a.status == AssignmentStatus.COMPLETED.value),
        quests_total=len(quests), streak_weeks=streak_state.weeks,
        unread_notifications=_unread(db, current_user),
    )
    db.commit()
    return out


@router.get("/leaderboard/friends", response_model=LeaderboardOut)
def friends_leaderboard(current_user: CurrentUser, db: DbSession,
                        period: str = Query(default="week", pattern="^(week|all)$"),
                        limit: int = Query(default=50, ge=1, le=100)) -> LeaderboardOut:
    """You and the people you follow, by workout points - this week (your
    week) or all time. Ties share a position."""
    people = social.following_ids(db, current_user.id) | {current_user.id}
    points = _points(db, people, _week_start(current_user) if period == "week" else None)
    users = list(db.scalars(select(User).where(User.id.in_(people), User.is_active.is_(True))))
    users.sort(key=lambda u: (-points.get(u.id, 0), u.display_name.lower()))
    by_id = {c.id: c for c in cards(db, current_user, users)}
    rows, position, last = [], 0, None
    for index, u in enumerate(users):
        score = points.get(u.id, 0)
        if score != last:
            position, last = index + 1, score
        rows.append(LeaderboardRow(position=position, user=by_id[u.id], points=score, is_me=u.id == current_user.id))
    me = next(r for r in rows if r.is_me)
    return LeaderboardOut(period=period, rows=rows[:limit], me=me)
