"""API layer."""

from fastapi import APIRouter

from app.api.routes import (
    social,
    analytics,
    auth,
    body,
    devices,
    duels,
    exercises,
    leagues,
    library,
    nl_log,
    parties,
    profile,
    quest_board,
    quests,
    rewards,
    routines,
    taxonomy,
    training_paths,
    workouts,
)

API_V1_PREFIX = "/api/v1"

# Versioned from the start: the frontend pins to this prefix, so a future
# breaking change can ship as /api/v2 without stranding an older client.
api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(auth.router)
# Before quests: /quests/current must not match /quests/{quest_id}.
api_router.include_router(quest_board.router)
api_router.include_router(quests.router)
api_router.include_router(rewards.router)
api_router.include_router(parties.router)
api_router.include_router(profile.router)
# Before exercises: /exercises/aliases must not match /exercises/{exercise_id}.
api_router.include_router(nl_log.router)
api_router.include_router(exercises.router)
api_router.include_router(routines.router)
# Before workouts: /workouts/suggested.
api_router.include_router(library.router)
api_router.include_router(workouts.router)
api_router.include_router(body.router)
api_router.include_router(leagues.router)
api_router.include_router(duels.router)
api_router.include_router(devices.router)
api_router.include_router(training_paths.router)
api_router.include_router(taxonomy.router)
api_router.include_router(analytics.router)
api_router.include_router(social.router)
