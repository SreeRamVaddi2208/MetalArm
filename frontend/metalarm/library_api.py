"""HTTP client for the Library tab (docs/api-contract.md, /library/*).

Thin on purpose: what is recommended, and in what order, comes back from the
server on every item (`recommended`, `sort`); nothing here decides it.
"""

from __future__ import annotations

from urllib.parse import urlencode

from metalarm.api import request


def _q(path: str, **params: object) -> str:
    clean = {k: v for k, v in params.items() if v not in (None, "", [])}
    return f"{path}?{urlencode(clean, doseq=True)}" if clean else path


async def home(token: str) -> dict:
    return await request("GET", "/library/home", token=token)


async def programs(token: str, *, category: str = "", difficulty: str = "", days_per_week: int | None = None,
                   equipment: list[str] | None = None) -> list[dict]:
    return await request("GET", _q("/library/programs", category=category, difficulty=difficulty,
                                   days_per_week=days_per_week, equipment=equipment or []), token=token)


async def program(token: str, slug: str) -> dict:
    return await request("GET", f"/library/programs/{slug}", token=token)


async def workouts(token: str, *, category: str = "", difficulty: str = "", equipment: list[str] | None = None,
                   max_minutes: int | None = None) -> list[dict]:
    return await request("GET", _q("/library/workouts", category=category, difficulty=difficulty,
                                   equipment=equipment or [], max_minutes=max_minutes), token=token)


async def workout(token: str, slug: str) -> dict:
    return await request("GET", f"/library/workouts/{slug}", token=token)


async def start(token: str, slug: str) -> dict:
    return await request("POST", f"/library/workouts/{slug}/start", token=token)


async def save_to_routines(token: str, slug: str) -> dict:
    return await request("POST", f"/library/workouts/{slug}/save-to-routines", token=token)


async def follow(token: str, slug: str) -> dict:
    return await request("POST", f"/library/programs/{slug}/follow", token=token)


async def unfollow(token: str, slug: str) -> dict:
    return await request("DELETE", f"/library/programs/{slug}/follow", token=token)
