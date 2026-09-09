"""Whether the database schema is actually migrated to the revision this code
expects.

Exists because a `SELECT 1` liveness probe cannot tell a fully migrated
database from an empty one. On a fresh volume with no `alembic upgrade head`,
Postgres answers `SELECT 1` perfectly happily while every real query fails with
`relation "users" does not exist` - so /health reported "ok" on a stack that
could not serve a single request. A health check that passes on a broken
deployment is worse than none.
"""

import logging
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("levelforge.schema")

# /app inside the container: this file is <root>/app/db/schema_state.py.
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def expected_head() -> str | None:
    """The migration revision this code expects, read from the versions
    directory. Static for a given image, so it is computed once."""
    try:
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        return ScriptDirectory.from_config(cfg).get_current_head()
    except Exception as exc:  # noqa: BLE001 - never let this break /health
        logger.warning("Could not determine expected migration head: %s", exc)
        return None


def applied_revision(conn: Connection) -> str | None:
    """The revision the database is actually at, or None if it has never been
    migrated (the alembic_version table itself is absent)."""
    try:
        return conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    except SQLAlchemyError:
        return None


def describe(conn: Connection) -> dict[str, object]:
    """Schema readiness for the health payload.

    `ready` is False when the database has not been migrated or is behind the
    code, both of which mean requests will fail even though Postgres is up.
    """
    head = expected_head()
    applied = applied_revision(conn)

    if head is None:
        # Cannot introspect the migrations; report rather than guess.
        return {"ready": True, "applied_revision": applied, "note": "head unknown"}

    if applied is None:
        return {
            "ready": False,
            "applied_revision": None,
            "expected_revision": head,
            "error": "database has never been migrated - run 'alembic upgrade head'",
        }

    if applied != head:
        return {
            "ready": False,
            "applied_revision": applied,
            "expected_revision": head,
            "error": "database schema is out of date - run 'alembic upgrade head'",
        }

    return {"ready": True, "applied_revision": applied}
