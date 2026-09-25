"""The activity feed: a read model over things that already happened.

Nothing here is a source of truth. Every row points back at the record that
caused it - a PersonalRecord, a WorkoutSession, a Duel, a QuestCompletion -
and the feed could be rebuilt from those if it were ever lost. That is the
whole reason it is safe for `record()` to swallow a duplicate: the facts live
elsewhere, so a feed row that fails to write costs a line in a list, not data.

Who sees what: yourself, and whoever shares a party with you AT THE TIME.
`party_id` is stamped in at write time rather than joined at read time, so
leaving a party neither erases what you did while you were in it nor keeps
showing your new PRs to people you have left.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.duel import ActivityEvent, ActivityType
from app.models.party import PartyMembership


def parties_of(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(select(PartyMembership.party_id).where(PartyMembership.user_id == user_id))
    )


def record(
    db: Session,
    *,
    user_id: uuid.UUID,
    event_type: ActivityType,
    headline: str,
    source_id: uuid.UUID | None = None,
    at: dt.datetime | None = None,
) -> list[ActivityEvent]:
    """Fan one event out to the user's own feed and each of their parties.

    Uses a SAVEPOINT per row, because the UNIQUE that makes this idempotent
    (a retried finish, a replayed PR) would otherwise poison the caller's
    transaction on conflict - and the caller is usually in the middle of
    awarding points, which must not be lost to a duplicate feed row.
    """
    moment = at or dt.datetime.now(dt.timezone.utc)
    written: list[ActivityEvent] = []
    targets: list[uuid.UUID | None] = [None, *parties_of(db, user_id)]
    for party_id in targets:
        event = ActivityEvent(
            user_id=user_id,
            party_id=party_id,
            event_type=event_type.value,
            source_id=source_id,
            headline=headline[:140],
            created_at=moment,
        )
        try:
            with db.begin_nested():
                db.add(event)
                db.flush()
        except IntegrityError:
            continue  # already recorded; the feed is not the source of truth
        written.append(event)
    return written


def feed(
    db: Session,
    user_id: uuid.UUID,
    *,
    party_id: uuid.UUID | None = None,
    limit: int = 30,
    before: dt.datetime | None = None,
) -> list[ActivityEvent]:
    """Newest first: the user's own events plus their parties'.

    `party_id` narrows it to one party, and is checked against membership by
    the caller - this function trusts what it is given.
    """
    query = select(ActivityEvent)
    if party_id is not None:
        query = query.where(ActivityEvent.party_id == party_id)
    else:
        mine = parties_of(db, user_id)
        query = query.where(
            (ActivityEvent.user_id == user_id) | (ActivityEvent.party_id.in_(mine) if mine else False)
        )
        # A user's own rows exist twice when they are in a party (one personal,
        # one per party); prefer the personal copy so the feed does not repeat.
        query = query.where(
            (ActivityEvent.user_id != user_id) | (ActivityEvent.party_id.is_(None))
        )
    if before is not None:
        query = query.where(ActivityEvent.created_at < before)
    return list(
        db.scalars(query.order_by(ActivityEvent.created_at.desc(), ActivityEvent.id).limit(limit))
    )
