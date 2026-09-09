"""Redis client factory.

Used for the party leaderboard in Sprint 5; wired up now only so /health can
report a genuine connection state from day one.
"""

from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
