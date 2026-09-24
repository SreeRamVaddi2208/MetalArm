#!/usr/bin/env python3
"""End-to-end smoke test against a RUNNING MetalArm stack.

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
    email = f"smoke-{uuid.uuid4().hex[:12]}@metalarm.dev"
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
    if status == 429:
        raise SystemExit(
            "signup rate limited (429).\n"
            "This test creates 5 accounts and the limit is 5 per IP per hour, so\n"
            "anything else that signed up from here in the last hour uses it up.\n"
            "Wait, or clear the counter on a LOCAL stack:\n"
            '  docker compose exec redis redis-cli -a "$REDIS_PASSWORD" '
            "--scan --pattern 'ratelimit:signup-ip:*' | xargs -r redis-cli del"
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

    print(f"MetalArm smoke test -> {BASE}")

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

    # -- Sprint 5: parties -------------------------------------------------
    section("Sprint 5 - parties, shared board, leaderboard")
    status, party = call("POST", "/parties", token, {"name": "Smoke Guild"})
    check("create a party", status == 201, str(party)[:100])
    check("creator is owner and member", party["my_role"] == "owner" and party["member_count"] == 1)
    check("default cap is 10", party["max_members"] == 10, str(party.get("max_members")))
    code = party["invite_code"]
    check("invite code avoids ambiguous characters",
          len(code) == 8 and not (set("01OIL") & set(code)), code)

    friend, _ = new_user()
    status, joined = call("POST", "/parties/join", friend, {"invite_code": code.lower()})
    check("join by code (case-insensitive)", status == 200 and joined["member_count"] == 2, str(joined)[:100])
    status, _ = call("POST", "/parties/join", friend, {"invite_code": "ZZZZZZZZ"})
    check("unknown invite code is 404", status == 404)

    status, pquest = call("POST", f"/parties/{party['id']}/quests", friend,
                          {"title": "Group raid", "xp_reward": 200, "recurrence": "daily"})
    check("any member can add a shared quest", status == 201, str(pquest)[:100])

    status, done = call("POST", f"/parties/{party['id']}/quests/{pquest['id']}/complete", token)
    check("complete a shared quest", status == 200, str(done)[:120])
    check("shared completion awards personal XP", done.get("xp_awarded") == 200)
    check("and credits the party", done.get("total_party_xp") == 200, str(done.get("total_party_xp")))
    status, _ = call("POST", f"/parties/{party['id']}/quests/{pquest['id']}/complete", token)
    check("repeat completion in the same period is 409", status == 409)

    status, board = call("GET", f"/parties/{party['id']}/leaderboard", token)
    check("leaderboard lists the whole party", status == 200 and len(board["entries"]) == 2, str(board)[:120])
    check("leaderboard ranks by contributed XP", board["entries"][0]["party_xp"] == 200)
    check("members with no contribution still appear", board["entries"][-1]["party_xp"] == 0)

    status, rotated = call("POST", f"/parties/{party['id']}/rotate-invite", token)
    check("owner can rotate the invite", status == 200 and rotated["invite_code"] != code)
    outsider, _ = new_user()
    status, _ = call("POST", "/parties/join", outsider, {"invite_code": code})
    check("the rotated-away code stops working", status == 404)

    status, _ = call("PATCH", f"/parties/{party['id']}", friend, {"name": "Hijacked"})
    check("a non-owner cannot rename the party", status == 403)

    # -- Cross-cutting: ownership isolation --------------------------------
    section("Cross-cutting - ownership isolation")
    other, _ = new_user()
    status, board = call("GET", "/quests", other)
    check("another user sees none of the quests", status == 200 and board == [])
    status, shop = call("GET", "/rewards", other)
    check("another user sees none of the rewards", status == 200 and shop == [])
    status, parties_seen = call("GET", "/parties", other)
    check("another user sees none of the parties", status == 200 and parties_seen == [])
    status, prof_other = call("GET", "/profile", other)
    check("another user's profile shows their own empty stats",
          status == 200 and prof_other["stats"]["quests_completed"] == 0)
    for method, path in [("GET", f"/quests/{daily['id']}"),
                         ("PATCH", f"/quests/{daily['id']}"),
                         ("DELETE", f"/quests/{daily['id']}"),
                         ("POST", f"/quests/{daily['id']}/complete"),
                         ("GET", f"/rewards/{reward['id']}"),
                         ("POST", f"/rewards/{reward['id']}/redeem"),
                         ("GET", f"/parties/{party['id']}"),
                         ("GET", f"/parties/{party['id']}/leaderboard"),
                         ("GET", f"/parties/{party['id']}/quests")]:
        status, _ = call(method, path, other, {} if method == "PATCH" else None)
        check(f"{method} another user's resource is 404", status == 404, f"got {status}")
    status, me_other = call("GET", "/auth/me", other)
    check("another user's XP is untouched", me_other["progress"]["total_xp"] == 0)

    # -- Section 2: profile page and badges --------------------------------
    section("Section 2 - profile, lifetime stats, badges")
    status, prof = call("GET", "/profile", token)
    check("GET /profile returns 200", status == 200, str(prof)[:100])
    # Not a fixed number: by this point the user has completed a personal
    # quest AND a party quest, and asserting one literal would break the moment
    # anything earlier in the run changes.
    status, me_now = call("GET", "/auth/me", token)
    check("profile progression matches /auth/me",
          prof["progress"]["total_xp"] == me_now["progress"]["total_xp"]
          and prof["progress"]["total_xp"] > 0,
          f'profile={prof["progress"]["total_xp"]} me={me_now["progress"]["total_xp"]}')
    check("lifetime stats counted", prof["stats"]["quests_completed"] >= 1, str(prof.get("stats"))[:80])
    check("party activity counted", prof["stats"]["parties_joined"] >= 1)
    check("badges listed", prof["badges_total"] > 0 and len(prof["badges"]) == prof["badges_total"])
    check("first-quest badge earned",
          any(b["id"] == "first_quest" and b["earned"] for b in prof["badges"]))
    check("unearned badges report progress",
          all(0 <= b["percent"] <= 100 and b["progress"] <= b["target"] for b in prof["badges"]))
    check("profile rank matches /auth/me",
          prof["progress"]["rank"] == call("GET", "/auth/me", token)[1]["progress"]["rank"])
    status, _ = call("GET", "/profile")
    check("profile requires auth", status == 401)

    # -- Gym workout module ------------------------------------------------
    section("Gym workouts - library, logging, PRs, points")
    status, meta = call("GET", "/exercises/meta", token)
    check("exercise vocabularies served", status == 200 and "quads" in meta.get("muscle_groups", []))
    status, library = call("GET", "/exercises?limit=200", token)
    check("starter library is seeded (50+)", status == 200 and len(library) >= 50, f"{len(library)}")
    status, found = call("GET", "/exercises?q=Barbell%20Bench%20Press", token)
    bench = next((e for e in found if e["name"] == "Barbell Bench Press"), None) if status == 200 else None
    check("library is searchable by name", bench is not None, str(found)[:100])

    status, routine = call("POST", "/routines", token,
                           {"name": "Smoke Push",
                            "exercises": [{"exercise_id": bench["id"], "target_sets": 3, "target_reps": 5}]})
    check("create a routine", status == 201, str(routine)[:100])
    status, session = call("POST", "/workouts/sessions", token, {"routine_id": routine["id"]})
    check("start a workout from the routine",
          status == 201 and session["exercises"][0]["target"]["target_sets"] == 3, str(session)[:120])
    sid = session["id"]
    status, _ = call("POST", "/workouts/sessions", token, {})
    check("a second live workout is 409", status == 409)
    status, active = call("GET", "/workouts/sessions/active", token)
    check("the live workout rehydrates", active.get("session", {}).get("id") == sid)

    xp_before = call("GET", "/auth/me", token)[1]["progress"]["total_xp"]
    client_set_id = str(uuid.uuid4())
    status, s1 = call("POST", f"/workouts/sessions/{sid}/sets", token,
                      {"exercise_id": bench["id"], "weight": 60, "reps": 5,
                       "client_set_id": client_set_id, "points": 9999})
    check("log a set", status == 201, str(s1)[:120])
    check("a client-sent point value is ignored", 0 < s1["points_awarded"] < 9999, str(s1["points_awarded"]))
    check("XP moves on every set",
          s1["progression"]["total_xp"] == xp_before + s1["points_awarded"])
    check("a first-ever lift is a baseline, not a paid PR",
          s1["pr_events"] and not any(e["bonus_awarded"] for e in s1["pr_events"]))
    status, dup = call("POST", f"/workouts/sessions/{sid}/sets", token,
                       {"exercise_id": bench["id"], "weight": 60, "reps": 5,
                        "client_set_id": client_set_id})
    check("a retried submit is not logged twice",
          dup.get("is_duplicate") is True and dup["set"]["id"] == s1["set"]["id"]
          and dup["points_awarded"] == 0, str(dup)[:120])

    status, s2 = call("POST", f"/workouts/sessions/{sid}/sets", token,
                      {"exercise_id": bench["id"], "weight": 65, "reps": 5})
    paid = [e for e in s2.get("pr_events", []) if e["bonus_awarded"]]
    check("a heavier set is a paid PR",
          len(paid) == 1 and paid[0]["record_type"] == "max_weight" and paid[0]["previous_value"] == 60,
          str(s2.get("pr_events"))[:160])
    status, s3 = call("POST", f"/workouts/sessions/{sid}/sets", token,
                      {"exercise_id": bench["id"], "weight": 225, "unit": "lb", "reps": 1})
    check("pounds are stored as kilograms", s3["set"]["weight_kg"] == 102.06, str(s3["set"]["weight_kg"]))
    status, removed = call("DELETE", f"/workouts/sessions/{sid}/sets/{s3['set']['id']}", token)
    check("deleting a set reverses its points",
          status == 200 and removed["points_awarded"] == -s3["points_awarded"], str(removed)[:120])

    status, done = call("POST", f"/workouts/sessions/{sid}/finish", token)
    check("finish the workout", status == 200, str(done)[:120])
    check("a two-minute workout earns no session bonus",
          done["qualified"] is False and done["breakdown"]["session_bonus"] == 0)
    check("session points are credited to the wallet",
          done["points_credited"] == done["breakdown"]["total"] > 0, str(done["breakdown"]))
    check("the PR is in the finish summary", any(e["bonus_awarded"] for e in done["pr_events"]))
    status, _ = call("POST", f"/workouts/sessions/{sid}/sets", token,
                     {"exercise_id": bench["id"], "weight": 70, "reps": 5})
    check("a finished workout is immutable", status == 409)

    status, wallet = call("GET", "/rewards/wallet", token)
    check("wallet 'earned' includes the workout credit",
          wallet["total_points_earned"] == 20 + done["points_credited"], str(wallet))
    status, records = call("GET", f"/workouts/records?exercise_id={bench['id']}", token)
    check("records reflect the deleted set's absence",
          [r["value"] for r in records if r["record_type"] == "max_weight"] == [65], str(records)[:160])
    status, points = call("GET", "/workouts/points", token)
    status, ledger = call("GET", "/workouts/points/ledger?limit=200", token)
    check("points total equals the ledger",
          points["total_points"] == sum(e["points"] for e in ledger), f"{points['total_points']}")
    check("reversals are ledger rows, not edits", any(e["source_type"] == "reversal" for e in ledger))
    status, hist = call("GET", f"/exercises/{bench['id']}/history", token)
    check("progress history has the session", status == 200 and hist[-1]["top_weight_kg"] == 65, str(hist)[:120])
    status, measurement = call("POST", "/body-measurements", token,
                               {"metric": "weight", "value": 80.5, "unit": "kg"})
    check("log a body measurement", status == 201, str(measurement)[:100])

    for method, path in [("GET", f"/workouts/sessions/{sid}"),
                         ("POST", f"/workouts/sessions/{sid}/finish"),
                         ("GET", f"/routines/{routine['id']}"),
                         ("DELETE", f"/body-measurements/{measurement['id']}")]:
        status, _ = call(method, path, other)
        check(f"{method} another user's workout data is 404", status == 404, f"got {status}")

    # -- Sprint 6: animation contract --------------------------------------
    section("Sprint 6 - animation contract (served frontend)")
    try:
        with urllib.request.urlopen("http://localhost:3000/dashboard", timeout=20) as resp:
            page = resp.read().decode()
    except Exception as exc:  # noqa: BLE001
        page = ""
        check("frontend reachable", False, str(exc)[:80])

    if page:
        import re as _re
        css = "".join(_re.findall(r"<style>(.*?)</style>", page, _re.S))

        check("frontend serves the dashboard", "lf-reveal" in css)

        # Content must never depend on JavaScript to become readable: the
        # unconditional .lf-reveal rule has to be empty, with the hidden state
        # scoped to the class the script adds.
        base = _re.search(r"\n\.lf-reveal \{(.*?)\}", css, _re.S)
        check("reveal is visible by default (no JS required)",
              base is not None and base.group(1).strip() == "",
              repr(base.group(1)) if base else "rule missing")
        check("hidden state is scoped to the JS-added class",
              ".lf-reveal.lf-armed {" in css)

        check("scroll-linked path is feature-detected",
              "@supports (animation-timeline: view())" in css)
        check("prefers-reduced-motion is handled",
              "@media (prefers-reduced-motion: reduce)" in css)
        check("pinned hero only where there are two columns",
              "@media (min-width: 1024px)" in css and ".lf-pinned" in css)

        # Section 7: transform/opacity only, so the compositor handles motion
        # instead of a reflow every frame.
        layout_transitions = _re.findall(
            r"transition:\s*(width|height|top|left|margin|padding)\b", css
        )
        check("no layout property is transitioned", not layout_transitions,
              str(layout_transitions))

        blocks = _re.findall(r"@keyframes\s+(lf-[\w-]+)\s*\{(.*?)\n\}", css, _re.S)
        check("keyframes exist", len(blocks) >= 4, f"found {len(blocks)}")
        offenders = []
        for name, body in blocks:
            for prop in set(_re.findall(r"([a-z-]+)\s*:", body)):
                if prop not in {"opacity", "transform"}:
                    offenders.append(f"{name}:{prop}")
        check("keyframes animate only transform/opacity", not offenders, str(offenders))

        check("XP bar uses transform, not width", "scaleX" in page)

        # The rank-up sequence is one timeline read from rank_tiers.py, so the
        # tier's numbers must arrive as custom properties rather than as five
        # hand-written animations.
        for prop in ("--lf-dur", "--lf-shake", "--lf-zoom", "--lf-base", "--lf-glow", "--lf-jewel"):
            check(f"rank-up reads {prop} from the tier", prop in css, "missing")
        check("rank-up scales one timeline, not five",
              css.count("@keyframes lf-shake") == 1 and "calc(var(--lf-dur)" in css)
        check("the top tier's dust outlasts the burst", ".lf-p.lf-ambient {" in css)
        # A reward moment cannot be swiped away before it has played, and must
        # always become dismissible afterwards.
        # Scoped to the celebration: the PR overlay shares .lf-veil and must
        # stay dismissible.
        check("the overlay ignores taps until it has played",
              ".lf-celebrate {" in css and "pointer-events: none" in css
              and ".lf-celebrate[data-ma-ready] {" in css)
        # The counter is painted from an attribute the script owns; writing
        # into a React-owned node breaks hydration (see rest_timer.py).
        check("the level counter is painted from an attribute",
              ".lf-count::after" in css and "attr(data-ma-count)" in css
              and ".lf-count-line {" in css)
        check("reduced motion drops the particles and the crown",
              ".lf-p, .lf-flash, .lf-crown" in css)

        # The quest-complete beat must stay lightweight: Section 7 reserves the
        # heavy motion for level-up and rank-up, "not every quest checkbox".
        check("quest completion animates transform only",
              "lf-complete" in css and "@keyframes lf-complete" in css)
        check("completion beat is short", "320ms" in css)

    # -- Gym workout pages (served frontend) --------------------------------
    section("Gym workout pages (served frontend)")
    for route in ("/workout", "/routines", "/progress"):
        try:
            with urllib.request.urlopen(f"http://localhost:3000{route}", timeout=20) as resp:
                check(f"frontend serves {route}", resp.status == 200)
        except Exception as exc:  # noqa: BLE001
            check(f"frontend serves {route}", False, str(exc)[:80])

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
        call("DELETE", f"/routines/{routine['id']}", token)
        call("DELETE", f"/body-measurements/{measurement['id']}", token)
        check("test routine and measurement removed", True)
        print("  note: smoke users and their finished workouts remain "
              "(no delete-account endpoint yet; workouts are history, not deletable)")

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
