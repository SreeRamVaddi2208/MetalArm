"""Overhaul phase 4: follows, the feed and its visibility rules, reactions,
notifications, people, the friends leaderboard, the game strip, and duels
between friends.

The gate: two accounts can follow each other, see each other's workouts,
react, and duel.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_workouts import BENCH, exercise_id, finish, log, start

A = "/api/v1"


def person(user_factory, name: str = "Tester"):
    headers, me = user_factory()
    return headers, me["id"]


def workout(client: TestClient, headers: dict, name: str = "Push", visibility: str | None = None,
            weight: float = 100) -> str:
    body = {"name": name, **({"visibility": visibility} if visibility else {})}
    s = start(client, headers, **body)
    bench = exercise_id(client, headers, BENCH)
    for _ in range(3):
        log(client, headers, s["id"], bench, weight, 5)
    finish(client, headers, s["id"])
    return s["id"]


def feed(client: TestClient, headers: dict) -> list[dict]:
    return client.get(f"{A}/feed/following", headers=headers).json()["items"]


def unread(client: TestClient, headers: dict) -> list[dict]:
    return [n for n in client.get(f"{A}/notifications", headers=headers).json()["items"] if not n["read"]]


# ---------------------------------------------------------------------------
# Follows and friends
# ---------------------------------------------------------------------------


def test_follow_is_one_way_until_it_is_mutual(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id) = person(user_factory), person(user_factory)
    assert client.post(f"{A}/follows/{b_id}", headers=a).status_code == 204
    assert client.post(f"{A}/follows/{b_id}", headers=a).status_code == 204  # again: fine
    prof = client.get(f"{A}/users/{b_id}", headers=a).json()
    assert (prof["followers"], prof["user"]["you_follow"], prof["user"]["follows_you"], prof["is_friend"]) == (
        1, True, False, False)
    client.post(f"{A}/follows/{a_id}", headers=b)
    assert client.get(f"{A}/users/{b_id}", headers=a).json()["is_friend"] is True
    # Followers and following lists.
    assert [u["id"] for u in client.get(f"{A}/users/{b_id}/followers", headers=a).json()["items"]] == [a_id]
    assert client.post(f"{A}/follows/{a_id}", headers=a).status_code == 422
    assert client.delete(f"{A}/follows/{b_id}", headers=a).status_code == 204
    assert client.get(f"{A}/users/{b_id}", headers=a).json()["is_friend"] is False


def test_a_follow_notifies_once(client: TestClient, user_factory) -> None:
    (a, a_id), (b, _) = person(user_factory), person(user_factory)
    b_id = client.get(f"{A}/auth/me", headers=b).json()["id"]
    for _ in range(2):
        client.post(f"{A}/follows/{b_id}", headers=a)
        client.delete(f"{A}/follows/{b_id}", headers=a)
    client.post(f"{A}/follows/{b_id}", headers=a)
    notes = unread(client, b)
    assert [(n["type"], n["actor"]["id"]) for n in notes] == [("follow", a_id)]


# ---------------------------------------------------------------------------
# The feed and visibility
# ---------------------------------------------------------------------------


def test_the_feed_shows_what_each_workout_allows(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id), (c, _) = person(user_factory), person(user_factory), person(user_factory)
    open_ = workout(client, b, "Open", "public")
    fans = workout(client, b, "Fans", "followers")
    secret = workout(client, b, "Secret", "private")
    mine = workout(client, a, "Mine", "private")
    # Before following: only A's own.
    assert [i["name"] for i in feed(client, a)] == ["Mine"]
    client.post(f"{A}/follows/{b_id}", headers=a)
    names = [i["name"] for i in feed(client, a)]
    assert names == ["Mine", "Fans", "Open"]          # newest first; never "Secret"
    # Someone who does not follow B sees only the public one on B's profile.
    assert [i["name"] for i in client.get(f"{A}/users/{b_id}/sessions", headers=c).json()["items"]] == ["Open"]
    assert client.get(f"{A}/users/{b_id}", headers=c).json()["workouts"] == 1
    # The full workout follows the same rule.
    assert client.get(f"{A}/workouts/sessions/{fans}", headers=a).status_code == 200
    assert client.get(f"{A}/workouts/sessions/{fans}", headers=c).status_code == 404
    assert client.get(f"{A}/workouts/sessions/{secret}", headers=a).status_code == 404
    assert client.get(f"{A}/workouts/sessions/{open_}", headers=c).status_code == 200
    # Making it private later takes it out.
    client.patch(f"{A}/workouts/sessions/{fans}", json={"visibility": "private"}, headers=b)
    assert "Fans" not in [i["name"] for i in feed(client, a)]
    assert mine


def test_a_feed_card_carries_the_finish_totals(client: TestClient, user_factory) -> None:
    (a, _), (b, b_id) = person(user_factory), person(user_factory)
    workout(client, b, "Heavy", "public", weight=100)
    client.post(f"{A}/follows/{b_id}", headers=a)
    item = feed(client, a)[0]
    assert (item["volume_kg"], item["working_sets"], item["user"]["id"]) == (1500.0, 3, b_id)
    assert item["exercises"] == [{"name": BENCH, "thumbnail_url": item["exercises"][0]["thumbnail_url"], "sets": 3}]
    assert item["more_exercises"] == 0 and item["points"] > 0
    assert item["user"]["rank"] and item["user"]["level"] >= 1


def test_the_feed_pages(client: TestClient, user_factory) -> None:
    a, _ = person(user_factory)
    for n in range(3):
        workout(client, a, f"W{n}")
    first = client.get(f"{A}/feed/following", params={"limit": 2}, headers=a).json()
    second = client.get(f"{A}/feed/following", params={"limit": 2, "cursor": first["next_cursor"]}, headers=a).json()
    assert [i["name"] for i in first["items"] + second["items"]] == ["W2", "W1", "W0"]
    assert second["next_cursor"] is None


# ---------------------------------------------------------------------------
# Reactions and notifications
# ---------------------------------------------------------------------------


def test_spotting_a_workout(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id), (c, _) = person(user_factory), person(user_factory), person(user_factory)
    s = workout(client, b, "Legs", "followers")
    # Not visible to A yet: 404, not a reaction.
    assert client.post(f"{A}/workouts/sessions/{s}/reactions", headers=a).status_code == 404
    client.post(f"{A}/follows/{b_id}", headers=a)
    r = client.post(f"{A}/workouts/sessions/{s}/reactions", headers=a).json()
    assert r == {"spotted": 1, "spotted_by_me": True}
    assert client.post(f"{A}/workouts/sessions/{s}/reactions", headers=a).json()["spotted"] == 1
    assert feed(client, a)[0]["spotted_by_me"] is True
    notes = unread(client, b)
    reaction = next(n for n in notes if n["type"] == "reaction")
    assert reaction["actor"]["id"] == a_id and reaction["target_id"] == s
    assert client.delete(f"{A}/workouts/sessions/{s}/reactions", headers=a).json() == {"spotted": 0, "spotted_by_me": False}
    # Spotting your own workout tells nobody.
    client.post(f"{A}/workouts/sessions/{s}/reactions", headers=b)
    assert [n["type"] for n in unread(client, b)].count("reaction") == 1
    assert client.post(f"{A}/workouts/sessions/{s}/reactions", headers=c).status_code == 404


def test_friends_hear_about_records_and_you_about_quests(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id) = person(user_factory), person(user_factory)
    client.post(f"{A}/follows/{b_id}", headers=a)
    client.post(f"{A}/follows/{a_id}", headers=b)
    workout(client, b, "Baseline", "followers", weight=80)
    assert not [n for n in unread(client, a) if n["type"] == "friend_pr"]   # a first lift is a baseline
    workout(client, b, "Heavier", "followers", weight=90)
    pr = [n for n in unread(client, a) if n["type"] == "friend_pr"]
    assert len(pr) == 1 and pr[0]["actor"]["id"] == b_id and BENCH in pr[0]["detail"]
    # Generated quests vary, so: exactly one notification per quest completed.
    board = client.get(f"{A}/quests/current", headers=b).json()
    done = {q["id"] for q in board["daily"] + board["weekly"] if q["status"] == "completed"}
    told = {n["target_id"] for n in unread(client, b) if n["type"] == "quest_complete"}
    assert told == done
    assert all(n["actor"] is None for n in unread(client, b) if n["type"] == "quest_complete")


def test_notifications_mark_read(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id) = person(user_factory), person(user_factory)
    client.post(f"{A}/follows/{b_id}", headers=a)
    page = client.get(f"{A}/notifications", headers=b).json()
    assert page["unread"] >= 1
    assert client.post(f"{A}/notifications/read", json={}, headers=b).json() == {"unread": 0}
    assert all(n["read"] for n in client.get(f"{A}/notifications", headers=b).json()["items"])


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


def test_people_search_and_suggestions(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id), (c, c_id) = person(user_factory), person(user_factory), person(user_factory)
    client.patch(f"{A}/auth/me", json={"display_name": "Quintessa Lift"}, headers=c)
    found = client.get(f"{A}/users/search", params={"q": "quintes"}, headers=a).json()["items"]
    assert [u["id"] for u in found] == [c_id]
    # Never yourself; never by email.
    assert client.get(f"{A}/users/search", params={"q": "quintes"}, headers=c).json()["items"] == []
    email = client.get(f"{A}/auth/me", headers=c).json()["email"]
    assert client.get(f"{A}/users/search", params={"q": email}, headers=a).json()["items"] == []
    # Friends of friends: A follows B, B follows C -> C is suggested to A, via B.
    client.patch(f"{A}/auth/me", json={"display_name": "Bea"}, headers=b)
    client.post(f"{A}/follows/{b_id}", headers=a)
    client.post(f"{A}/follows/{c_id}", headers=b)
    suggested = client.get(f"{A}/users/suggested", headers=a).json()["items"]
    assert suggested[0]["id"] == c_id and suggested[0]["reason"] == "Followed by Bea"
    client.post(f"{A}/follows/{c_id}", headers=a)
    assert c_id not in [u["id"] for u in client.get(f"{A}/users/suggested", headers=a).json()["items"]]


# ---------------------------------------------------------------------------
# Duels between friends - no party needed
# ---------------------------------------------------------------------------


def test_friends_can_duel_strangers_cannot(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id) = person(user_factory), person(user_factory)
    body = {"opponent_id": b_id, "metric": "volume", "days": 7}
    assert client.post(f"{A}/duels", json=body, headers=a).status_code == 404
    client.post(f"{A}/follows/{b_id}", headers=a)
    assert client.post(f"{A}/duels", json=body, headers=a).status_code == 404   # one-way is not friends
    client.post(f"{A}/follows/{a_id}", headers=b)
    assert [u["id"] for u in client.get(f"{A}/duels/opponents", headers=a).json()] == [b_id]
    duel = client.post(f"{A}/duels", json=body, headers=a)
    assert duel.status_code == 201, duel.text
    challenge = next(n for n in unread(client, b) if n["type"] == "duel_challenge")
    assert challenge["target_id"] == duel.json()["id"]
    accepted = client.post(f"{A}/duels/{duel.json()['id']}/accept", headers=b)
    assert accepted.status_code == 200 and accepted.json()["status"] == "active"


# ---------------------------------------------------------------------------
# The leaderboard and the game strip
# ---------------------------------------------------------------------------


def test_friends_leaderboard_ranks_by_points(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id), (c, c_id) = person(user_factory), person(user_factory), person(user_factory)
    workout(client, b, "B", weight=100)
    client.post(f"{A}/follows/{b_id}", headers=a)
    client.post(f"{A}/follows/{c_id}", headers=a)
    board = client.get(f"{A}/leaderboard/friends", headers=a).json()
    rows = [(r["user"]["id"], r["position"]) for r in board["rows"]]
    assert rows[0] == (b_id, 1)
    # A and C have 0 points: they share second place.
    assert sorted(p for _, p in rows[1:]) == [2, 2]
    assert board["me"]["user"]["id"] == a_id and board["me"]["points"] == 0
    points_b = board["rows"][0]["points"]
    assert client.get(f"{A}/leaderboard/friends", params={"period": "all"}, headers=a).json()["rows"][0]["points"] == points_b


def test_the_game_strip(client: TestClient, user_factory) -> None:
    (a, a_id), (b, b_id) = person(user_factory), person(user_factory)
    workout(client, a, "A")
    client.post(f"{A}/follows/{a_id}", headers=b)
    g = client.get(f"{A}/me/game", headers=a).json()
    me = client.get(f"{A}/auth/me", headers=a).json()["progress"]
    assert g["rank"] == me["rank"] and g["level"] == me["current_level"] and g["xp"] == me["total_xp"]
    assert g["next_rank"] == me["next_rank"] and g["xp_next_rank"] > g["xp"]
    assert g["points_this_week"] > 0 and g["quests_total"] >= g["quests_done"] >= 0
    assert g["unread_notifications"] >= 1          # B's follow
