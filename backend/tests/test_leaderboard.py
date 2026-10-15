"""Redis is a cache: every failure must degrade to Postgres, never raise."""

import uuid
from unittest import mock

import redis

from app.core import leaderboard


def test_key_is_versioned_and_party_scoped() -> None:
    pid = uuid.uuid4()
    key = leaderboard.key_for(pid)
    assert leaderboard.KEY_VERSION in key
    assert str(pid) in key


def test_add_xp_ignores_non_positive_amounts() -> None:
    with mock.patch.object(leaderboard, "get_redis") as get:
        leaderboard.add_xp(uuid.uuid4(), uuid.uuid4(), 0)
        leaderboard.add_xp(uuid.uuid4(), uuid.uuid4(), -5)
    get.assert_not_called()


def test_add_xp_swallows_redis_errors() -> None:
    with mock.patch.object(
        leaderboard, "get_redis", side_effect=redis.ConnectionError("down")
    ):
        leaderboard.add_xp(uuid.uuid4(), uuid.uuid4(), 10)


def test_top_returns_cached_ranking_without_touching_the_database() -> None:
    client = mock.Mock()
    client.zrevrange.return_value = [("a", 30.0), ("b", 10.0)]
    db = mock.Mock()
    with mock.patch.object(leaderboard, "get_redis", return_value=client):
        assert leaderboard.top(db, uuid.uuid4()) == [("a", 30), ("b", 10)]
    db.execute.assert_not_called()


def test_top_falls_back_to_postgres_when_redis_is_down() -> None:
    scores = {"a": 5, "b": 50, "c": 20}
    with (
        mock.patch.object(
            leaderboard, "get_redis", side_effect=redis.ConnectionError("down")
        ),
        mock.patch.object(leaderboard, "compute_from_db", return_value=scores),
    ):
        assert leaderboard.top(mock.Mock(), uuid.uuid4(), limit=2) == [
            ("b", 50),
            ("c", 20),
        ]


def test_top_rebuilds_on_a_cache_miss() -> None:
    client = mock.Mock()
    client.zrevrange.return_value = []
    with (
        mock.patch.object(leaderboard, "get_redis", return_value=client),
        mock.patch.object(leaderboard, "compute_from_db", return_value={"a": 7}),
    ):
        assert leaderboard.top(mock.Mock(), uuid.uuid4()) == [("a", 7)]
    client.pipeline.return_value.zadd.assert_called_once()


def test_drop_swallows_redis_errors() -> None:
    with mock.patch.object(
        leaderboard, "get_redis", side_effect=redis.ConnectionError("down")
    ):
        leaderboard.drop(uuid.uuid4())
