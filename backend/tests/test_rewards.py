"""Rewards shop: CRUD, ownership, and the spend path."""

import pytest
from fastapi.testclient import TestClient

REWARDS = "/api/v1/rewards"
QUESTS = "/api/v1/quests"
ME = "/api/v1/auth/me"


def make_reward(client: TestClient, auth: dict, **overrides) -> dict:
    payload = {"title": "Order takeout", "point_cost": 50}
    payload.update(overrides)
    r = client.post(REWARDS, json=payload, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def earn_points(client: TestClient, auth: dict, points: int) -> None:
    """Points enter the wallet only by completing a quest."""
    quest = client.post(
        QUESTS,
        json={"title": f"Earn {points}", "xp_reward": 0, "points_reward": points},
        headers=auth,
    ).json()
    r = client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    assert r.status_code == 200, r.text


def balance_of(client: TestClient, auth: dict) -> int:
    return client.get(ME, headers=auth).json()["progress"]["points_balance"]


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------


def test_reward_endpoints_require_auth(client: TestClient) -> None:
    assert client.get(REWARDS).status_code == 401
    assert client.post(REWARDS, json={"title": "x", "point_cost": 1}).status_code == 401


def test_create_and_list(client: TestClient, auth: dict) -> None:
    made = make_reward(client, auth)
    listed = client.get(REWARDS, headers=auth).json()
    assert [r["id"] for r in listed] == [made["id"]]
    assert listed[0]["times_redeemed"] == 0


def test_zero_cost_reward_is_rejected(client: TestClient, auth: dict) -> None:
    """A free reward would be an infinite loop."""
    r = client.post(REWARDS, json={"title": "Free", "point_cost": 0}, headers=auth)
    assert r.status_code == 422


def test_negative_cost_is_rejected(client: TestClient, auth: dict) -> None:
    r = client.post(REWARDS, json={"title": "Paid", "point_cost": -10}, headers=auth)
    assert r.status_code == 422


def test_affordable_tracks_the_balance(client: TestClient, auth: dict) -> None:
    make_reward(client, auth, point_cost=50)
    assert client.get(REWARDS, headers=auth).json()[0]["affordable"] is False

    earn_points(client, auth, 50)
    assert client.get(REWARDS, headers=auth).json()[0]["affordable"] is True


def test_deactivated_rewards_are_hidden_by_default(client: TestClient, auth: dict) -> None:
    reward = make_reward(client, auth)
    client.patch(f"{REWARDS}/{reward['id']}", json={"is_active": False}, headers=auth)

    assert client.get(REWARDS, headers=auth).json() == []
    shown = client.get(f"{REWARDS}?include_inactive=true", headers=auth).json()
    assert [r["id"] for r in shown] == [reward["id"]]


def test_patch_leaves_unset_fields_untouched(client: TestClient, auth: dict) -> None:
    reward = make_reward(client, auth, title="Takeout", point_cost=50)
    r = client.patch(f"{REWARDS}/{reward['id']}", json={"point_cost": 75}, headers=auth)
    assert r.json()["point_cost"] == 75
    assert r.json()["title"] == "Takeout"


def test_delete_an_unredeemed_reward(client: TestClient, auth: dict) -> None:
    reward = make_reward(client, auth)
    assert client.delete(f"{REWARDS}/{reward['id']}", headers=auth).status_code == 204
    assert client.get(f"{REWARDS}/{reward['id']}", headers=auth).status_code == 404


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def test_a_users_shop_shows_only_their_own_rewards(
    client: TestClient, user_factory
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    make_reward(client, alice)
    assert client.get(REWARDS, headers=bob).json() == []


def test_another_users_reward_is_404(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    reward = make_reward(client, alice)
    url = f"{REWARDS}/{reward['id']}"

    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"point_cost": 1}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.post(f"{url}/redeem", headers=bob).status_code == 404


def test_a_user_cannot_spend_another_users_points(
    client: TestClient, user_factory
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    earn_points(client, alice, 500)
    reward = make_reward(client, alice, point_cost=50)

    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=bob)
    assert balance_of(client, alice) == 500


# --------------------------------------------------------------------------
# Spending
# --------------------------------------------------------------------------


def test_redeeming_debits_the_balance(client: TestClient, auth: dict) -> None:
    earn_points(client, auth, 100)
    reward = make_reward(client, auth, point_cost=40)

    r = client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["points_balance"] == 60
    assert body["redemption"]["points_spent"] == 40
    assert body["redemption"]["reward_title"] == "Order takeout"
    assert balance_of(client, auth) == 60


def test_redeeming_without_enough_points_is_rejected(
    client: TestClient, auth: dict
) -> None:
    earn_points(client, auth, 10)
    reward = make_reward(client, auth, point_cost=50)

    r = client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)
    assert r.status_code == 409
    assert "Insufficient" in r.json()["detail"]
    # The rejected attempt must not have moved anything.
    assert balance_of(client, auth) == 10


def test_balance_can_reach_exactly_zero(client: TestClient, auth: dict) -> None:
    earn_points(client, auth, 50)
    reward = make_reward(client, auth, point_cost=50)

    assert client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth).status_code == 200
    assert balance_of(client, auth) == 0
    # ...and the next attempt fails rather than going negative.
    assert client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth).status_code == 409


def test_spending_repeatedly_cannot_overdraw(client: TestClient, auth: dict) -> None:
    """Sequential guard. The concurrent case is closed by the row lock plus
    CHECK (points_balance >= 0) and is exercised live, not here - TestClient
    runs in-process against a single session."""
    earn_points(client, auth, 100)
    reward = make_reward(client, auth, point_cost=30)

    codes = [
        client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth).status_code
        for _ in range(5)
    ]
    assert codes == [200, 200, 200, 409, 409]
    assert balance_of(client, auth) == 10


def test_a_deactivated_reward_cannot_be_redeemed(client: TestClient, auth: dict) -> None:
    earn_points(client, auth, 100)
    reward = make_reward(client, auth, point_cost=50)
    client.patch(f"{REWARDS}/{reward['id']}", json={"is_active": False}, headers=auth)

    r = client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)
    assert r.status_code == 409
    assert balance_of(client, auth) == 100


def test_repricing_does_not_rewrite_spend_history(client: TestClient, auth: dict) -> None:
    """points_spent is snapshotted, so the ledger keeps the price actually
    paid."""
    earn_points(client, auth, 200)
    reward = make_reward(client, auth, point_cost=40)
    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)
    client.patch(f"{REWARDS}/{reward['id']}", json={"point_cost": 150}, headers=auth)

    history = client.get(f"{REWARDS}/redemptions", headers=auth).json()
    assert history[0]["points_spent"] == 40


def test_redeemed_reward_cannot_be_deleted(client: TestClient, auth: dict) -> None:
    """ON DELETE RESTRICT: deleting would erase the record of points spent.
    Must be a clean 409, not a 500 from the database."""
    earn_points(client, auth, 100)
    reward = make_reward(client, auth, point_cost=40)
    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)

    r = client.delete(f"{REWARDS}/{reward['id']}", headers=auth)
    assert r.status_code == 409
    assert "Deactivate" in r.json()["detail"]

    # The documented alternative works and hides it from the shop.
    assert client.patch(
        f"{REWARDS}/{reward['id']}", json={"is_active": False}, headers=auth
    ).status_code == 200
    assert client.get(REWARDS, headers=auth).json() == []


def test_times_redeemed_is_counted(client: TestClient, auth: dict) -> None:
    earn_points(client, auth, 200)
    reward = make_reward(client, auth, point_cost=40)
    for _ in range(3):
        client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)

    assert client.get(REWARDS, headers=auth).json()[0]["times_redeemed"] == 3


# --------------------------------------------------------------------------
# Wallet and history
# --------------------------------------------------------------------------


def test_wallet_reports_earned_spent_and_balance(client: TestClient, auth: dict) -> None:
    earn_points(client, auth, 100)
    earn_points(client, auth, 50)
    reward = make_reward(client, auth, point_cost=40)
    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)

    wallet = client.get(f"{REWARDS}/wallet", headers=auth).json()
    assert wallet["total_points_earned"] == 150
    assert wallet["total_points_spent"] == 40
    # The balance must reconcile against the two histories.
    assert wallet["points_balance"] == 110
    assert (
        wallet["points_balance"]
        == wallet["total_points_earned"] - wallet["total_points_spent"]
    )


def test_new_wallet_is_empty(client: TestClient, auth: dict) -> None:
    wallet = client.get(f"{REWARDS}/wallet", headers=auth).json()
    assert wallet == {
        "points_balance": 0,
        "total_points_earned": 0,
        "total_points_spent": 0,
    }


def test_redemption_history_is_newest_first(client: TestClient, auth: dict) -> None:
    earn_points(client, auth, 500)
    cheap = make_reward(client, auth, title="Cheap", point_cost=10)
    dear = make_reward(client, auth, title="Dear", point_cost=100)
    client.post(f"{REWARDS}/{cheap['id']}/redeem", headers=auth)
    client.post(f"{REWARDS}/{dear['id']}/redeem", headers=auth)

    history = client.get(f"{REWARDS}/redemptions", headers=auth).json()
    assert [h["reward_title"] for h in history] == ["Dear", "Cheap"]


def test_history_is_scoped_to_the_caller(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    earn_points(client, alice, 100)
    reward = make_reward(client, alice, point_cost=40)
    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=alice)

    assert client.get(f"{REWARDS}/redemptions", headers=bob).json() == []


@pytest.mark.parametrize("literal", ["wallet", "redemptions"])
def test_literal_routes_are_not_swallowed_by_the_uuid_route(
    client: TestClient, auth: dict, literal: str
) -> None:
    """Route ORDER regression guard. Declared after /{reward_id}, these would
    be parsed as a UUID and 422 instead of resolving."""
    r = client.get(f"{REWARDS}/{literal}", headers=auth)
    assert r.status_code == 200


def test_wallet_totals_do_not_reconcile_after_a_quest_is_deleted(
    client: TestClient, auth: dict
) -> None:
    """Documents a real, intended asymmetry.

    Deleting a quest cascades its completions away, so total_points_earned
    drops - but the balance does not, because those points were genuinely
    earned and may already be spent. The UI must render points_balance, never
    `earned - spent`.
    """
    quest = client.post(
        QUESTS,
        json={"title": "Earn", "xp_reward": 0, "points_reward": 100},
        headers=auth,
    ).json()
    client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    reward = make_reward(client, auth, point_cost=80)
    client.post(f"{REWARDS}/{reward['id']}/redeem", headers=auth)

    client.delete(f"{QUESTS}/{quest['id']}", headers=auth)

    wallet = client.get(f"{REWARDS}/wallet", headers=auth).json()
    assert wallet["points_balance"] == 20      # authoritative, unchanged
    assert wallet["total_points_earned"] == 0  # history cascaded away
    assert wallet["total_points_spent"] == 80  # RESTRICT keeps redemptions
