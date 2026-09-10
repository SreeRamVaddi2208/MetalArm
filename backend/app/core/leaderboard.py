"""Redis-backed party leaderboard.

Postgres remains the SOURCE OF TRUTH: every score here is derivable from
party_quest_completions. Redis holds a sorted set purely so ranking a party is
one O(log N) read instead of a GROUP BY per request.

That relationship is the important part. Redis is treated as a cache that may
be empty, stale, or entirely gone:

  - Every read falls back to Postgres and rebuilds the set on a miss, so a
    `FLUSHALL` costs a rebuild, never data.
  - Every Redis failure is caught and degrades to the Postgres path. A cache
    outage must not take the feature down - it should only make it slower.

Scores are cumulative party XP per member, which by construction counts only
what was earned WHILE a member: a party quest cannot be completed by someone
who is not in the party.
"""

import logging
import uuid

import redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.redis_client import get_redis
from app.models.party import PartyQuest, PartyQuestCompletion

logger = logging.getLogger("levelforge.leaderboard")

# Bumped if the value format ever changes, so old entries cannot be read as new.
KEY_VERSION = "v1"
# Rebuilt cheaply from Postgres, so a bounded TTL costs little and stops
# abandoned parties pinning memory forever.
TTL_SECONDS = 6 * 60 * 60


def key_for(party_id: uuid.UUID) -> str:
    return f"levelforge:{KEY_VERSION}:party:{party_id}:xp"


def compute_from_db(db: Session, party_id: uuid.UUID) -> dict[str, int]:
    """Authoritative per-member party XP, straight from Postgres."""
    rows = db.execute(
        select(
            PartyQuestCompletion.user_id,
            func.coalesce(func.sum(PartyQuestCompletion.xp_awarded), 0),
        )
        .join(PartyQuest, PartyQuest.id == PartyQuestCompletion.party_quest_id)
        .where(PartyQuest.party_id == party_id)
        .group_by(PartyQuestCompletion.user_id)
    ).all()
    return {str(user_id): int(total) for user_id, total in rows}


def rebuild(db: Session, party_id: uuid.UUID) -> dict[str, int]:
    """Recompute from Postgres and repopulate Redis. Safe to call any time."""
    scores = compute_from_db(db, party_id)
    key = key_for(party_id)
    try:
        client = get_redis()
        pipe = client.pipeline()
        pipe.delete(key)
        if scores:
            pipe.zadd(key, scores)
            pipe.expire(key, TTL_SECONDS)
        pipe.execute()
    except (redis.RedisError, OSError) as exc:
        # Losing the cache write is survivable; the caller already has the
        # authoritative numbers.
        logger.warning("Leaderboard rebuild could not write to Redis: %s", exc)
    return scores


def add_xp(party_id: uuid.UUID, user_id: uuid.UUID, xp: int) -> None:
    """Incrementally credit a completion.

    ZINCRBY only, never a recompute: the write path stays O(log N) regardless
    of party history. If Redis is down the increment is simply lost, and the
    next read's miss-and-rebuild restores the correct value from Postgres.
    """
    if xp <= 0:
        return
    key = key_for(party_id)
    try:
        client = get_redis()
        pipe = client.pipeline()
        pipe.zincrby(key, xp, str(user_id))
        pipe.expire(key, TTL_SECONDS)
        pipe.execute()
    except (redis.RedisError, OSError) as exc:
        logger.warning("Leaderboard increment skipped (Redis unavailable): %s", exc)


def top(db: Session, party_id: uuid.UUID, limit: int = 50) -> list[tuple[str, int]]:
    """Ranked (user_id, xp) descending.

    Reads Redis first, and on a miss or a failure rebuilds from Postgres, so
    the caller always gets correct data whatever state the cache is in.
    """
    key = key_for(party_id)
    try:
        client = get_redis()
        raw = client.zrevrange(key, 0, limit - 1, withscores=True)
        if raw:
            return [(member, int(score)) for member, score in raw]
        # Empty could mean "no completions yet" or "cache evicted". Only
        # Postgres can tell the difference.
    except (redis.RedisError, OSError) as exc:
        logger.warning("Leaderboard read fell back to Postgres: %s", exc)

    scores = rebuild(db, party_id)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ranked[:limit]


def drop(party_id: uuid.UUID) -> None:
    """Forget a party's cached set, e.g. once it is dissolved."""
    try:
        get_redis().delete(key_for(party_id))
    except (redis.RedisError, OSError) as exc:
        logger.warning("Leaderboard key not dropped (Redis unavailable): %s", exc)
