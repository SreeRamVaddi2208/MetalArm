"""Profile page: lifetime stats and badges."""

from fastapi.testclient import TestClient

from app.core import badges as badge_rules

PROFILE = "/api/v1/profile"
QUESTS = "/api/v1/quests"
REWARDS = "/api/v1/rewards"
PARTIES = "/api/v1/parties"


def complete_quest(client: TestClient, auth: dict, xp: int = 50, points: int = 0) -> None:
    q = client.post(
        QUESTS, json={"title": "Task", "xp_reward": xp, "points_reward": points}, headers=auth
    ).json()
    r = client.post(f"{QUESTS}/{q['id']}/complete", headers=auth)
    assert r.status_code == 200, r.text


def badge(profile: dict, badge_id: str) -> dict:
    return next(b for b in profile["badges"] if b["id"] == badge_id)


def test_profile_requires_auth(client: TestClient) -> None:
    assert client.get(PROFILE).status_code == 401


def test_a_new_profile_is_empty_but_complete(client: TestClient, auth: dict) -> None:
    p = client.get(PROFILE, headers=auth).json()
    assert p["progress"]["current_level"] == 1
    assert p["stats"]["quests_completed"] == 0
    assert p["badges_earned"] == 0
    # Unearned badges are still listed, so the panel can show what is close.
    assert p["badges_total"] == len(p["badges"]) > 0
    assert all(b["earned"] is False for b in p["badges"])


def test_completing_a_quest_earns_the_first_badge(
    client: TestClient, auth: dict
) -> None:
    complete_quest(client, auth)
    p = client.get(PROFILE, headers=auth).json()
    assert badge(p, "first_quest")["earned"] is True
    assert p["badges_earned"] == 1
    assert p["stats"]["quests_completed"] == 1


def test_unearned_badges_report_progress(client: TestClient, auth: dict) -> None:
    """A panel that only lists what you have gives you nothing to aim at."""
    for _ in range(3):
        complete_quest(client, auth)
    ten = badge(client.get(PROFILE, headers=auth).json(), "ten_quests")
    assert ten["earned"] is False
    assert ten["progress"] == 3
    assert ten["target"] == 10
    assert ten["percent"] == 30


def test_lifetime_stats_track_points(client: TestClient, auth: dict) -> None:
    complete_quest(client, auth, points=100)
    reward = client.post(
        REWARDS, json={"title": "Treat", "point_cost": 40}, headers=auth
    ).json()
    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)

    stats = client.get(PROFILE, headers=auth).json()["stats"]
    assert stats["points_earned"] == 100
    assert stats["points_spent"] == 40
    assert stats["rewards_redeemed"] == 1


def test_party_activity_counts_toward_the_profile(
    client: TestClient, auth: dict
) -> None:
    party = client.post(PARTIES, json={"name": "Guild"}, headers=auth).json()
    quest = client.post(
        f"{PARTIES}/{party['id']}/quests",
        json={"title": "Raid", "xp_reward": 120},
        headers=auth,
    ).json()
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=auth)

    p = client.get(PROFILE, headers=auth).json()
    assert p["stats"]["parties_joined"] == 1
    assert p["stats"]["party_quests_completed"] == 1
    assert p["stats"]["party_xp_contributed"] == 120
    assert badge(p, "party_member")["earned"] is True
    # Party quests are quests too - excluding them would make the counters
    # disagree with what the user actually did.
    assert badge(p, "first_quest")["earned"] is True


def test_profile_rank_matches_the_stat_panel(client: TestClient, auth: dict) -> None:
    complete_quest(client, auth)
    profile = client.get(PROFILE, headers=auth).json()
    me = client.get("/api/v1/auth/me", headers=auth).json()
    assert profile["progress"]["rank"] == me["progress"]["rank"]
    assert profile["progress"]["current_level"] == me["progress"]["current_level"]
    assert profile["progress"]["total_xp"] == me["progress"]["total_xp"]


# --------------------------------------------------------------------------
# Badge rules (pure)
# --------------------------------------------------------------------------


def test_badges_key_off_values_that_never_decrease() -> None:
    """Losing a streak must not revoke a badge that was genuinely earned, so
    the rule reads longest_streak, not the current one."""
    earned = badge_rules.evaluate(badge_rules.BadgeInputs(longest_streak=30))
    ids = {b.id for b in earned if b.earned}
    assert {"streak_7", "streak_30"} <= ids
    assert "streak_100" not in ids


def test_badge_percent_is_clamped() -> None:
    over = badge_rules.evaluate(badge_rules.BadgeInputs(quests_completed=10_000))
    for b in over:
        assert 0 <= b.percent <= 100
        assert b.progress <= b.target


def test_every_badge_has_a_distinct_id() -> None:
    all_badges = badge_rules.evaluate(badge_rules.BadgeInputs())
    ids = [b.id for b in all_badges]
    assert len(ids) == len(set(ids))
