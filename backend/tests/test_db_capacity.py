"""The connection pool, its timeouts, and the threadpool that feeds it.

None of this was exercised before: the test suite builds its own engine, so the
application engine's configuration was never asserted anywhere and could drift
silently. What matters here is not the exact numbers - they are meant to be
tuned per deployment - but that the guard rails exist at all and that the
arithmetic tying threads to connections still holds.

A stock Postgres has no statement_timeout and no
idle_in_transaction_session_timeout, so if these flags stop being sent, one
runaway aggregate can hold a connection until someone notices and one abandoned
transaction can block VACUUM indefinitely.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.redis_client import get_redis
from app.db.session import engine


def _settings(**overrides: object) -> Settings:
    """A Settings instance with the required secrets filled in.

    Built directly rather than through get_settings() so a test can vary the
    pool numbers without touching the process-wide lru_cache, which poisons
    every later test in the run if cleared.
    """
    base: dict[str, object] = {
        "postgres_password": "test-password",
        "jwt_secret_key": "test-secret-at-least-thirty-two-bytes-long",
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


# --- The server-side timeouts -------------------------------------------------


def test_every_timeout_is_sent_to_the_server():
    options = _settings().postgres_options
    assert "statement_timeout=" in options
    assert "lock_timeout=" in options
    assert "idle_in_transaction_session_timeout=" in options


def test_the_timeouts_are_shaped_as_libpq_flags():
    """libpq wants `-c key=value`; anything else is silently ignored."""
    options = _settings(
        db_statement_timeout_ms=15_000,
        db_lock_timeout_ms=3_000,
        db_idle_in_transaction_timeout_ms=30_000,
    ).postgres_options
    assert options == (
        "-c statement_timeout=15000 -c lock_timeout=3000 "
        "-c idle_in_transaction_session_timeout=30000"
    )


def test_a_zero_leaves_that_timeout_to_the_server():
    """0 has to mean "don't send it", not "send 0" - which would DISABLE it.

    A batch script raising DB_STATEMENT_TIMEOUT_MS=0 wants the server default,
    and sending `-c statement_timeout=0` happens to mean the same thing here,
    but only by luck. Leaving it out says what is meant.
    """
    options = _settings(db_statement_timeout_ms=0).postgres_options
    assert "statement_timeout" not in options
    assert "lock_timeout=" in options


def test_lock_timeout_is_shorter_than_statement_timeout():
    """A statement blocked on a lock should give up before the statement does,
    so the error names the real problem: contention, not slowness."""
    settings = _settings()
    assert settings.db_lock_timeout_ms < settings.db_statement_timeout_ms


# --- Threads against connections ----------------------------------------------


def test_request_threads_stay_under_the_pool_ceiling():
    """Every route is a sync def holding a connection for its whole life.

    More threads than connections means threads blocked in pool.connect() until
    pool_timeout, holding nothing and achieving nothing. AnyIO's own default is
    40, which is why this has to be set rather than left alone.
    """
    settings = _settings(db_pool_size=10, db_max_overflow=10)
    ceiling = settings.db_pool_size + settings.db_max_overflow
    assert settings.request_thread_limit < ceiling


def test_connections_are_reserved_for_the_health_check():
    """/health takes a connection without going through get_db.

    If a fully busy app cannot answer it, Docker calls the container unhealthy
    and restarts it - a slow minute becomes an outage.
    """
    settings = _settings(db_pool_size=10, db_max_overflow=10)
    spare = (settings.db_pool_size + settings.db_max_overflow) - settings.request_thread_limit
    assert spare >= 1


@pytest.mark.parametrize("pool_size,overflow", [(1, 0), (1, 1), (2, 0)])
def test_a_tiny_pool_still_allows_one_thread(pool_size: int, overflow: int):
    """The reserve must never drive the limit to zero, which would wedge the
    app: no thread could ever start and every request would hang."""
    settings = _settings(db_pool_size=pool_size, db_max_overflow=overflow)
    assert settings.request_thread_limit >= 1


# --- The engine actually built at import time ---------------------------------


def test_the_application_engine_pool_is_configured():
    """Asserted against the real engine object, not the settings that built it:
    a create_engine call that forgot to pass one of these would still pass every
    test above."""
    assert engine.pool._pre_ping is True
    assert engine.pool.timeout() < 30, "SQLAlchemy's 30s default is too long to be useful"
    assert engine.pool._recycle > 0, "connections would otherwise live forever"


def test_the_timeouts_are_live_on_a_real_connection():
    """The one test that proves it rather than inferring it.

    Everything above checks the string we intend to send. This opens the
    application engine's own connection and asks the server what it actually
    got, which is the only way to catch connect_args being dropped, misspelt or
    overridden. Read-only: SHOW touches no data.
    """
    settings = _settings()
    with engine.connect() as conn:
        live = {
            name: conn.execute(text(f"SHOW {name}")).scalar()
            for name in ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout")
        }
        application = conn.execute(text("SHOW application_name")).scalar()

    # Postgres reports these in its own units ("15s", "3s", "30s").
    assert live["statement_timeout"] == f"{settings.db_statement_timeout_ms // 1000}s"
    assert live["lock_timeout"] == f"{settings.db_lock_timeout_ms // 1000}s"
    assert live["idle_in_transaction_session_timeout"] == (
        f"{settings.db_idle_in_transaction_timeout_ms // 1000}s"
    )
    assert application == "metalarm-api"


def test_a_statement_over_the_limit_is_actually_killed():
    """The rail exists to stop a runaway query, so make one and watch it die.

    Without this, a statement_timeout that is set but ineffective - sent to the
    wrong place, or overridden per-role on a managed server - looks identical to
    a working one.
    """
    with engine.connect() as conn:
        conn.execute(text("SET statement_timeout = 250"))
        with pytest.raises(OperationalError) as caught:
            conn.execute(text("SELECT pg_sleep(2)"))
    assert "statement timeout" in str(caught.value).lower()


# --- Redis memory ceiling -----------------------------------------------------


def test_redis_has_a_memory_ceiling_and_will_evict():
    """Unbounded with noeviction is the Redis default, and it fails badly here.

    Redis holds the rate-limit buckets and the party XP cache. With no maxmemory
    it grows until the host OOMs; with noeviction it then refuses writes, at
    which point rate limiting fails open (app/core/rate_limit.py swallows the
    error) and every leaderboard read falls through to a Postgres GROUP BY - the
    load lands hardest exactly when the system is already struggling.
    """
    config = get_redis().config_get("maxmemory", "maxmemory-policy")

    assert int(config["maxmemory"]) > 0, "no memory ceiling: Redis will grow until the host OOMs"
    assert config["maxmemory-policy"] != "noeviction", (
        "at the ceiling Redis would refuse writes instead of evicting"
    )


def test_redis_only_evicts_keys_that_have_a_ttl():
    """volatile-lru, not allkeys-lru.

    Every key this app writes sets a TTL, so there is always something to evict.
    Choosing the volatile policy means anything added LATER without a TTL is
    protected rather than silently dropped - the safer default, given that a
    policy cannot differ per key on a single instance.
    """
    policy = get_redis().config_get("maxmemory-policy")["maxmemory-policy"]
    assert policy.startswith("volatile-"), policy
