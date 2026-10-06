"""Client for the clarity screens' read models (overhaul phase 2). Every
number is the server's; these only fetch."""

from __future__ import annotations

from metalarm.api import request
from metalarm.workout_api import _q


async def snapshot(token: str, week: str = "") -> dict:
    return await request("GET", _q("/analytics/snapshot", week=week), token=token)


async def series(token: str, metric: str, range_: str) -> dict:
    return await request("GET", _q("/analytics/series", metric=metric, range=range_), token=token)


async def muscles(token: str, from_: str = "", to: str = "") -> dict:
    return await request("GET", _q("/analytics/muscles", **{"from": from_, "to": to}), token=token)


async def calendar(token: str, month: str = "") -> dict:
    return await request("GET", _q("/analytics/calendar", month=month), token=token)


async def recovery(token: str) -> dict:
    return await request("GET", "/analytics/recovery", token=token)


async def history(token: str, cursor: str = "", limit: int = 20) -> dict:
    return await request("GET", _q("/history", cursor=cursor, limit=limit), token=token)


async def my_exercises(token: str, cursor: str = "", limit: int = 30) -> dict:
    return await request("GET", _q("/me/exercises", cursor=cursor, limit=limit), token=token)


async def exercise_stats(token: str, exercise_id: str, range_: str = "All") -> dict:
    return await request("GET", _q(f"/exercises/{exercise_id}/stats", range=range_), token=token)
