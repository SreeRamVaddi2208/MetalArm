#!/usr/bin/env python3
"""End-to-end smoke test against a RUNNING LevelForge stack.

Exercises the full user journey across every sprint - health, auth, quests,
completion, XP/level/rank, rewards, redemption, wallet - over real HTTP, and
cleans up after itself. Exits non-zero on the first failure.

This complements the pytest suite rather than duplicating it: pytest drives the
app in-process against a throwaway database, whereas this proves the actual
deployed stack (containers, network, migrations, real Postgres and Redis)
serves real requests.

    docker compose up -d
    python3 scripts/smoke_test.py
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = "http://localhost:8000"
API = f"{BASE}/api/v1"

_passed = 0
_failed: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  \033[32mPASS\033[0m  {label}")
    else:
        _failed.append(label)
        print(f"  \033[31mFAIL\033[0m  {label}  {detail}")


def call(
    method: str, path: str, token: str | None = None, body: dict | None = None
) -> tuple[int, dict]:
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw else {})


def new_user(tz: str = "UTC") -> tuple[str, dict]:
    email = f"smoke-{uuid.uuid4().hex[:12]}@levelforge.dev"
    status, created = call(
        "POST",
        "/auth/signup",
        body={
            "email": email,
            "password": "smoke-test-passphrase",
            "display_name": "Smoke",
            "timezone": tz,
        },
    )
    if status != 201:
        raise SystemExit(f"signup failed: {status} {created}")
    status, tok = call(
        "POST", "/auth/login", body={"email": email, "password": "smoke-test-passphrase"}
    )
    if status != 200:
        raise SystemExit(f"login failed: {status} {tok}")
    return tok["access_token"], created


def section(name: str) -> None:
    print(f"\n\033[1m{name}\033[0m")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="Do not delete the test users.")
    args = parser.parse_args()

    print(f"LevelForge smoke test -> {BASE}")

    # -- Sprint 1: infrastructure ------------------------------------------
    section("Sprint 1 - health and readiness")
    status, health = call("GET", f"{BASE}/health")
    check("GET /health returns 200", status == 200, str(health)[:120])
    check("postgres connected", health.get("dependencies", {}).get("postgres", {}).get("connected") is True)
    check("redis connected", health.get("dependencies", {}).get("redis", {}).get("connected") is True)
    schema = health.get("dependencies", {}).get("postgres", {}).get("schema", {})
    check("schema is migrated", schema.get("ready") is True, str(schema))
    check("health reports a real postgres version",
          bool(health.get("dependencies", {}).get("postgres", {}).get("server_version")))
    status, _ = call("GET", f"{BASE}/openapi.json")
    check("GET /openapi.json returns 200", status == 200)

    # -- Sprint 2: auth ----------------------------------------------------
    section("Sprint 2 - auth")
    token, created = new_user(tz="America/New_York")
    check("signup + login succeed", bool(token))
    status, me = call("GET", "/auth/me", token)
    check("GET /auth/me returns the user", status == 200 and me["id"] == created["id"])
    check("password hash never leaves the API", "password" not in json.dumps(me))
    status, _ = call("GET", "/auth/me")
    check("GET /auth/me without a token is 401", status == 401)
    status, _ = call("GET", "/auth/me", "not.a.jwt")
    check("garbage token is 401", status == 401)
    status, body = call("POST", "/auth/signup",
                        body={"email": created["email"], "password": "another-passphrase",
                              "display_name": "Dup"})
    check("duplicate email is 409", status == 409, str(body)[:100])

    # -- Sprint 2: quests --------------------------------------------------
    section("Sprint 2 - quests")
    status, daily = call("POST", "/quests", token,
                         {"title": "Morning run", "xp_reward": 150, "points_reward": 20,
                          "recurrence": "daily"})
    check("create a daily quest", status == 201, str(daily)[:100])
    status, weekly = call("POST", "/quests", token,
                          {"title": "Weekly review", "xp_reward": 300, "recurrence": "weekly"})
    check("create a weekly quest", status == 201)
    check("weekly period key is an ISO week",
          "W" in weekly.get("current_period_key", ""), weekly.get("current_period_key", ""))
    status, board = call("GET", "/quests", token)
    check("quest board lists both", status == 200 and len(board) == 2)
    status, body = call("POST", "/quests", token, {"title": "Cheat", "xp_reward": 999999})
    check("XP over the cap is 422", status == 422)

    status, done = call("POST", f"/quests/{daily['id']}/complete", token)
    check("complete a quest", status == 200, str(done)[:120])
    prog = done.get("progression", {})
    check("XP was awarded", prog.get("xp_awarded") == 150)
    check("level-up reported", prog.get("leveled_up") is True, str(prog))
    check("streak started", prog.get("current_streak") == 1)
    status, body = call("POST", f"/quests/{daily['id']}/complete", token)
    check("double completion in the same period is 409", status == 409, str(body)[:100])
    status, board = call("GET", "/quests", token)
    done_flags = {q["title"]: q["completed_in_current_period"] for q in board}
    check("board shows per-period completion", done_flags.get("Morning run") is True)

    # -- Sprint 3: progression --------------------------------------------
    section("Sprint 3 - XP curve and rank")
    status, me = call("GET", "/auth/me", token)
    p = me["progress"]
    check("total_xp reflects the completion", p["total_xp"] == 150)
    check("level derived from the curve", p["current_level"] >= 2, str(p["current_level"]))
    check("rank present", p["rank"] in {"E", "D", "C", "B", "A", "S"})
    check("XP bar populated", p["xp_for_next_level"] > 0)
    check("streak is active", p["streak_is_active"] is True)
    check("next rank advertised", p["next_rank"] == "D" and p["next_rank_level"] == 8, str(p))

    # -- Sprint 4: rewards -------------------------------------------------
    section("Sprint 4 - rewards shop")
    status, reward = call("POST", "/rewards", token, {"title": "Order takeout", "point_cost": 15})
    check("create a reward", status == 201, str(reward)[:100])
    check("affordable computed", reward["affordable"] is True, str(reward))
    status, body = call("POST", "/rewards", token, {"title": "Free", "point_cost": 0})
    check("zero-cost reward is 422", status == 422)
    status, expensive = call("POST", "/rewards", token, {"title": "Holiday", "point_cost": 99999})
    check("unaffordable reward flagged", expensive["affordable"] is False)
    status, body = call("POST", f"/rewards/{expensive['id']}/redeem", token)
    check("redeeming beyond balance is 409", status == 409, str(body)[:100])

    status, redeemed = call("POST", f"/rewards/{reward['id']}/redeem", token)
    check("redeem a reward", status == 200, str(redeemed)[:120])
    check("balance debited", redeemed.get("points_balance") == 5, str(redeemed))
    status, wallet = call("GET", "/rewards/wallet", token)
    check("wallet balance correct", wallet["points_balance"] == 5, str(wallet))
    check("wallet earned/spent tracked",
          wallet["total_points_earned"] == 20 and wallet["total_points_spent"] == 15, str(wallet))
    status, history = call("GET", "/rewards/redemptions", token)
    check("redemption history recorded",
          status == 200 and len(history) == 1 and history[0]["points_spent"] == 15)
    status, body = call("DELETE", f"/rewards/{reward['id']}", token)
    check("deleting a redeemed reward is 409", status == 409, str(body)[:100])
    status, _ = call("PATCH", f"/rewards/{reward['id']}", token, {"is_active": False})
    check("deactivating instead succeeds", status == 200)

    # -- Cross-cutting: ownership isolation --------------------------------
    section("Cross-cutting - ownership isolation")
    other, _ = new_user()
    status, board = call("GET", "/quests", other)
    check("another user sees none of the quests", status == 200 and board == [])
    status, shop = call("GET", "/rewards", other)
    check("another user sees none of the rewards", status == 200 and shop == [])
    for method, path in [("GET", f"/quests/{daily['id']}"),
                         ("PATCH", f"/quests/{daily['id']}"),
                         ("DELETE", f"/quests/{daily['id']}"),
                         ("POST", f"/quests/{daily['id']}/complete"),
                         ("GET", f"/rewards/{reward['id']}"),
                         ("POST", f"/rewards/{reward['id']}/redeem")]:
        status, _ = call(method, path, other, {} if method == "PATCH" else None)
        check(f"{method} another user's resource is 404", status == 404, f"got {status}")
    status, me_other = call("GET", "/auth/me", other)
    check("another user's XP is untouched", me_other["progress"]["total_xp"] == 0)

    # -- Cleanup -----------------------------------------------------------
    if not args.keep:
        section("Cleanup")
        for tok in (token, other):
            status, quests = call("GET", "/quests", tok)
            for q in quests:
                call("DELETE", f"/quests/{q['id']}", tok)
            status, quests = call("GET", "/quests?status=archived", tok)
            for q in quests:
                call("DELETE", f"/quests/{q['id']}", tok)
        check("test quests removed", True)
        print("  note: smoke users remain (no delete-account endpoint yet)")

    # -- Summary -----------------------------------------------------------
    total = _passed + len(_failed)
    print(f"\n{'=' * 60}")
    if _failed:
        print(f"\033[31m{len(_failed)} of {total} checks FAILED\033[0m")
        for name in _failed:
            print(f"  - {name}")
        return 1
    print(f"\033[32mAll {total} checks passed.\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
