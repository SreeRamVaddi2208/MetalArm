"""Client for the social graph and the game strip (overhaul phase 4)."""

from __future__ import annotations

from metalarm.api import request
from metalarm.workout_api import _q


async def follow(token: str, user_id: str, on: bool = True) -> None:
    await request("POST" if on else "DELETE", f"/follows/{user_id}", token=token)


async def search_users(token: str, q: str, cursor: str = "") -> dict:
    return await request("GET", _q("/users/search", q=q, cursor=cursor), token=token)


async def suggested_users(token: str) -> dict:
    return await request("GET", "/users/suggested", token=token)


async def profile(token: str, user_id: str) -> dict:
    return await request("GET", f"/users/{user_id}", token=token)


async def user_sessions(token: str, user_id: str, cursor: str = "") -> dict:
    return await request("GET", _q(f"/users/{user_id}/sessions", cursor=cursor), token=token)


async def feed(token: str, cursor: str = "", limit: int = 10) -> dict:
    return await request("GET", _q("/feed/following", cursor=cursor, limit=limit), token=token)


async def spot(token: str, session_id: str, on: bool = True) -> dict:
    return await request("POST" if on else "DELETE", f"/workouts/sessions/{session_id}/reactions", token=token)


async def notifications(token: str, cursor: str = "") -> dict:
    return await request("GET", _q("/notifications", cursor=cursor), token=token)


async def mark_read(token: str, ids: list[str] | None = None) -> dict:
    return await request("POST", "/notifications/read", token=token, json={"ids": ids or []})


async def game(token: str) -> dict:
    return await request("GET", "/me/game", token=token)


async def leaderboard(token: str, period: str = "week") -> dict:
    return await request("GET", _q("/leaderboard/friends", period=period), token=token)


async def duel_opponents(token: str) -> list[dict]:
    return await request("GET", "/duels/opponents", token=token)


async def set_visibility(token: str, session_id: str, visibility: str) -> dict:
    return await request("PATCH", f"/workouts/sessions/{session_id}", token=token, json={"visibility": visibility})


async def reactions(token: str, session_id: str) -> dict:
    return await request("GET", f"/workouts/sessions/{session_id}/reactions", token=token)
