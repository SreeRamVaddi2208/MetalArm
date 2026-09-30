"""Application settings.

Every value is sourced from the environment. There are no hardcoded
credentials and no defaults for secrets - if JWT_SECRET_KEY or the Postgres
password is missing, the app fails loudly at import time rather than starting
in an insecure state.
"""

from functools import lru_cache
from typing import ClassVar
from urllib.parse import quote

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Postgres (no default password: must come from the environment) ---
    postgres_user: str = "levelforge"
    postgres_password: str
    postgres_db: str = "levelforge"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # --- Database connection pool ---
    # The ceiling per worker PROCESS is db_pool_size + db_max_overflow. What
    # Postgres sees is that times the uvicorn worker count times the container
    # count, and it has to stay under the server's max_connections (100 on a
    # stock server) with room left over for migrations, the backup job and a
    # psql session. 2 workers x 20 = 40 leaves plenty; 8 workers x 20 would not.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # Fail fast rather than queue. SQLAlchemy's default is 30 seconds - long
    # enough that the client has usually given up and retried, which puts more
    # load on a pool that is already saturated.
    db_pool_timeout: int = 10
    # Without this a pooled connection lives forever, and a pooler or firewall
    # that drops idle connections eventually hands out a dead one. pool_pre_ping
    # catches that at the cost of a round trip per checkout; recycling makes it
    # rare rather than routine.
    db_pool_recycle_seconds: int = 1800

    # --- Server-side timeouts, applied to every connection this app opens ---
    # A stock Postgres has NONE of these: statement_timeout is 0, so one
    # runaway aggregate holds a connection until someone notices, and
    # idle_in_transaction_session_timeout is 0, so one abandoned transaction
    # blocks VACUUM indefinitely and the table bloats behind it.
    #
    # Set any of them to 0 to fall back to the server default (no limit). A
    # batch script that legitimately runs longer than statement_timeout should
    # raise DB_STATEMENT_TIMEOUT_MS for its own run rather than the app's.
    db_statement_timeout_ms: int = 15_000
    db_lock_timeout_ms: int = 3_000
    db_idle_in_transaction_timeout_ms: int = 30_000

    # --- Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379
    # Redis warns loudly at startup that it is unauthenticated and "will accept
    # connections from any IP address on any network interface". Binding the
    # published port to loopback already blocks outside access; requiring a
    # password also stops anything else on this machine from reading the
    # leaderboard cache. Empty means no auth, for a bare local redis-server.
    redis_password: str = ""

    # --- Auth (no default secret: must come from the environment) ---
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Refresh tokens keep the mobile app signed in without storing the password.
    refresh_token_expire_days: int = 30
    # Redis-backed limits on login/signup/refresh (app/core/rate_limit.py).
    # Switched off only by the test suite, which logs in hundreds of times.
    rate_limit_enabled: bool = True

    # --- App ---
    # "production" hides /docs, /redoc and /openapi.json.
    environment: str = "development"
    log_level: str = "info"
    cors_origins: str = "http://localhost:3000"

    # The example file ships JWT_SECRET_KEY=CHANGE_ME_GENERATE_A_RANDOM_48_BYTE_SECRET.
    # Deployed unchanged, every token would be signed with a string published in
    # this repository - anyone could mint one for any account. A short secret is
    # refused for the same reason: HS256 is only as strong as its key. Refused at
    # startup, where it is one clear error, rather than silently at the first login.
    MIN_JWT_SECRET_BYTES: ClassVar[int] = 32

    @model_validator(mode="after")
    def _production_needs_a_real_secret(self) -> "Settings":
        if self.environment != "production":
            return self
        secret = self.jwt_secret_key
        if "CHANGE_ME" in secret.upper():
            raise ValueError(
                "JWT_SECRET_KEY is still the placeholder from "
                "deploy/.env.production.example - generate one with: "
                "python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        if len(secret.encode()) < self.MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {self.MIN_JWT_SECRET_BYTES} bytes "
                f"({len(secret.encode())} given) - generate one with: "
                "python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy URL. Built from parts so the password is never duplicated
        across env vars and can't drift out of sync with the postgres service."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Connections held back from request threads, for the callers that take one
    # without going through get_db: /health, chiefly. Without this reserve a
    # fully busy app cannot answer its own health check, Docker calls the
    # container unhealthy and restarts it - turning a slow minute into an outage.
    THREAD_CONNECTION_RESERVE: ClassVar[int] = 2

    @computed_field  # type: ignore[prop-decorator]
    @property
    def request_thread_limit(self) -> int:
        """How many sync route handlers may run at once.

        Every route in this app is a sync `def`, so Starlette runs each one in
        AnyIO's worker threadpool, and each one holds a pooled connection for
        its whole life. AnyIO's default is 40 threads, which against a pool of
        20 means 20 threads doing work and 20 blocked in pool.connect() until
        pool_timeout expires - a queue with a cliff at the end, and connections
        held by requests whose clients have already given up.

        Capping threads just under the pool means a thread that starts always
        has a connection waiting, and overload shows up as requests waiting to
        start rather than requests failing halfway through.
        """
        return max(1, self.db_pool_size + self.db_max_overflow - self.THREAD_CONNECTION_RESERVE)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_options(self) -> str:
        """The `-c key=value` flags libpq sends to the server on connect.

        Set here rather than in postgresql.conf so they travel with the
        application: the same limits apply against a managed database we do not
        configure, and they cannot drift out of sync with a server file nobody
        remembers editing. A value of 0 is left out entirely, which means the
        server's own setting stands.
        """
        flags = (
            ("statement_timeout", self.db_statement_timeout_ms),
            ("lock_timeout", self.db_lock_timeout_ms),
            ("idle_in_transaction_session_timeout", self.db_idle_in_transaction_timeout_ms),
        )
        return " ".join(f"-c {name}={value}" for name, value in flags if value > 0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        # URL-quoted: a password containing '@' or '/' would otherwise be
        # parsed as part of the host.
        if self.redis_password:
            secret = quote(self.redis_password, safe="")
            return f"redis://:{secret}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is read once per process."""
    return Settings()  # type: ignore[call-arg]
