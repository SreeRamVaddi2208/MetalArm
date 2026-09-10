"""Parties/guilds: membership, the shared quest board, and the leaderboard.

Settled with the user on 2026-09-10:
  - Periodic refresh, not WebSockets. Everything here is plain REST.
  - Max 10 members; parties are freely created and dissolved.
  - A leaving owner hands the party to the longest-serving member rather than
    orphaning it.
  - Party XP counts only what was earned WHILE a member, which falls out of the
    schema: a party quest cannot be completed by someone outside the party.
"""

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.core import leaderboard, leveling
from app.core.invites import generate_invite_code, normalize_invite_code
from app.core.periods import local_date, period_key
from app.core.progression import apply_completion, lock_progress
from app.models.enums import PartyRole
from app.models.party import (
    Party,
    PartyMembership,
    PartyQuest,
    PartyQuestCompletion,
)
from app.models.user import LevelProgress, User
from app.schemas.party import (
    JoinRequest,
    LeaderboardEntry,
    LeaderboardOut,
    MemberOut,
    PartyCreate,
    PartyOut,
    PartyQuestCompleteResponse,
    PartyQuestCreate,
    PartyQuestOut,
    PartyQuestUpdate,
    PartyUpdate,
)

logger = logging.getLogger("levelforge.parties")

router = APIRouter(prefix="/parties", tags=["parties"])

# Invite codes are drawn from a 8.5e11 space, so a collision is vanishingly
# unlikely - but "unlikely" is not "impossible", and the column is UNIQUE.
MAX_CODE_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _membership_or_404(
    db: Session, party_id: uuid.UUID, user: User, *, require_active: bool = True
) -> tuple[Party, PartyMembership]:
    """Fetch the party and the caller's membership, or 404.

    404 rather than 403 for a party the caller is not in: a 403 would confirm
    the party exists, letting someone probe for valid ids.
    """
    row = db.execute(
        select(Party, PartyMembership)
        .join(PartyMembership, PartyMembership.party_id == Party.id)
        .where(Party.id == party_id, PartyMembership.user_id == user.id)
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party not found"
        )
    party, membership = row
    if require_active and not party.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This party has been dissolved",
        )
    return party, membership


def _require_owner(membership: PartyMembership) -> None:
    if membership.role != PartyRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the party owner can do that",
        )


def _member_count(db: Session, party_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(PartyMembership).where(
            PartyMembership.party_id == party_id
        )
    ).scalar_one()


def _party_xp_totals(db: Session, party_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(
            PartyQuestCompletion.user_id,
            func.coalesce(func.sum(PartyQuestCompletion.xp_awarded), 0),
        )
        .join(PartyQuest, PartyQuest.id == PartyQuestCompletion.party_quest_id)
        .where(PartyQuest.party_id == party_id)
        .group_by(PartyQuestCompletion.user_id)
    ).all()
    return {user_id: int(total) for user_id, total in rows}


def _derive_rank(progress: LevelProgress, tz_name: str, now: dt.datetime) -> str:
    """Rank as the Stat Panel would show it, judged in the MEMBER's timezone.

    The cached rank column is not read here: nothing updates it while a user is
    away, so a lapsed member would otherwise appear on the leaderboard holding
    a rank their streak no longer supports.

    The member's own local date is what decides whether their streak is still
    alive. Using the server's date instead shifts every member's streak
    boundary onto the server's midnight: at 02:00 UTC a Los Angeles member who
    last completed "yesterday" their time reads as two days idle, and a live
    40-day streak is reported as rank B when they in fact hold S.
    """
    today = local_date(now, tz_name)
    streak = leveling.effective_streak(
        progress.current_streak, progress.last_completed_on, today
    )
    return leveling.rank_for(progress.current_level, streak).value


def _serialize_party(
    db: Session, party: Party, membership: PartyMembership
) -> PartyOut:
    totals = _party_xp_totals(db, party.id)
    return PartyOut(
        id=party.id,
        name=party.name,
        owner_id=party.owner_id,
        max_members=party.max_members,
        member_count=_member_count(db, party.id),
        is_active=party.is_active,
        created_at=party.created_at,
        my_role=membership.role.value,
        # The code is a capability: only ever returned to a member.
        invite_code=party.invite_code,
        total_party_xp=sum(totals.values()),
    )


# ---------------------------------------------------------------------------
# Party lifecycle. Literal paths first - FastAPI matches in declaration order,
# so /parties/join declared after /parties/{party_id} would be parsed as a UUID.
# ---------------------------------------------------------------------------


@router.post("/join", response_model=PartyOut)
def join_party(
    payload: JoinRequest, current_user: CurrentUser, db: DbSession
) -> PartyOut:
    """Join by invite code.

    The party row is locked FOR UPDATE before the headcount is read: checking
    the cap without the lock is a race, and two simultaneous joins into a
    9-of-10 party would both see room and both insert.
    """
    code = normalize_invite_code(payload.invite_code)

    party = db.execute(
        select(Party).where(Party.invite_code == code).with_for_update()
    ).scalar_one_or_none()

    # Same message whether the code is malformed, unknown, or belongs to a
    # dissolved party - a distinct one would let someone probe for live codes.
    if party is None or not party.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite code"
        )

    existing = db.get(PartyMembership, (party.id, current_user.id))
    if existing is not None:
        # Idempotent rather than an error: re-using a link you already accepted
        # should land you in the party, not on a failure page.
        return _serialize_party(db, party, existing)

    if _member_count(db, party.id) >= party.max_members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This party is full ({party.max_members} members)",
        )

    membership = PartyMembership(
        party_id=party.id,
        user_id=current_user.id,
        role=PartyRole.MEMBER,
        joined_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Could not join this party"
        ) from None

    db.refresh(membership)
    logger.info("user %s joined party %s", current_user.id, party.id)
    return _serialize_party(db, party, membership)


@router.get("", response_model=list[PartyOut])
def list_parties(
    current_user: CurrentUser,
    db: DbSession,
    include_dissolved: bool = Query(default=False),
) -> list[PartyOut]:
    """Every party the caller belongs to."""
    query = (
        select(Party, PartyMembership)
        .join(PartyMembership, PartyMembership.party_id == Party.id)
        .where(PartyMembership.user_id == current_user.id)
    )
    if not include_dissolved:
        query = query.where(Party.is_active.is_(True))

    rows = db.execute(query.order_by(Party.created_at.desc())).all()
    return [_serialize_party(db, party, membership) for party, membership in rows]


@router.post("", response_model=PartyOut, status_code=status.HTTP_201_CREATED)
def create_party(
    payload: PartyCreate, current_user: CurrentUser, db: DbSession
) -> PartyOut:
    """Create a party and join it as owner, in one transaction.

    A party with no members would be unreachable - nobody could see it or use
    its invite code - so the owner's membership is not a separate step.
    """
    party: Party | None = None
    for _ in range(MAX_CODE_ATTEMPTS):
        candidate = Party(
            name=payload.name.strip(),
            invite_code=generate_invite_code(),
            owner_id=current_user.id,
            max_members=payload.max_members,
            is_active=True,
        )
        db.add(candidate)
        try:
            db.flush()
        except IntegrityError:
            # UNIQUE(invite_code) collision. Astronomically rare, but the
            # column enforces it, so retry rather than 500.
            db.rollback()
            continue
        party = candidate
        break

    if party is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not allocate an invite code; please retry",
        )

    membership = PartyMembership(
        party_id=party.id,
        user_id=current_user.id,
        role=PartyRole.OWNER,
        joined_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(membership)
    db.commit()
    db.refresh(party)
    db.refresh(membership)
    logger.info("user %s created party %s", current_user.id, party.id)
    return _serialize_party(db, party, membership)


@router.get("/{party_id}", response_model=PartyOut)
def get_party(
    party_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> PartyOut:
    party, membership = _membership_or_404(db, party_id, current_user, require_active=False)
    return _serialize_party(db, party, membership)


@router.patch("/{party_id}", response_model=PartyOut)
def update_party(
    party_id: uuid.UUID,
    payload: PartyUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> PartyOut:
    party, membership = _membership_or_404(db, party_id, current_user)
    _require_owner(membership)

    changes = payload.model_dump(exclude_unset=True)
    if changes.get("name"):
        party.name = changes["name"].strip()

    db.commit()
    db.refresh(party)
    return _serialize_party(db, party, membership)


@router.post("/{party_id}/rotate-invite", response_model=PartyOut)
def rotate_invite(
    party_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> PartyOut:
    """Issue a fresh invite code, invalidating the old one.

    The only way to revoke a leaked link: the code IS the capability, so
    rotating it is what stops further joins.
    """
    party, membership = _membership_or_404(db, party_id, current_user)
    _require_owner(membership)

    for _ in range(MAX_CODE_ATTEMPTS):
        party.invite_code = generate_invite_code()
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        db.commit()
        db.refresh(party)
        return _serialize_party(db, party, membership)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate an invite code; please retry",
    )


@router.delete("/{party_id}", status_code=status.HTTP_204_NO_CONTENT)
def dissolve_party(
    party_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """Dissolve a party (owner only).

    Soft: is_active=false, never a row delete. Members keep the XP they earned
    and the completion history stays reconstructible - deleting would cascade
    party_quests and their completions away, silently rewriting the record of
    work people actually did.
    """
    party, membership = _membership_or_404(db, party_id, current_user)
    _require_owner(membership)

    party.is_active = False
    db.commit()
    leaderboard.drop(party.id)
    logger.info("party %s dissolved by %s", party.id, current_user.id)


@router.post("/{party_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_party(
    party_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> None:
    """Leave a party.

    When the OWNER leaves, the party is handed to the longest-serving remaining
    member rather than orphaned - an ownerless party could never be renamed,
    have its invite rotated, or be dissolved. If nobody remains, the party is
    dissolved instead of being left empty and unreachable.
    """
    party, membership = _membership_or_404(db, party_id, current_user)

    if membership.role == PartyRole.OWNER:
        successor = db.execute(
            select(PartyMembership)
            .where(
                PartyMembership.party_id == party.id,
                PartyMembership.user_id != current_user.id,
            )
            .order_by(PartyMembership.joined_at.asc())
            .limit(1)
        ).scalar_one_or_none()

        if successor is None:
            party.is_active = False
            db.delete(membership)
            db.commit()
            leaderboard.drop(party.id)
            logger.info("party %s dissolved - last member left", party.id)
            return

        successor.role = PartyRole.OWNER
        party.owner_id = successor.user_id
        logger.info("party %s ownership -> %s", party.id, successor.user_id)

    db.delete(membership)
    db.commit()


# ---------------------------------------------------------------------------
# Members and leaderboard
# ---------------------------------------------------------------------------


@router.get("/{party_id}/members", response_model=list[MemberOut])
def list_members(
    party_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[MemberOut]:
    party, _ = _membership_or_404(db, party_id, current_user, require_active=False)
    totals = _party_xp_totals(db, party.id)
    now = dt.datetime.now(dt.timezone.utc)

    rows = db.execute(
        select(PartyMembership, User, LevelProgress)
        .join(User, User.id == PartyMembership.user_id)
        .join(LevelProgress, LevelProgress.user_id == User.id)
        .where(PartyMembership.party_id == party.id)
        .order_by(PartyMembership.joined_at.asc())
    ).all()

    return [
        MemberOut(
            user_id=user.id,
            display_name=user.display_name,
            role=membership.role.value,
            joined_at=membership.joined_at,
            level=progress.current_level,
            rank=_derive_rank(progress, user.timezone, now),
            party_xp=totals.get(user.id, 0),
        )
        for membership, user, progress in rows
    ]


@router.get("/{party_id}/leaderboard", response_model=LeaderboardOut)
def party_leaderboard(
    party_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> LeaderboardOut:
    """Ranked party members by XP contributed to this party.

    Served from the Redis sorted set, which falls back to Postgres and rebuilds
    on a miss - so a cache flush costs a rebuild, never data.
    """
    party, _ = _membership_or_404(db, party_id, current_user, require_active=False)

    ranked = leaderboard.top(db, party.id, limit=limit)

    # Names, levels and ranks still come from Postgres: caching them would mean
    # a renamed or levelled-up member showing stale details until the TTL.
    rows = db.execute(
        select(User, LevelProgress)
        .join(LevelProgress, LevelProgress.user_id == User.id)
        .join(PartyMembership, PartyMembership.user_id == User.id)
        .where(PartyMembership.party_id == party.id)
    ).all()
    profiles = {str(user.id): (user, progress) for user, progress in rows}
    now = dt.datetime.now(dt.timezone.utc)

    entries: list[LeaderboardEntry] = []
    for position, (user_id, xp) in enumerate(ranked, start=1):
        profile = profiles.get(user_id)
        if profile is None:
            # Scored while a member, since left. Their contribution stays in
            # the party total but they are not listed as a current member.
            continue
        user, progress = profile
        entries.append(
            LeaderboardEntry(
                position=position,
                user_id=user.id,
                display_name=user.display_name,
                party_xp=xp,
                level=progress.current_level,
                rank=_derive_rank(progress, user.timezone, now),
                is_me=(user.id == current_user.id),
            )
        )

    # Members who have contributed nothing yet are absent from the sorted set
    # but should still appear, so the board shows the whole party.
    listed = {str(e.user_id) for e in entries}
    for user_id, (user, progress) in profiles.items():
        if user_id in listed:
            continue
        entries.append(
            LeaderboardEntry(
                position=len(entries) + 1,
                user_id=user.id,
                display_name=user.display_name,
                party_xp=0,
                level=progress.current_level,
                rank=_derive_rank(progress, user.timezone, now),
                is_me=(user.id == current_user.id),
            )
        )

    return LeaderboardOut(
        party_id=party.id,
        # The authoritative total, NOT a sum over the listed rows. Those skip
        # departed contributors and are truncated by `limit`, so summing them
        # made GET /parties/{id} and this endpoint disagree about the same
        # party. Work genuinely done for the party stays in its total, which is
        # consistent with dissolution and quest removal both being soft.
        total_party_xp=sum(_party_xp_totals(db, party.id).values()),
        entries=entries[:limit],
    )


# ---------------------------------------------------------------------------
# Shared quest board
# ---------------------------------------------------------------------------


def _serialize_party_quests(
    db: Session, quests: list[PartyQuest], user: User, now: dt.datetime
) -> list[PartyQuestOut]:
    """Attach per-caller and party-wide completion state.

    Two grouped queries for the whole board rather than a lookup per quest, so
    the board's cost does not grow with the number of shared quests.
    """
    if not quests:
        return []

    keys = {q.id: period_key(q.recurrence, now, user.timezone) for q in quests}
    pairs = list(keys.items())

    mine = {
        (row.party_quest_id, row.period_key)
        for row in db.execute(
            select(
                PartyQuestCompletion.party_quest_id, PartyQuestCompletion.period_key
            ).where(
                PartyQuestCompletion.user_id == user.id,
                tuple_(
                    PartyQuestCompletion.party_quest_id,
                    PartyQuestCompletion.period_key,
                ).in_(pairs),
            )
        ).all()
    }

    counts = {
        (row[0], row[1]): row[2]
        for row in db.execute(
            select(
                PartyQuestCompletion.party_quest_id,
                PartyQuestCompletion.period_key,
                func.count(PartyQuestCompletion.id),
            )
            .where(PartyQuestCompletion.party_quest_id.in_(list(keys)))
            .group_by(
                PartyQuestCompletion.party_quest_id, PartyQuestCompletion.period_key
            )
        ).all()
    }

    return [
        PartyQuestOut(
            id=q.id,
            party_id=q.party_id,
            title=q.title,
            description=q.description,
            xp_reward=q.xp_reward,
            points_reward=q.points_reward,
            recurrence=q.recurrence,
            is_active=q.is_active,
            due_at=q.due_at,
            created_at=q.created_at,
            current_period_key=keys[q.id],
            completed_in_current_period=(q.id, keys[q.id]) in mine,
            completed_by_count=counts.get((q.id, keys[q.id]), 0),
        )
        for q in quests
    ]


@router.get("/{party_id}/quests", response_model=list[PartyQuestOut])
def list_party_quests(
    party_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    include_inactive: bool = Query(default=False),
) -> list[PartyQuestOut]:
    party, _ = _membership_or_404(db, party_id, current_user, require_active=False)

    query = select(PartyQuest).where(PartyQuest.party_id == party.id)
    if not include_inactive:
        query = query.where(PartyQuest.is_active.is_(True))

    quests = list(db.execute(query.order_by(PartyQuest.created_at.desc())).scalars())
    return _serialize_party_quests(
        db, quests, current_user, dt.datetime.now(dt.timezone.utc)
    )


@router.post(
    "/{party_id}/quests",
    response_model=PartyQuestOut,
    status_code=status.HTTP_201_CREATED,
)
def create_party_quest(
    party_id: uuid.UUID,
    payload: PartyQuestCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> PartyQuestOut:
    """Any member may add to the shared board.

    Deliberately not owner-only: a shared quest board that only one person can
    write to is a to-do list handed down, not a party.
    """
    party, _ = _membership_or_404(db, party_id, current_user)

    quest = PartyQuest(
        party_id=party.id,
        created_by=current_user.id,
        title=payload.title.strip(),
        description=payload.description,
        xp_reward=payload.xp_reward,
        points_reward=payload.points_reward,
        recurrence=payload.recurrence.value,
        is_active=True,
        due_at=payload.due_at,
    )
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return _serialize_party_quests(
        db, [quest], current_user, dt.datetime.now(dt.timezone.utc)
    )[0]


@router.patch("/{party_id}/quests/{quest_id}", response_model=PartyQuestOut)
def update_party_quest(
    party_id: uuid.UUID,
    quest_id: uuid.UUID,
    payload: PartyQuestUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> PartyQuestOut:
    party, membership = _membership_or_404(db, party_id, current_user)
    quest = db.execute(
        select(PartyQuest).where(
            PartyQuest.id == quest_id, PartyQuest.party_id == party.id
        )
    ).scalar_one_or_none()
    if quest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party quest not found"
        )

    # The author or the owner. Otherwise any member could reprice a quest other
    # people have already been completing.
    if quest.created_by != current_user.id and membership.role != PartyRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the quest's author or the party owner can edit it",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "recurrence" and value is not None:
            quest.recurrence = value.value
        elif field == "title" and value is not None:
            quest.title = value.strip()
        else:
            setattr(quest, field, value)

    db.commit()
    db.refresh(quest)
    return _serialize_party_quests(
        db, [quest], current_user, dt.datetime.now(dt.timezone.utc)
    )[0]


@router.delete(
    "/{party_id}/quests/{quest_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_party_quest(
    party_id: uuid.UUID,
    quest_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Deactivate a shared quest.

    Soft, like dissolving a party: a hard delete would cascade away the
    completion rows that back every member's contributed XP, silently changing
    the leaderboard.
    """
    party, membership = _membership_or_404(db, party_id, current_user)
    quest = db.execute(
        select(PartyQuest).where(
            PartyQuest.id == quest_id, PartyQuest.party_id == party.id
        )
    ).scalar_one_or_none()
    if quest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party quest not found"
        )
    if quest.created_by != current_user.id and membership.role != PartyRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the quest's author or the party owner can remove it",
        )

    quest.is_active = False
    db.commit()


@router.post(
    "/{party_id}/quests/{quest_id}/complete",
    response_model=PartyQuestCompleteResponse,
)
def complete_party_quest(
    party_id: uuid.UUID,
    quest_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> PartyQuestCompleteResponse:
    """Complete a shared quest for the current period.

    Same transaction shape as a personal completion, and for the same reasons:
    lock level_progress FOR UPDATE first (consistent lock order across every
    writer, so no deadlock), then let
    UNIQUE(party_quest_id, user_id, period_key) - not a Python pre-check - be
    what actually stops double-awarding.

    The award lands in BOTH places: the member's personal total_xp and their
    party contribution. Because a non-member cannot reach this endpoint, party
    XP counts only what was earned while a member, with no extra bookkeeping.
    """
    party, _ = _membership_or_404(db, party_id, current_user)

    quest = db.execute(
        select(PartyQuest).where(
            PartyQuest.id == quest_id, PartyQuest.party_id == party.id
        )
    ).scalar_one_or_none()
    if quest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party quest not found"
        )
    if not quest.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot complete a removed quest",
        )

    now = dt.datetime.now(dt.timezone.utc)
    key = period_key(quest.recurrence, now, current_user.timezone)

    progress = lock_progress(db, current_user.id)

    completion = PartyQuestCompletion(
        party_quest_id=quest.id,
        user_id=current_user.id,
        period_key=key,
        completed_at=now,
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
            detail=f"You already completed this party quest for this period ({key})",
        ) from None

    delta = apply_completion(
        progress,
        xp=quest.xp_reward,
        points=quest.points_reward,
        completed_at=now,
        tz_name=current_user.timezone,
    )
    db.commit()

    # Cache update AFTER the commit: crediting Redis for a transaction that
    # then rolled back would inflate the leaderboard with XP nobody earned.
    leaderboard.add_xp(party.id, current_user.id, quest.xp_reward)

    totals = _party_xp_totals(db, party.id)
    return PartyQuestCompleteResponse(
        xp_awarded=delta.xp_awarded,
        points_awarded=delta.points_awarded,
        total_xp=delta.total_xp,
        level_before=delta.level_before,
        level_after=delta.level_after,
        rank_before=delta.rank_before,
        rank_after=delta.rank_after,
        current_streak=delta.current_streak,
        longest_streak=delta.longest_streak,
        leveled_up=delta.leveled_up,
        ranked_up=delta.ranked_up,
        party_xp_contributed=totals.get(current_user.id, 0),
        total_party_xp=sum(totals.values()),
    )
