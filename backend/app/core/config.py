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
    # 3000 is the web app, 4000 the marketing site (marketing/). Both post to
    # this API from a browser, so both have to be allowed or the waitlist form
    # fails with a CORS error that looks like the server being down.
    cors_origins: str = "http://localhost:3000,http://localhost:4000"

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
