"""MetalArm API entrypoint.

Sprint 1: application scaffold plus a /health endpoint that reports a REAL
Postgres and Redis connection state. Nothing here is hardcoded to "ok" - if a
dependency is down, /health says so and returns 503.

Sprint 2: auth (signup/login/JWT) and quest CRUD, mounted under /api/v1.
"""

import logging
from typing import Any

import redis
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import api_router
from app.core.config import get_settings
from app.db.redis_client import get_redis
from app.db.schema_state import describe as describe_schema
from app.db.session import engine

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("metalarm")

app = FastAPI(
    title="MetalArm API",
    description="Turn real goals and habits into RPG-style progression.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _check_postgres() -> dict[str, Any]:
    """Round-trip a query AND confirm the schema is migrated.

    The connectivity half reports the real server version so a pass cannot be
    confused with a stubbed response. The schema half exists because
    connectivity alone is not readiness: an un-migrated database answers
    SELECT 1 happily while every real query fails on a missing table.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            version = conn.execute(text("SHOW server_version")).scalar_one()
            schema = describe_schema(conn)
        return {"connected": True, "server_version": version, "schema": schema}
    except SQLAlchemyError as exc:
        logger.warning("Postgres health check failed: %s", exc)
        return {"connected": False, "error": exc.__class__.__name__}


def _check_redis() -> dict[str, Any]:
    try:
        client = get_redis()
        client.ping()
        info = client.info("server")
        return {"connected": True, "server_version": info.get("redis_version")}
    except (redis.RedisError, OSError) as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {"connected": False, "error": exc.__class__.__name__}


@app.get("/health", tags=["system"])
def health(response: Response) -> dict[str, Any]:
    """Liveness + dependency readiness.

    Returns 200 only when Postgres AND Redis both genuinely respond;
    otherwise 503 with per-dependency detail.
    """
    postgres = _check_postgres()
    cache = _check_redis()
    # Readiness, not just liveness: a connected but un-migrated database is
    # not something this service can serve requests against.
    schema_ready = bool(postgres.get("schema", {}).get("ready", False))
    healthy = postgres["connected"] and cache["connected"] and schema_ready

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "degraded",
        "service": "metalarm-api",
        "version": app.version,
        "dependencies": {"postgres": postgres, "redis": cache},
    }


app.include_router(api_router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "metalarm-api", "docs": "/docs", "health": "/health"}
