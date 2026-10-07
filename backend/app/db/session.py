"""Database engine and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    # Verifies a pooled connection is still alive before handing it out.
    # Without this, a Postgres restart leaves stale connections in the pool
    # that fail on first use.
    pool_pre_ping=True,
    # Sized from settings, not hardcoded: the right number depends on the
    # worker and container count, which is a deployment decision. See the
    # comments on these in app/core/config.py for the arithmetic.
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle_seconds,
    echo=False,
    connect_args={
        # Names this app's connections in pg_stat_activity, so a saturated
        # server can be told apart from a saturated pool.
        "application_name": "metalarm-api",
        # An unreachable database should fail in seconds, not hang a request
        # thread on the TCP default.
        "connect_timeout": 5,
        # statement_timeout / lock_timeout / idle_in_transaction_session_timeout.
        # A stock server has none of them.
        "options": settings.postgres_options,
    },
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base. All ORM models inherit from this so Alembic
    autogenerate can see them via Base.metadata."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session that is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
