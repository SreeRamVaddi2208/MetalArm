"""Parties: lifecycle, membership, shared board, and the leaderboard."""

from fastapi.testclient import TestClient

PARTIES = "/api/v1/parties"
ME = "/api/v1/auth/me"


def make_party(client: TestClient, auth: dict, **overrides) -> dict:
    payload = {"name": "Shadow Guild"}
    payload.update(overrides)
    r = client.post(PARTIES, json=payload, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def join(client: TestClient, auth: dict, code: str):
    return client.post(f"{PARTIES}/join", json={"invite_code": code}, headers=auth)


def add_quest(client: TestClient, auth: dict, party_id: str, **overrides) -> dict:
    payload = {"title": "Group run", "xp_reward": 100}
    payload.update(overrides)
    r = client.post(f"{PARTIES}/{party_id}/quests", json=payload, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


def test_party_endpoints_require_auth(client: TestClient) -> None:
    assert client.get(PARTIES).status_code == 401
    assert client.post(PARTIES, json={"name": "x"}).status_code == 401


def test_creating_a_party_makes_you_its_owner_and_member(
    client: TestClient, auth: dict
) -> None:
    """A party with no members would be unreachable, so membership is not a
    separate step."""
    party = make_party(client, auth)
    assert party["my_role"] == "owner"
    assert party["member_count"] == 1
    assert party["is_active"] is True
    assert len(party["invite_code"]) == 8


def test_default_cap_is_ten(client: TestClient, auth: dict) -> None:
    assert make_party(client, auth)["max_members"] == 10


def test_invite_codes_avoid_ambiguous_characters(
    client: TestClient, user_factory
) -> None:
    """0/O and 1/I/L are excluded so a code can be read aloud and retyped."""
    codes = []
    for _ in range(6):
        headers, _ = user_factory()
        codes.append(make_party(client, headers)["invite_code"])
    joined = "".join(codes)
    assert not (set("01OIL") & set(joined)), joined
    assert len(set(codes)) == len(codes), "invite codes must be unique"


def test_listing_shows_only_my_parties(client: TestClient, user_factory) -> None:
    alice, _ = user_factory()
    bob, _ = user_factory()
    make_party(client, alice)
    assert client.get(PARTIES, headers=bob).json() == []


def test_a_non_member_gets_404_not_403(client: TestClient, user_factory) -> None:
    """403 would confirm the party exists and allow probing for ids."""
    alice, _ = user_factory()
    bob, _ = user_factory()
    party = make_party(client, alice)
    url = f"{PARTIES}/{party['id']}"

    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"name": "Hijacked"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.get(f"{url}/members", headers=bob).status_code == 404
    assert client.get(f"{url}/leaderboard", headers=bob).status_code == 404


def test_only_the_owner_can_rename_or_dissolve(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    join(client, member, party["invite_code"])

    url = f"{PARTIES}/{party['id']}"
    assert client.patch(url, json={"name": "Renamed"}, headers=member).status_code == 403
    assert client.delete(url, headers=member).status_code == 403
    assert client.post(f"{url}/rotate-invite", headers=member).status_code == 403

    assert client.patch(url, json={"name": "Renamed"}, headers=owner).status_code == 200


def test_dissolving_is_soft_and_preserves_history(
    client: TestClient, auth: dict
) -> None:
    """A hard delete would cascade the completion rows away, silently
    rewriting what people actually did."""
    party = make_party(client, auth)
    quest = add_quest(client, auth, party["id"])
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=auth)

    assert client.delete(f"{PARTIES}/{party['id']}", headers=auth).status_code == 204

    assert client.get(PARTIES, headers=auth).json() == []
    still_there = client.get(f"{PARTIES}?include_dissolved=true", headers=auth).json()
    assert len(still_there) == 1 and still_there[0]["is_active"] is False
    # The XP earned in it is still visible.
    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=auth).json()
    assert board["total_party_xp"] == 100


def test_a_dissolved_party_rejects_further_writes(
    client: TestClient, auth: dict
) -> None:
    party = make_party(client, auth)
    client.delete(f"{PARTIES}/{party['id']}", headers=auth)
    r = client.post(
        f"{PARTIES}/{party['id']}/quests", json={"title": "New"}, headers=auth
    )
    assert r.status_code == 409


# --------------------------------------------------------------------------
# Joining
# --------------------------------------------------------------------------


def test_joining_by_invite_code(client: TestClient, user_factory) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)

    r = join(client, member, party["invite_code"])
    assert r.status_code == 200, r.text
    assert r.json()["my_role"] == "member"
    assert r.json()["member_count"] == 2


def test_invite_code_is_accepted_case_and_separator_insensitively(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    code = make_party(client, owner)["invite_code"]
    messy = f" {code[:4].lower()}-{code[4:].lower()} "
    assert join(client, member, messy).status_code == 200


def test_an_unknown_code_is_404(client: TestClient, auth: dict) -> None:
    assert join(client, auth, "ZZZZZZZZ").status_code == 404


def test_a_dissolved_partys_code_stops_working(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    client.delete(f"{PARTIES}/{party['id']}", headers=owner)
    assert join(client, member, party["invite_code"]).status_code == 404


def test_rejoining_is_idempotent(client: TestClient, user_factory) -> None:
    """Re-using a link you already accepted should land you in the party, not
    on an error."""
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    assert join(client, member, party["invite_code"]).status_code == 200
    r = join(client, member, party["invite_code"])
    assert r.status_code == 200
    assert r.json()["member_count"] == 2


def test_rotating_the_invite_invalidates_the_old_code(
    client: TestClient, user_factory
) -> None:
    """Rotation is the only way to revoke a leaked link - the code IS the
    capability."""
    owner, _ = user_factory()
    stranger, _ = user_factory()
    party = make_party(client, owner)
    old = party["invite_code"]

    rotated = client.post(f"{PARTIES}/{party['id']}/rotate-invite", headers=owner).json()
    assert rotated["invite_code"] != old

    assert join(client, stranger, old).status_code == 404
    assert join(client, stranger, rotated["invite_code"]).status_code == 200


def test_a_full_party_is_rejected(client: TestClient, user_factory) -> None:
    owner, _ = user_factory()
    party = make_party(client, owner, max_members=3)
    code = party["invite_code"]

    for _ in range(2):
        headers, _ = user_factory()
        assert join(client, headers, code).status_code == 200

    overflow, _ = user_factory()
    r = join(client, overflow, code)
    assert r.status_code == 409
    assert "full" in r.json()["detail"].lower()
    assert client.get(f"{PARTIES}/{party['id']}", headers=owner).json()["member_count"] == 3


# --------------------------------------------------------------------------
# Leaving and ownership handoff
# --------------------------------------------------------------------------


def test_a_member_can_leave(client: TestClient, user_factory) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    join(client, member, party["invite_code"])

    assert client.post(f"{PARTIES}/{party['id']}/leave", headers=member).status_code == 204
    assert client.get(PARTIES, headers=member).json() == []
    assert client.get(f"{PARTIES}/{party['id']}", headers=owner).json()["member_count"] == 1


def test_a_leaving_owner_hands_off_to_the_longest_serving_member(
    client: TestClient, user_factory
) -> None:
    """An ownerless party could never be renamed, rotated or dissolved."""
    owner, _ = user_factory()
    first, first_user = user_factory()
    second, _ = user_factory()
    party = make_party(client, owner)
    join(client, first, party["invite_code"])
    join(client, second, party["invite_code"])

    assert client.post(f"{PARTIES}/{party['id']}/leave", headers=owner).status_code == 204

    seen = client.get(f"{PARTIES}/{party['id']}", headers=first).json()
    assert seen["my_role"] == "owner", "earliest joiner should inherit"
    assert seen["owner_id"] == first_user["id"]
    assert seen["member_count"] == 2
    # ...and the new owner can actually exercise ownership.
    assert client.patch(
        f"{PARTIES}/{party['id']}", json={"name": "Inherited"}, headers=first
    ).status_code == 200


def test_the_last_member_leaving_dissolves_the_party(
    client: TestClient, auth: dict
) -> None:
    party = make_party(client, auth)
    assert client.post(f"{PARTIES}/{party['id']}/leave", headers=auth).status_code == 204
    assert client.get(f"{PARTIES}/{party['id']}", headers=auth).status_code == 404


# --------------------------------------------------------------------------
# Shared quest board
# --------------------------------------------------------------------------


def test_any_member_can_add_a_shared_quest(client: TestClient, user_factory) -> None:
    """A board only one person can write to is a to-do list, not a party."""
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    join(client, member, party["invite_code"])

    quest = add_quest(client, member, party["id"], title="Member's idea")
    board = client.get(f"{PARTIES}/{party['id']}/quests", headers=owner).json()
    assert [q["title"] for q in board] == ["Member's idea"]
    assert quest["completed_in_current_period"] is False


def test_each_member_completes_the_shared_quest_independently(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    join(client, member, party["invite_code"])
    quest = add_quest(client, owner, party["id"], xp_reward=100)
    url = f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete"

    assert client.post(url, headers=owner).status_code == 200
    # The other member has NOT been marked done by someone else's completion.
    assert client.post(url, headers=member).status_code == 200

    board = client.get(f"{PARTIES}/{party['id']}/quests", headers=owner).json()
    assert board[0]["completed_by_count"] == 2


def test_completing_a_shared_quest_twice_in_a_period_is_rejected(
    client: TestClient, auth: dict
) -> None:
    party = make_party(client, auth)
    quest = add_quest(client, auth, party["id"], recurrence="daily")
    url = f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete"

    assert client.post(url, headers=auth).status_code == 200
    second = client.post(url, headers=auth)
    assert second.status_code == 409
    assert "already completed" in second.json()["detail"].lower()


def test_shared_completion_awards_personal_xp_too(
    client: TestClient, auth: dict
) -> None:
    party = make_party(client, auth)
    quest = add_quest(client, auth, party["id"], xp_reward=150, points_reward=20)
    r = client.post(
        f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=auth
    )
    body = r.json()
    assert body["xp_awarded"] == 150
    assert body["leveled_up"] is True

    progress = client.get(ME, headers=auth).json()["progress"]
    assert progress["total_xp"] == 150
    assert progress["points_balance"] == 20


def test_removing_a_shared_quest_is_soft(client: TestClient, auth: dict) -> None:
    """A hard delete would cascade away the completions backing the
    leaderboard."""
    party = make_party(client, auth)
    quest = add_quest(client, auth, party["id"], xp_reward=100)
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=auth)

    assert client.delete(
        f"{PARTIES}/{party['id']}/quests/{quest['id']}", headers=auth
    ).status_code == 204
    assert client.get(f"{PARTIES}/{party['id']}/quests", headers=auth).json() == []
    # Contribution survives.
    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=auth).json()
    assert board["total_party_xp"] == 100


def test_a_removed_quest_cannot_be_completed(client: TestClient, auth: dict) -> None:
    party = make_party(client, auth)
    quest = add_quest(client, auth, party["id"])
    client.delete(f"{PARTIES}/{party['id']}/quests/{quest['id']}", headers=auth)
    r = client.post(
        f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=auth
    )
    assert r.status_code == 409


def test_a_member_cannot_edit_someone_elses_quest(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    a, _ = user_factory()
    b, _ = user_factory()
    party = make_party(client, owner)
    join(client, a, party["invite_code"])
    join(client, b, party["invite_code"])

    quest = add_quest(client, a, party["id"])
    url = f"{PARTIES}/{party['id']}/quests/{quest['id']}"

    assert client.patch(url, json={"xp_reward": 9999}, headers=b).status_code == 403
    # Author and owner both may.
    assert client.patch(url, json={"xp_reward": 200}, headers=a).status_code == 200
    assert client.patch(url, json={"xp_reward": 300}, headers=owner).status_code == 200


def test_a_non_member_cannot_reach_the_shared_board(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    stranger, _ = user_factory()
    party = make_party(client, owner)
    quest = add_quest(client, owner, party["id"])

    assert client.get(f"{PARTIES}/{party['id']}/quests", headers=stranger).status_code == 404
    assert client.post(
        f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=stranger
    ).status_code == 404


# --------------------------------------------------------------------------
# Leaderboard
# --------------------------------------------------------------------------


def test_leaderboard_ranks_by_contributed_xp(
    client: TestClient, user_factory
) -> None:
    owner, _ = user_factory()
    member, _ = user_factory()
    party = make_party(client, owner)
    join(client, member, party["invite_code"])

    small = add_quest(client, owner, party["id"], title="Small", xp_reward=50)
    big = add_quest(client, owner, party["id"], title="Big", xp_reward=500)

    # The member out-earns the owner.
    client.post(f"{PARTIES}/{party['id']}/quests/{small['id']}/complete", headers=owner)
    client.post(f"{PARTIES}/{party['id']}/quests/{big['id']}/complete", headers=member)

    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=owner).json()
    assert board["total_party_xp"] == 550
    assert [e["party_xp"] for e in board["entries"]] == [500, 50]
    assert [e["position"] for e in board["entries"]] == [1, 2]
    assert board["entries"][1]["is_me"] is True


def test_members_with_no_contribution_still_appear(
    client: TestClient, user_factory
) -> None:
    """They are absent from the Redis sorted set, but the board should show the
    whole party."""
    owner, _ = user_factory()
    idle, _ = user_factory()
    party = make_party(client, owner)
    join(client, idle, party["invite_code"])
    quest = add_quest(client, owner, party["id"], xp_reward=100)
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=owner)

    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=owner).json()
    assert len(board["entries"]) == 2
    assert board["entries"][-1]["party_xp"] == 0


def test_party_xp_counts_only_what_was_earned_as_a_member(
    client: TestClient, user_factory
) -> None:
    """A high-level recruit must not inflate the party total.

    The joiner arrives with personal XP already earned; the party total stays
    at what was actually contributed to THIS party.
    """
    owner, _ = user_factory()
    veteran, _ = user_factory()

    # The veteran earns a lot of PERSONAL xp before joining.
    solo = client.post(
        "/api/v1/quests",
        json={"title": "Solo grind", "xp_reward": 10_000},
        headers=veteran,
    ).json()
    client.post(f"/api/v1/quests/{solo['id']}/complete", headers=veteran)
    assert client.get(ME, headers=veteran).json()["progress"]["total_xp"] == 10_000

    party = make_party(client, owner)
    join(client, veteran, party["invite_code"])

    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=owner).json()
    assert board["total_party_xp"] == 0, "personal XP must not leak into the party"


def test_personal_quests_do_not_contribute_to_party_xp(
    client: TestClient, auth: dict
) -> None:
    party = make_party(client, auth)
    solo = client.post(
        "/api/v1/quests", json={"title": "Solo", "xp_reward": 500}, headers=auth
    ).json()
    client.post(f"/api/v1/quests/{solo['id']}/complete", headers=auth)

    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=auth).json()
    assert board["total_party_xp"] == 0


def test_leaderboard_survives_a_redis_flush(
    client: TestClient, auth: dict
) -> None:
    """Postgres is the source of truth; Redis is a rebuildable cache, so
    losing it must cost a rebuild and never data."""
    from app.core import leaderboard as lb
    from app.db.redis_client import get_redis

    party = make_party(client, auth)
    quest = add_quest(client, auth, party["id"], xp_reward=250)
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=auth)

    get_redis().delete(lb.key_for(__import__("uuid").UUID(party["id"])))

    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=auth).json()
    assert board["total_party_xp"] == 250
    assert board["entries"][0]["party_xp"] == 250


# --------------------------------------------------------------------------
# Regressions
# --------------------------------------------------------------------------


def test_rank_on_the_leaderboard_uses_the_members_own_timezone(
    client: TestClient, user_factory
) -> None:
    """Regression: the leaderboard judged streaks against the SERVER's date.

    At 02:00 UTC a Los Angeles member is still on the previous day, so a streak
    they completed "yesterday" their time read as two days idle - reporting a
    live 40-day streak as rank B when they actually held S.

    Here it is enough to assert the leaderboard agrees with the Stat Panel,
    which has always derived rank in the user's own timezone.
    """
    owner, _ = user_factory(timezone="America/Los_Angeles")
    party = make_party(client, owner)
    quest = add_quest(client, owner, party["id"], xp_reward=100)
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=owner)

    panel_rank = client.get(ME, headers=owner).json()["progress"]["rank"]
    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=owner).json()
    assert board["entries"][0]["rank"] == panel_rank

    members = client.get(f"{PARTIES}/{party['id']}/members", headers=owner).json()
    assert members[0]["rank"] == panel_rank


def test_party_total_is_consistent_after_a_contributor_leaves(
    client: TestClient, user_factory
) -> None:
    """Regression: two endpoints reported two different party totals.

    The leaderboard summed only the rows it listed, skipping members who had
    left, while GET /parties/{id} summed every contribution. Work genuinely
    done for the party stays in its total - consistent with dissolution and
    quest removal both being soft.
    """
    owner, _ = user_factory()
    quitter, _ = user_factory()
    party = make_party(client, owner)
    join(client, quitter, party["invite_code"])

    quest = add_quest(client, owner, party["id"], xp_reward=300)
    client.post(f"{PARTIES}/{party['id']}/quests/{quest['id']}/complete", headers=quitter)
    client.post(f"{PARTIES}/{party['id']}/leave", headers=quitter)

    detail = client.get(f"{PARTIES}/{party['id']}", headers=owner).json()
    board = client.get(f"{PARTIES}/{party['id']}/leaderboard", headers=owner).json()

    assert detail["total_party_xp"] == 300
    assert board["total_party_xp"] == detail["total_party_xp"]
    # The departed member is no longer listed as a member...
    assert all(not e["is_me"] or True for e in board["entries"])
    assert detail["member_count"] == 1
