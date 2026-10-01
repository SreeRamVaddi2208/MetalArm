"""Fixed-window rate limiting for the auth endpoints, backed by Redis.

Without it, login is an unlimited password-guessing oracle and signup an
unlimited account factory. Counters live in Redis so every backend worker (and
every replica) shares them.

Fails OPEN: if Redis is unreachable the request proceeds and /health already
reports Redis as down. Locking every user out of login because the cache
blipped would be worse than a few minutes without a limit.

Behind the production proxy, request.client.host is the real client address
only because uvicorn runs with --proxy-headers (see deploy/docker-compose.prod.yml).
"""

import logging
from dataclasses import dataclass

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.db.redis_client import get_redis

logger = logging.getLogger("metalarm.ratelimit")


@dataclass(frozen=True)
class Limit:
    scope: str
    max_requests: int
    window_seconds: int


# Per client address.
LOGIN_PER_IP = Limit("login-ip", 30, 15 * 60)
SIGNUP_PER_IP = Limit("signup-ip", 5, 60 * 60)
REFRESH_PER_IP = Limit("refresh-ip", 60, 15 * 60)
# The marketing site's waitlist. Looser than signup because joining is
# harmless, tight enough that the table cannot be filled from one address.
WAITLIST_PER_IP = Limit("waitlist-ip", 10, 60 * 60)
# Per user: an import rebuilds every touched record, so it is not free.
IMPORT_PER_USER = Limit("import-user", 10, 60 * 60)
# Per account, whatever address the guesses come from.
LOGIN_PER_EMAIL = Limit("login-email", 10, 15 * 60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(limit: Limit, key: str) -> None:
    """Count one attempt against `limit` for `key`; raise 429 once over it."""
    if not get_settings().rate_limit_enabled:
        return

    bucket = f"ratelimit:{limit.scope}:{key}"
    try:
        client = get_redis()
        pipe = client.pipeline()
        pipe.incr(bucket)
        # NX: the window starts at the first attempt and is not extended by
        # later ones, so a blocked client is let back in on schedule.
        pipe.expire(bucket, limit.window_seconds, nx=True)
        pipe.ttl(bucket)
        count, _, ttl = pipe.execute()
    except (redis.RedisError, OSError) as exc:
        logger.warning("Rate limiter unavailable, allowing request: %s", exc)
        return

    if count > limit.max_requests:
        retry_after = ttl if isinstance(ttl, int) and ttl > 0 else limit.window_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts - try again later",
            headers={"Retry-After": str(retry_after)},
        )
