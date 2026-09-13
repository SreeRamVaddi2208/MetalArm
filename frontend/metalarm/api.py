"""HTTP client for the MetalArm API.

Every endpoint shape here comes from docs/api-contract.md, which the backend
generates from its live OpenAPI spec. Nothing is invented locally - if
something is missing, it gets added there first (Section 4 of the brief).

These calls run SERVER-side inside the Reflex process, not in the browser, so
the base URL is resolved on the compose network.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# LEVELFORGE_API_BASE_URL is the pre-rename name, still honoured so an existing
# local .env keeps working after the project became MetalArm.
BASE_URL = (
    os.getenv("METALARM_API_BASE_URL")
    or os.getenv("LEVELFORGE_API_BASE_URL")
    or "http://localhost:8000"
).rstrip("/")
API = f"{BASE_URL}/api/v1"

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class ApiError(Exception):
    """A non-2xx response, carrying the API's own message.

    The backend writes `detail` strings to be shown to a user (e.g. "Quest
    already completed for this period"), so they are surfaced verbatim rather
    than replaced with a generic failure message.
    """

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _extract_detail(response: httpx.Response) -> str:
    """Pull a human-readable message out of an error body.

    FastAPI returns `detail` as a string for HTTPException but as a LIST of
    per-field objects for 422 validation errors, so both shapes are handled -
    otherwise a validation error renders as an unreadable blob.
    """
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        parts = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            loc = item.get("loc") or []
            field = str(loc[-1]) if loc else "input"
            parts.append(f"{field}: {item.get('msg', 'invalid')}")
        if parts:
            return "; ".join(parts)
    return f"HTTP {response.status_code}"


async def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    """Call the API and return the decoded body, raising ApiError on failure."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{API}{path}"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.request(method, url, headers=headers, json=json)
    except httpx.RequestError as exc:
        # The backend being down must read as a clear message, not a stack
        # trace in the UI. The frontend is deliberately startable without it.
        raise ApiError(0, f"Cannot reach the API at {BASE_URL}: {exc.__class__.__name__}") from exc

    if response.status_code >= 400:
        raise ApiError(response.status_code, _extract_detail(response))

    if response.status_code == 204 or not response.content:
        return None
    return response.json()


# --- Auth ------------------------------------------------------------------


async def signup(email: str, password: str, display_name: str, timezone: str) -> dict:
    return await request(
        "POST",
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
            "timezone": timezone,
        },
    )


async def login(email: str, password: str) -> dict:
    return await request("POST", "/auth/login", json={"email": email, "password": password})


async def refresh(refresh_token: str) -> dict:
    """Swap a refresh token for a new access + refresh pair."""
    return await request("POST", "/auth/refresh", json={"refresh_token": refresh_token})


async def logout(*, refresh_token: str = "", token: str = "") -> None:
    """End this browser's session on the server (other devices stay signed in).

    Prefers the refresh token: it is still valid after the access token has
    expired, so the session is revoked even from a tab left open for hours.
    """
    if refresh_token:
        await request("POST", "/auth/logout", json={"refresh_token": refresh_token})
    else:
        await request("POST", "/auth/logout", token=token)


async def me(token: str) -> dict:
    return await request("GET", "/auth/me", token=token)


# --- Quests ----------------------------------------------------------------


async def list_quests(token: str, status: str = "active") -> list[dict]:
    return await request("GET", f"/quests?status={status}", token=token)


async def create_quest(token: str, payload: dict) -> dict:
    return await request("POST", "/quests", token=token, json=payload)


async def update_quest(token: str, quest_id: str, payload: dict) -> dict:
    return await request("PATCH", f"/quests/{quest_id}", token=token, json=payload)


async def delete_quest(token: str, quest_id: str) -> None:
    await request("DELETE", f"/quests/{quest_id}", token=token)


async def complete_quest(token: str, quest_id: str) -> dict:
    return await request("POST", f"/quests/{quest_id}/complete", token=token)


# --- Rewards ---------------------------------------------------------------


async def list_rewards(token: str, include_inactive: bool = False) -> list[dict]:
    return await request(
        "GET", f"/rewards?include_inactive={str(include_inactive).lower()}", token=token
    )


async def create_reward(token: str, payload: dict) -> dict:
    return await request("POST", "/rewards", token=token, json=payload)


async def update_reward(token: str, reward_id: str, payload: dict) -> dict:
    return await request("PATCH", f"/rewards/{reward_id}", token=token, json=payload)


async def delete_reward(token: str, reward_id: str) -> None:
    await request("DELETE", f"/rewards/{reward_id}", token=token)


async def redeem_reward(token: str, reward_id: str) -> dict:
    return await request("POST", f"/rewards/{reward_id}/redeem", token=token)


async def wallet(token: str) -> dict:
    return await request("GET", "/rewards/wallet", token=token)


async def redemptions(token: str) -> list[dict]:
    return await request("GET", "/rewards/redemptions", token=token)


# --- Parties ---------------------------------------------------------------


async def list_parties(token: str) -> list[dict]:
    return await request("GET", "/parties", token=token)


async def create_party(token: str, name: str) -> dict:
    return await request("POST", "/parties", token=token, json={"name": name})


async def join_party(token: str, invite_code: str) -> dict:
    return await request(
        "POST", "/parties/join", token=token, json={"invite_code": invite_code}
    )


async def get_party(token: str, party_id: str) -> dict:
    return await request("GET", f"/parties/{party_id}", token=token)


async def leave_party(token: str, party_id: str) -> None:
    await request("POST", f"/parties/{party_id}/leave", token=token)


async def dissolve_party(token: str, party_id: str) -> None:
    await request("DELETE", f"/parties/{party_id}", token=token)


async def rotate_invite(token: str, party_id: str) -> dict:
    return await request("POST", f"/parties/{party_id}/rotate-invite", token=token)


async def party_leaderboard(token: str, party_id: str) -> dict:
    return await request("GET", f"/parties/{party_id}/leaderboard", token=token)


async def list_party_quests(token: str, party_id: str) -> list[dict]:
    return await request("GET", f"/parties/{party_id}/quests", token=token)


async def create_party_quest(token: str, party_id: str, payload: dict) -> dict:
    return await request(
        "POST", f"/parties/{party_id}/quests", token=token, json=payload
    )


async def complete_party_quest(token: str, party_id: str, quest_id: str) -> dict:
    return await request(
        "POST", f"/parties/{party_id}/quests/{quest_id}/complete", token=token
    )


async def delete_party_quest(token: str, party_id: str, quest_id: str) -> None:
    await request("DELETE", f"/parties/{party_id}/quests/{quest_id}", token=token)


# --- Profile ---------------------------------------------------------------


async def profile(token: str) -> dict:
    return await request("GET", "/profile", token=token)
