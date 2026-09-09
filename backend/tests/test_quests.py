"""Quest CRUD, ownership isolation, and the completion invariants."""

from fastapi.testclient import TestClient

QUESTS = "/api/v1/quests"
ME = "/api/v1/auth/me"


def make_quest(client: TestClient, auth: dict, **overrides) -> dict:
    payload = {"title": "Morning run", "xp_reward": 100, "points_reward": 5}
    payload.update(overrides)
    r = client.post(QUESTS, json=payload, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------


def test_quest_endpoints_require_auth(client: TestClient) -> None:
    assert client.get(QUESTS).status_code == 401
    assert client.post(QUESTS, json={"title": "x"}).status_code == 401


def test_create_and_list(client: TestClient, auth: dict) -> None:
    made = make_quest(client, auth, title="Morning run")
    listed = client.get(QUESTS, headers=auth).json()
    assert [q["id"] for q in listed] == [made["id"]]
    assert listed[0]["completed_in_current_period"] is False


def test_xp_reward_over_the_cap_is_rejected(client: TestClient, auth: dict) -> None:
    """Bounded so a self-authored quest cannot mint arbitrary XP."""
    r = client.post(QUESTS, json={"title": "Cheat", "xp_reward": 999_999}, headers=auth)
    assert r.status_code == 422


def test_unsupported_recurrence_is_rejected(client: TestClient, auth: dict) -> None:
    r = client.post(QUESTS, json={"title": "M", "recurrence": "monthly"}, headers=auth)
    assert r.status_code == 422


def test_patch_leaves_unset_fields_untouched(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth, description="5km")
    r = client.patch(f"{QUESTS}/{quest['id']}", json={"title": "New title"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["title"] == "New title"
    # The whole point of exclude_unset: an unrelated edit must not wipe this.
    assert r.json()["description"] == "5km"


def test_patch_can_explicitly_clear_a_field(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth, description="5km")
    r = client.patch(f"{QUESTS}/{quest['id']}", json={"description": None}, headers=auth)
    assert r.json()["description"] is None


def test_delete_then_get_is_404(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth)
    assert client.delete(f"{QUESTS}/{quest['id']}", headers=auth).status_code == 204
    assert client.get(f"{QUESTS}/{quest['id']}", headers=auth).status_code == 404


def test_archived_quests_are_hidden_by_default(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth)
    client.patch(f"{QUESTS}/{quest['id']}", json={"status": "archived"}, headers=auth)

    assert client.get(QUESTS, headers=auth).json() == []
    archived = client.get(f"{QUESTS}?status=archived", headers=auth).json()
    assert [q["id"] for q in archived] == [quest["id"]]


# --------------------------------------------------------------------------
# Ownership isolation
# --------------------------------------------------------------------------


def test_a_users_board_shows_only_their_own_quests(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    make_quest(client, alice, title="Alice's quest")
    assert client.get(QUESTS, headers=bob).json() == []


def test_another_users_quest_is_404_not_403(client: TestClient, user_factory) -> None:
    """404 rather than 403: a 403 would confirm the ID exists and allow
    enumeration of other users' quests."""
    alice, _ = user_factory()
    bob, _ = user_factory()
    quest = make_quest(client, alice)
    url = f"{QUESTS}/{quest['id']}"

    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"xp_reward": 9999}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.post(f"{url}/complete", headers=bob).status_code == 404


def test_a_user_cannot_earn_xp_from_another_users_quest(
    client: TestClient, user_factory
) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    quest = make_quest(client, alice, xp_reward=500)

    client.post(f"{QUESTS}/{quest['id']}/complete", headers=bob)
    assert client.get(ME, headers=bob).json()["progress"]["total_xp"] == 0


# --------------------------------------------------------------------------
# Completion
# --------------------------------------------------------------------------


def test_completing_awards_xp_and_points(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth, xp_reward=120, points_reward=10)
    r = client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    assert r.status_code == 200

    progression = r.json()["progression"]
    assert progression["xp_awarded"] == 120
    assert progression["total_xp"] == 120
    assert progression["current_streak"] == 1

    progress = client.get(ME, headers=auth).json()["progress"]
    assert progress["total_xp"] == 120
    assert progress["points_balance"] == 10


def test_completing_twice_in_the_same_period_is_rejected(
    client: TestClient, auth: dict
) -> None:
    """The UNIQUE(quest_id, user_id, period_key) constraint - the only real
    defense against XP farming by double-submitting."""
    quest = make_quest(client, auth, xp_reward=100, recurrence="daily")
    assert client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth).status_code == 200

    second = client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    assert second.status_code == 409

    # The rejected attempt must not have awarded anything.
    assert client.get(ME, headers=auth).json()["progress"]["total_xp"] == 100


def test_a_one_off_quest_cannot_be_completed_twice(client: TestClient, auth: dict) -> None:
    """Guards the 'once' sentinel: a NULL period_key would satisfy UNIQUE an
    unlimited number of times, since NULL never equals NULL."""
    quest = make_quest(client, auth, recurrence="none")
    assert client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth).status_code == 200
    assert client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth).status_code == 409


def test_board_reflects_completion_for_the_current_period(
    client: TestClient, auth: dict
) -> None:
    quest = make_quest(client, auth, recurrence="daily")
    client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    assert client.get(QUESTS, headers=auth).json()[0]["completed_in_current_period"] is True


def test_archived_quests_cannot_be_completed(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth)
    client.patch(f"{QUESTS}/{quest['id']}", json={"status": "archived"}, headers=auth)
    assert client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth).status_code == 409


def test_editing_the_reward_does_not_rewrite_past_awards(
    client: TestClient, auth: dict
) -> None:
    """xp_awarded is snapshotted at completion time, so raising a quest's
    reward cannot retroactively inflate earned XP."""
    quest = make_quest(client, auth, xp_reward=100)
    client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    client.patch(f"{QUESTS}/{quest['id']}", json={"xp_reward": 5000}, headers=auth)

    assert client.get(ME, headers=auth).json()["progress"]["total_xp"] == 100


def test_level_up_is_reported_on_the_completion_response(
    client: TestClient, auth: dict
) -> None:
    """The client must not have to infer a level-up by diffing two responses -
    this flag is what triggers the Section 7 animation."""
    quest = make_quest(client, auth, xp_reward=120)
    progression = client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth).json()[
        "progression"
    ]
    assert progression["level_before"] == 1
    assert progression["level_after"] == 2
    assert progression["leveled_up"] is True
    assert progression["ranked_up"] is False


def test_no_level_up_below_the_threshold(client: TestClient, auth: dict) -> None:
    quest = make_quest(client, auth, xp_reward=10)
    progression = client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth).json()[
        "progression"
    ]
    assert progression["leveled_up"] is False


def test_deleting_a_quest_does_not_claw_back_earned_xp(
    client: TestClient, auth: dict
) -> None:
    quest = make_quest(client, auth, xp_reward=100)
    client.post(f"{QUESTS}/{quest['id']}/complete", headers=auth)
    client.delete(f"{QUESTS}/{quest['id']}", headers=auth)

    # total_xp is cumulative and the XP was legitimately earned.
    assert client.get(ME, headers=auth).json()["progress"]["total_xp"] == 100
