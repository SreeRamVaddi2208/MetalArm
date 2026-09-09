"""API layer."""

from fastapi import APIRouter

from app.api.routes import auth, quests, rewards

API_V1_PREFIX = "/api/v1"

# Versioned from the start: the frontend pins to this prefix, so a future
# breaking change can ship as /api/v2 without stranding an older client.
api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(auth.router)
api_router.include_router(quests.router)
api_router.include_router(rewards.router)
