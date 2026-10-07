"""HTTP client for the gym-workout endpoints.

Shapes come from docs/api-contract.md and behaviour from docs/workouts-api.md.
Nothing is invented locally. Built on api.request, so errors surface as
ApiError carrying the API's own user-facing message.

No function here sends a point value: the API computes every award from the
raw workout data (brief, Section 4).
"""

from __future__ import annotations

from urllib.parse import urlencode

from metalarm.api import request


def _q(path: str, **params: object) -> str:
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{path}?{urlencode(clean)}" if clean else path


# --- Account -----------------------------------------------------------------


async def update_account(token: str, payload: dict) -> dict:
    return await request("PATCH", "/auth/me", token=token, json=payload)


# --- Party workout leaderboard ---------------------------------------------


async def party_workout_leaderboard(token: str, party_id: str, period: str = "week") -> dict:
    return await request(
        "GET", _q(f"/parties/{party_id}/workout-leaderboard", period=period), token=token
    )


# --- Exercise library ------------------------------------------------------


async def exercise_meta(token: str) -> dict:
    return await request("GET", "/exercises/meta", token=token)


async def search_exercises(
    token: str, q: str = "", muscle: str = "", limit: int = 40
) -> list[dict]:
    return await request(
        "GET", _q("/exercises", q=q.strip(), muscle=muscle, limit=limit), token=token
    )


async def get_exercise(token: str, exercise_id: str) -> dict:
    return await request("GET", f"/exercises/{exercise_id}", token=token)


async def create_exercise(token: str, payload: dict) -> dict:
    return await request("POST", "/exercises", token=token, json=payload)


async def last_performance(token: str, exercise_id: str) -> dict:
    return await request("GET", f"/exercises/{exercise_id}/last-performance", token=token)


async def exercise_history(token: str, exercise_id: str, limit: int = 60) -> list[dict]:
    return await request(
        "GET", _q(f"/exercises/{exercise_id}/history", limit=limit), token=token
    )


# --- Routines --------------------------------------------------------------


async def list_routines(token: str) -> list[dict]:
    return await request("GET", "/routines", token=token)


async def get_routine(token: str, routine_id: str) -> dict:
    return await request("GET", f"/routines/{routine_id}", token=token)


async def create_routine(token: str, payload: dict) -> dict:
    return await request("POST", "/routines", token=token, json=payload)


async def replace_routine(token: str, routine_id: str, payload: dict) -> dict:
    return await request("PUT", f"/routines/{routine_id}", token=token, json=payload)


async def delete_routine(token: str, routine_id: str) -> None:
    await request("DELETE", f"/routines/{routine_id}", token=token)


# --- Sessions --------------------------------------------------------------


async def presets(token: str) -> list[dict]:
    """The ready-made workouts, one per training style."""
    return await request("GET", "/workouts/presets", token=token)


async def start_session(
    token: str, routine_id: str | None = None, preset_slug: str | None = None
) -> dict:
    body: dict[str, str] = {}
    if preset_slug:
        body["preset_slug"] = preset_slug
    elif routine_id:
        body["routine_id"] = routine_id
    return await request("POST", "/workouts/sessions", token=token, json=body)


async def active_session(token: str) -> dict:
    return await request("GET", "/workouts/sessions/active", token=token)


async def get_session(token: str, session_id: str) -> dict:
    return await request("GET", f"/workouts/sessions/{session_id}", token=token)


async def list_sessions(
    token: str, limit: int = 20, before: str = "", status: str = ""
) -> list[dict]:
    return await request(
        "GET",
        _q("/workouts/sessions", limit=limit, before=before, status=status),
        token=token,
    )


async def log_set(token: str, session_id: str, payload: dict) -> dict:
    return await request(
        "POST", f"/workouts/sessions/{session_id}/sets", token=token, json=payload
    )


async def update_set(token: str, session_id: str, set_id: str, payload: dict) -> dict:
    return await request(
        "PATCH", f"/workouts/sessions/{session_id}/sets/{set_id}", token=token, json=payload
    )


async def delete_set(token: str, session_id: str, set_id: str) -> dict:
    return await request(
        "DELETE", f"/workouts/sessions/{session_id}/sets/{set_id}", token=token
    )


async def finish_session(token: str, session_id: str) -> dict:
    return await request("POST", f"/workouts/sessions/{session_id}/finish", token=token)


async def routine_from_session(token: str, session_id: str, name: str | None = None) -> dict:
    return await request("POST", f"/routines/from-session/{session_id}", token=token,
                         json={"name": name} if name else {})


async def abandon_session(token: str, session_id: str) -> dict:
    return await request("POST", f"/workouts/sessions/{session_id}/abandon", token=token)


# --- Records and points ----------------------------------------------------


async def records(token: str) -> list[dict]:
    return await request("GET", "/workouts/records", token=token)


async def points(token: str) -> dict:
    return await request("GET", "/workouts/points", token=token)


# --- Body measurements -----------------------------------------------------


async def list_measurements(token: str, metric: str = "", limit: int = 100) -> list[dict]:
    return await request(
        "GET", _q("/body-measurements", metric=metric, limit=limit), token=token
    )


async def create_measurement(token: str, payload: dict) -> dict:
    return await request("POST", "/body-measurements", token=token, json=payload)


async def delete_measurement(token: str, measurement_id: str) -> None:
    await request("DELETE", f"/body-measurements/{measurement_id}", token=token)


# --- Natural-language logging ----------------------------------------------
# A parse PROPOSES sets; nothing is logged until each is sent to log_set.


async def parse_set(token: str, text: str, session_id: str = "", exercise_id: str = "") -> dict:
    body: dict = {"text": text}
    if session_id:
        body["session_id"] = session_id
    if exercise_id:
        body["exercise_id"] = exercise_id
    return await request("POST", "/log/parse", token=token, json=body)


async def parse_feedback(token: str, parse_id: str, payload: dict) -> dict:
    return await request("POST", f"/log/parse/{parse_id}/feedback", token=token, json=payload)


# --- Overhaul phase 1: exercise cards ---------------------------------------
# A session is an ordered list of cards; sets belong to a card.


async def add_session_exercise(token: str, session_id: str, exercise_id: str) -> dict:
    return await request("POST", f"/workouts/sessions/{session_id}/exercises", token=token,
                         json={"exercise_id": exercise_id})


async def update_session_exercise(token: str, session_id: str, card_id: str, payload: dict) -> dict:
    return await request("PATCH", f"/workouts/sessions/{session_id}/exercises/{card_id}",
                         token=token, json=payload)


async def reorder_session_exercises(token: str, session_id: str, order: list[str]) -> dict:
    return await request("POST", f"/workouts/sessions/{session_id}/exercises/reorder",
                         token=token, json={"order": order})


async def remove_session_exercise(token: str, session_id: str, card_id: str, force: bool = False) -> dict:
    return await request("DELETE", _q(f"/workouts/sessions/{session_id}/exercises/{card_id}",
                                      force="true" if force else ""), token=token)


# --- Overhaul phase 1: the Library -------------------------------------------


async def library(token: str, filter: str = "programs", sort: str = "recents", cursor: str = "",
                  limit: int = 30) -> dict:
    return await request("GET", _q("/library", filter=filter, sort=sort, cursor=cursor, limit=limit),
                         token=token)


async def programs(token: str, mine: bool = True) -> list[dict]:
    return await request("GET", _q("/programs", mine="true" if mine else "false"), token=token)


async def get_program(token: str, program_id: str) -> dict:
    return await request("GET", f"/programs/{program_id}", token=token)


async def create_program(token: str, payload: dict) -> dict:
    return await request("POST", "/programs", token=token, json=payload)


async def delete_program(token: str, program_id: str) -> None:
    await request("DELETE", f"/programs/{program_id}", token=token)


async def favorite(token: str, target_type: str, target_id: str, on: bool) -> None:
    if on:
        await request("POST", "/favorites", token=token,
                      json={"target_type": target_type, "target_id": target_id})
    else:
        await request("DELETE", f"/favorites/{target_type}/{target_id}", token=token)


async def suggested(token: str) -> list[dict]:
    return await request("GET", "/workouts/suggested", token=token)


# --- Explore (overhaul phase 3) ---------------------------------------------


async def browse(token: str, q: str = "", muscle: str = "", equipment: str = "", category: str = "",
                 cursor: str = "", limit: int = 30) -> dict:
    return await request("GET", _q("/exercises/browse", q=q, muscle=muscle, equipment=equipment,
                                    category=category, cursor=cursor, limit=limit), token=token)


async def curated_programs(token: str, category: str = "") -> list[dict]:
    return await request("GET", _q("/programs/curated", category=category), token=token)


async def save_curated(token: str, slug: str) -> dict:
    return await request("POST", f"/programs/curated/{slug}/save", token=token)
