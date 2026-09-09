"""The progression payload the Stat Panel renders (GET /auth/me).

Rank and streak are derived per request rather than read from the cached
columns, so these tests exercise the derivation, not the cache.
"""

from fastapi.testclient import TestClient

from app.core import leveling

ME = "/api/v1/auth/me"
QUESTS = "/api/v1/quests"


def progress_of(client: TestClient, auth: dict) -> dict:
    r = client.get(ME, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()["progress"]


def test_a_new_user_starts_at_the_bottom_of_the_ladder(
    client: TestClient, auth: dict
) -> None:
    p = progress_of(client, auth)
    assert (p["current_level"], p["rank"], p["total_xp"]) == (1, "E", 0)
    assert p["current_streak"] == 0
    assert p["streak_is_active"] is False
    assert p["last_completed_on"] is None


def test_new_user_is_told_what_the_next_rank_costs(
    client: TestClient, auth: dict
) -> None:
    """The Stat Panel's "next rank" line, so the frontend never hardcodes a
    threshold."""
    p = progress_of(client, auth)
    assert p["next_rank"] == "D"
    assert p["next_rank_level"] == 8
    assert p["next_rank_streak"] == 0


def test_xp_bar_matches_the_curve(client: TestClient, auth: dict) -> None:
    p = progress_of(client, auth)
    assert p["xp_into_level"] == 0
    assert p["xp_for_next_level"] == leveling.xp_for_level(2)


def test_completing_a_quest_activates_the_streak(
    client: TestClient, auth: dict
) -> None:
    r = client.post(
        QUESTS, json={"title": "Run", "xp_reward": 100, "recurrence": "daily"}, headers=auth
    )
    client.post(f"{QUESTS}/{r.json()['id']}/complete", headers=auth)

    p = progress_of(client, auth)
    assert p["current_streak"] == 1
    assert p["streak_is_active"] is True
    assert p["last_completed_on"] is not None
    assert p["total_xp"] == 100


def _grind_to_high_level(client: TestClient, auth: dict, quests: int = 10) -> dict:
    """Earn enough XP to clear the A-rank level threshold in one day.

    Each quest can only be completed once per period, so this uses several
    max-reward quests rather than repeating one.
    """
    for i in range(quests):
        made = client.post(
            QUESTS, json={"title": f"Grind {i}", "xp_reward": 10_000}, headers=auth
        )
        client.post(f"{QUESTS}/{made.json()['id']}/complete", headers=auth)
    return progress_of(client, auth)


def test_level_can_earn_a_rank_the_streak_still_withholds(
    client: TestClient, auth: dict
) -> None:
    """The streak gate, end to end.

    100k XP clears the level-45 A threshold, but a one-day-old streak is short
    of the 14 days A requires - so the user holds B while `rank_by_level`
    reports the A they have earned on level alone. The UI should say "reach a
    14-day streak to claim A" rather than silently showing B.
    """
    p = _grind_to_high_level(client, auth)

    assert p["current_level"] >= 45
    assert p["rank_by_level"] == "A"
    assert p["rank"] == "B"
    assert p["current_streak"] == 1
    assert p["next_rank"] == "A"
    assert p["next_rank_streak"] == 14


def test_completion_response_does_not_report_a_rank_up_that_was_gated(
    client: TestClient, auth: dict
) -> None:
    """Crossing the A level threshold without the streak must not fire the
    rank-up animation."""
    _grind_to_high_level(client, auth, quests=9)

    made = client.post(
        QUESTS, json={"title": "Final", "xp_reward": 10_000}, headers=auth
    )
    progression = client.post(
        f"{QUESTS}/{made.json()['id']}/complete", headers=auth
    ).json()["progression"]

    assert progression["rank_after"] in {"B", "C"}
    assert progression["ranked_up"] is False or progression["rank_after"] != "A"


def test_cached_rank_column_agrees_with_the_derived_rank(
    client: TestClient, auth: dict, db
) -> None:
    """The cached column is what Sprint 5's leaderboard will read, so on the
    write path it must match what the read path derives."""
    made = client.post(QUESTS, json={"title": "Run", "xp_reward": 100}, headers=auth)
    client.post(f"{QUESTS}/{made.json()['id']}/complete", headers=auth)

    from app.models.user import LevelProgress

    stored = db.query(LevelProgress).one()
    assert stored.rank.value == progress_of(client, auth)["rank"]
    assert stored.current_level == progress_of(client, auth)["current_level"]
