"""Rate limits on the auth endpoints (app/core/rate_limit.py).

conftest switches limiting off for the rest of the suite; these tests switch it
back on and clear only the counters they create, so repeated runs within a
window start clean.
"""

from collections.abc import Generator

import pytest
import redis
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.config import get_settings
from app.core.security import normalize_email
from app.db.redis_client import get_redis
from tests.conftest import unique_email

settings = get_settings()
SIGNUP = "/api/v1/auth/signup"
LOGIN = "/api/v1/auth/login"
TEST_CLIENT_IP = "testclient"


def _clear(*keys: str) -> None:
    client = get_redis()
    for key in keys:
        client.delete(key)


def _ip_keys() -> list[str]:
    limits = (rate_limit.LOGIN_PER_IP, rate_limit.SIGNUP_PER_IP, rate_limit.REFRESH_PER_IP)
    return [f"ratelimit:{limit.scope}:{TEST_CLIENT_IP}" for limit in limits]


@pytest.fixture
def limits_on(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    _clear(*_ip_keys())
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    yield
    _clear(*_ip_keys())


def test_login_is_limited_per_account(client: TestClient, limits_on: None) -> None:
    email = unique_email()
    client.post(SIGNUP, json={"email": email, "password": "correct-horse-1", "display_name": "Sung"})
    email_key = f"ratelimit:{rate_limit.LOGIN_PER_EMAIL.scope}:{normalize_email(email)}"
    try:
        for _ in range(rate_limit.LOGIN_PER_EMAIL.max_requests):
            r = client.post(LOGIN, json={"email": email, "password": "wrong-pass-9"})
            assert r.status_code == 401

        blocked = client.post(LOGIN, json={"email": email, "password": "correct-horse-1"})
        assert blocked.status_code == 429
        assert int(blocked.headers["Retry-After"]) > 0
    finally:
        _clear(email_key)


def test_signup_is_limited_per_address(client: TestClient, limits_on: None) -> None:
    for _ in range(rate_limit.SIGNUP_PER_IP.max_requests):
        r = client.post(SIGNUP, json={"email": unique_email(), "password": "correct-horse-1", "display_name": "A"})
        assert r.status_code == 201, r.text

    r = client.post(SIGNUP, json={"email": unique_email(), "password": "correct-horse-1", "display_name": "A"})
    assert r.status_code == 429


def test_limiter_fails_open_when_redis_is_down(
    client: TestClient, limits_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable() -> redis.Redis:
        raise redis.ConnectionError("redis is down")

    monkeypatch.setattr(rate_limit, "get_redis", unavailable)
    r = client.post(LOGIN, json={"email": unique_email(), "password": "wrong-pass-9"})
    # Normal auth failure, not a 500 and not a 429.
    assert r.status_code == 401
